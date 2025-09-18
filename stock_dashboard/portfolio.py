"""Lightweight SQLite-backed portfolio tracker used by the dashboard."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd

from .data import fetch_latest_price


@dataclass
class Trade:
    """Simple representation of a trade captured through the UI."""

    symbol: str
    trade_date: date
    quantity: float
    price: float
    side: str
    fees: float = 0.0

    def normalized_symbol(self) -> str:
        return self.symbol.strip().upper()

    def normalized_side(self) -> str:
        return self.side.strip().upper()


class PortfolioManager:
    """Persist and summarise trade history using SQLite."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        default_path = Path(__file__).resolve().parent / "data" / "portfolio.db"
        self.db_path = Path(db_path) if db_path else default_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    side TEXT NOT NULL,
                    fees REAL NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_trade(self, trade: Trade) -> None:
        """Store a trade in the database."""
        symbol = trade.normalized_symbol()
        side = trade.normalized_side()

        if side not in {"BUY", "SELL"}:
            raise ValueError("Trade side must be either 'BUY' or 'SELL'.")
        if trade.quantity <= 0:
            raise ValueError("Quantity must be positive.")
        if trade.price <= 0:
            raise ValueError("Price must be positive.")

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO trades(symbol, trade_date, quantity, price, side, fees)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    trade.trade_date.isoformat(),
                    float(trade.quantity),
                    float(trade.price),
                    side,
                    float(trade.fees or 0.0),
                ),
            )
            conn.commit()

    def clear_trades(self) -> None:
        """Remove all stored trades."""
        with self._connect() as conn:
            conn.execute("DELETE FROM trades")
            conn.commit()

    def get_trades(self) -> pd.DataFrame:
        """Return the trade ledger as a DataFrame."""
        with self._connect() as conn:
            df = pd.read_sql_query(
                "SELECT symbol, trade_date, quantity, price, side, fees FROM trades ORDER BY trade_date",
                conn,
                parse_dates=["trade_date"],
            )
        if df.empty:
            return df
        df["symbol"] = df["symbol"].str.upper()
        df["side"] = df["side"].str.upper()
        return df

    # ------------------------------------------------------------------
    # Reporting helpers
    # ------------------------------------------------------------------
    def _latest_prices(self, symbols: Iterable[str]) -> Dict[str, Optional[float]]:
        prices: Dict[str, Optional[float]] = {}
        for symbol in symbols:
            prices[symbol] = fetch_latest_price(symbol)  # pragma: no cover - network access
        return prices

    def _summarise_symbol(
        self, trades: pd.DataFrame, market_price: Optional[float]
    ) -> Dict[str, float]:
        trades = trades.sort_values("trade_date")
        avg_cost = 0.0
        net_qty = 0.0
        realized = 0.0

        for _, row in trades.iterrows():
            qty = float(row["quantity"])
            price = float(row["price"])
            fees = float(row.get("fees", 0.0))
            side = row["side"].upper()

            if side == "BUY":
                total_cost = avg_cost * net_qty + price * qty + fees
                net_qty += qty
                avg_cost = total_cost / net_qty if net_qty else 0.0
            else:  # SELL
                if net_qty <= 0:
                    # No existing position; treat as opening a short with sale price as cost basis.
                    net_qty -= qty
                    avg_cost = price
                    realized -= fees
                else:
                    sell_qty = min(qty, net_qty)
                    realized += (price - avg_cost) * sell_qty - fees
                    net_qty -= sell_qty
                    if net_qty == 0:
                        avg_cost = 0.0
                    elif qty > sell_qty:
                        # additional quantity turns the position short
                        short_qty = qty - sell_qty
                        net_qty -= short_qty
                        avg_cost = price
        market_value = None
        unrealized = None
        total_pl = realized

        if market_price is not None:
            market_value = market_price * net_qty
            unrealized = (market_price - avg_cost) * net_qty
            total_pl = realized + (unrealized or 0.0)

        return {
            "net_quantity": net_qty,
            "average_cost": avg_cost,
            "market_price": market_price if market_price is not None else float("nan"),
            "market_value": market_value if market_value is not None else float("nan"),
            "realized_pl": realized,
            "unrealized_pl": unrealized if unrealized is not None else float("nan"),
            "total_pl": total_pl,
        }

    def get_portfolio_summary(
        self, latest_prices: Optional[Dict[str, float]] = None
    ) -> pd.DataFrame:
        """Summarise all symbols currently stored in the trade ledger."""
        trades = self.get_trades()
        if trades.empty:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "net_quantity",
                    "average_cost",
                    "market_price",
                    "market_value",
                    "realized_pl",
                    "unrealized_pl",
                    "total_pl",
                ]
            )

        symbols = trades["symbol"].unique()
        price_lookup = dict(latest_prices or {})
        missing = [symbol for symbol in symbols if price_lookup.get(symbol) is None]
        if missing:
            price_lookup.update(self._latest_prices(missing))

        rows = []
        for symbol in symbols:
            metrics = self._summarise_symbol(trades[trades["symbol"] == symbol], price_lookup.get(symbol))
            rows.append({"symbol": symbol, **metrics})

        summary = pd.DataFrame(rows)
        return summary
