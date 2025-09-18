"""Utility functions for retrieving market data using yfinance."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd
import yfinance as yf


@dataclass
class PriceRequest:
    """Container describing how much history should be fetched for a ticker."""

    symbol: str
    period: str = "6mo"
    interval: str = "1d"

    def normalized_symbol(self) -> str:
        """Return the symbol upper-cased and stripped of whitespace."""
        return self.symbol.strip().upper()


def _clean_index(frame: pd.DataFrame) -> pd.DataFrame:
    """Ensure the dataframe index is timezone naive for plotting purposes."""
    if isinstance(frame.index, pd.DatetimeIndex):
        frame.index = frame.index.tz_localize(None)
    return frame


def fetch_price_data(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """Retrieve historical price data for a ticker symbol.

    Parameters
    ----------
    symbol:
        Ticker symbol recognised by Yahoo Finance (e.g. ``"AAPL"``).
    period:
        The look-back period such as ``"1mo"``, ``"6mo"``, or ``"1y"``.
    interval:
        Resolution of the data, e.g. ``"1d"`` for daily or ``"1h"`` for hourly bars.

    Returns
    -------
    pandas.DataFrame
        Historical OHLCV data indexed by timestamp.

    Raises
    ------
    ValueError
        If ``symbol`` is blank or no data could be downloaded.
    ConnectionError
        If yfinance raises an exception while requesting data.
    """
    cleaned_symbol = symbol.strip().upper()
    if not cleaned_symbol:
        raise ValueError("A ticker symbol is required to download price data.")

    request = PriceRequest(cleaned_symbol, period, interval)

    try:
        frame = yf.download(
            request.normalized_symbol(),
            period=request.period,
            interval=request.interval,
            auto_adjust=False,
            progress=False,
        )
    except Exception as exc:  # pragma: no cover - defensive guard for API errors
        raise ConnectionError(f"Could not download data for {cleaned_symbol}: {exc}") from exc

    if frame.empty:
        raise ValueError(
            "Yahoo Finance returned no data. Double check the ticker symbol and interval."
        )

    return _clean_index(frame)


def fetch_latest_price(symbol: str) -> Optional[float]:
    """Return the latest closing price for ``symbol`` if it can be determined."""
    cleaned_symbol = symbol.strip().upper()
    if not cleaned_symbol:
        return None

    try:
        latest = yf.download(
            cleaned_symbol,
            period="5d",
            interval="1d",
            progress=False,
        )
    except Exception:  # pragma: no cover - yfinance network failures
        return None

    if latest.empty:
        return None

    latest = _clean_index(latest)
    close_series = latest.get("Close")
    if close_series is None or close_series.empty:
        return None
    return float(close_series.iloc[-1])
