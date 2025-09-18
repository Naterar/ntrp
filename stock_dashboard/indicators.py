"""Collection of helper functions for computing popular technical indicators."""
from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd


def calculate_sma(close: pd.Series, window: int = 20) -> pd.Series:
    """Simple moving average of ``close`` prices."""
    return close.rolling(window=window, min_periods=window).mean()


def calculate_ema(close: pd.Series, span: int = 20) -> pd.Series:
    """Exponential moving average of ``close`` prices."""
    return close.ewm(span=span, adjust=False).mean()


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (RSI).

    The implementation follows the classic Wilder smoothing technique.
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Return MACD line, signal line and histogram."""
    fast_ema = calculate_ema(close, span=fast)
    slow_ema = calculate_ema(close, span=slow)
    macd_line = fast_ema - slow_ema
    signal_line = calculate_ema(macd_line, span=signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram
