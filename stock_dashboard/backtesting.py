"""Simple backtesting utilities used by the Streamlit dashboard."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd

from .indicators import calculate_sma


@dataclass
class BacktestResult:
    """Container for the strategy equity curve and summary statistics."""

    equity_curve: pd.DataFrame
    statistics: Dict[str, float]


def _max_drawdown(series: pd.Series) -> float:
    """Return the maximum drawdown of a cumulative returns series."""
    if series.empty:
        return 0.0
    cumulative_max = series.cummax()
    drawdown = series / cumulative_max - 1
    return float(drawdown.min())


def ma_crossover_backtest(
    price_data: pd.DataFrame,
    fast_window: int = 20,
    slow_window: int = 50,
) -> BacktestResult:
    """Run a long-only moving average crossover backtest.

    Parameters
    ----------
    price_data:
        DataFrame that contains at least the ``Close`` column.
    fast_window / slow_window:
        Moving average look-back periods. ``fast_window`` must be shorter
        than ``slow_window``.
    """
    if "Close" not in price_data.columns:
        raise ValueError("price_data must contain a 'Close' column")
    if fast_window >= slow_window:
        raise ValueError("fast_window should be smaller than slow_window")

    frame = price_data[["Close"]].copy()
    frame["FastMA"] = calculate_sma(frame["Close"], window=fast_window)
    frame["SlowMA"] = calculate_sma(frame["Close"], window=slow_window)
    frame.dropna(inplace=True)

    if frame.empty:
        raise ValueError("Not enough data to compute the moving averages.")

    frame["Signal"] = 0
    frame.loc[frame["FastMA"] > frame["SlowMA"], "Signal"] = 1
    frame["Position"] = frame["Signal"].shift(1).fillna(0)

    frame["Market Return"] = frame["Close"].pct_change().fillna(0)
    frame["Strategy Return"] = frame["Market Return"] * frame["Position"]

    frame["Cumulative Market"] = (1 + frame["Market Return"]).cumprod()
    frame["Cumulative Strategy"] = (1 + frame["Strategy Return"]).cumprod()

    trades = frame["Position"].diff().abs().sum()
    winning_periods = (frame.loc[frame["Position"] != 0, "Strategy Return"] > 0).sum()
    active_periods = (frame["Position"] != 0).sum()
    win_rate = (winning_periods / active_periods) if active_periods else 0.0

    avg_return = frame["Strategy Return"].mean()
    volatility = frame["Strategy Return"].std()
    sharpe = (avg_return / volatility * (252 ** 0.5)) if volatility else 0.0

    statistics = {
        "total_trades": float(trades),
        "strategy_return_pct": float((frame["Cumulative Strategy"].iloc[-1] - 1) * 100),
        "market_return_pct": float((frame["Cumulative Market"].iloc[-1] - 1) * 100),
        "max_drawdown_pct": float(_max_drawdown(frame["Cumulative Strategy"]) * 100),
        "win_rate": float(win_rate),
        "sharpe_ratio": float(sharpe),
    }

    return BacktestResult(equity_curve=frame, statistics=statistics)
