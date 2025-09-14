import io
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# ---------- Page & Layout ----------
st.set_page_config(
    page_title="Stock Market Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Utilities ----------


@st.cache_data(show_spinner=False, ttl=60)
def fetch_prices(ticker: str, start: pd.Timestamp, end: pd.Timestamp, interval: str) -> pd.DataFrame:
    df = yf.download(
        tickers=ticker,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if isinstance(df, pd.DataFrame) and not df.empty:
        df = df.rename(columns=str.title)  # Open, High, Low, Close, Volume
        df.dropna(how="any", inplace=True)
    return df


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False, min_periods=window).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(gain, index=series.index).rolling(window).mean()
    roll_down = pd.Series(loss, index=series.index).rolling(window).mean()
    rs = roll_up / roll_down
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def macd(series: pd.Series, fast=12, slow=26, signal=9):
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def equity_curve(returns: pd.Series) -> pd.Series:
    return (1 + returns.fillna(0)).cumprod()


def format_usd(x: float) -> str:
    return f"${x:,.2f}"


# ---------- Sidebar Controls ----------
st.sidebar.header("Inputs")

default_ticker = "AAPL"
ticker = st.sidebar.text_input("Ticker", value=default_ticker).strip().upper()

today = date.today()
start = st.sidebar.date_input("Start date", today - timedelta(days=365))
end = st.sidebar.date_input("End date", today)
interval = st.sidebar.selectbox(
    "Interval",
    ["1d", "1h", "30m", "15m", "5m"],
    index=0,
    help="Shorter intervals may have fewer historical days available.",
)

st.sidebar.divider()
st.sidebar.subheader("Indicators")
show_sma = st.sidebar.checkbox("SMA", value=True)
sma_fast = st.sidebar.number_input(
    "SMA Fast", min_value=2, max_value=200, value=20, step=1)
sma_slow = st.sidebar.number_input(
    "SMA Slow", min_value=3, max_value=400, value=50, step=1)

show_ema = st.sidebar.checkbox("EMA", value=False)
ema_fast = st.sidebar.number_input(
    "EMA Fast", min_value=2, max_value=200, value=12, step=1)
ema_slow = st.sidebar.number_input(
    "EMA Slow", min_value=3, max_value=400, value=26, step=1)

show_rsi = st.sidebar.checkbox("RSI", value=False)
rsi_window = st.sidebar.number_input(
    "RSI Window", min_value=2, max_value=50, value=14, step=1)
rsi_overbought = st.sidebar.slider("RSI Overbought", 50, 90, 70, step=1)
rsi_oversold = st.sidebar.slider("RSI Oversold", 10, 50, 30, step=1)

show_macd = st.sidebar.checkbox("MACD", value=False)

st.sidebar.divider()
st.sidebar.subheader("Backtest: SMA Crossover (Long-only)")
bt_fast = st.sidebar.number_input(
    "Fast Window", min_value=2, max_value=200, value=20)
bt_slow = st.sidebar.number_input(
    "Slow Window", min_value=3, max_value=400, value=50)
use_rsi_filter = st.sidebar.checkbox(
    "Use RSI Filter", value=False, help="Enter only when RSI > 50, exit when RSI < 50")

st.sidebar.divider()
st.sidebar.caption("Powered by yfinance • For educational use")

# ---------- Data ----------
if start >= end:
    st.error("Start date must be before End date.")
    st.stop()

prices = fetch_prices(ticker, pd.to_datetime(start),
                      pd.to_datetime(end), interval)
if prices is None or prices.empty:
    st.error("No market data returned. Try a different ticker or date range.")
    st.stop()

close = prices["Close"].copy()

# Indicators
indicators = {}
if show_sma:
    indicators["SMA Fast"] = sma(close, sma_fast)
    indicators["SMA Slow"] = sma(close, sma_slow)
if show_ema:
    indicators["EMA Fast"] = ema(close, ema_fast)
    indicators["EMA Slow"] = ema(close, ema_slow)
if show_rsi:
    indicators["RSI"] = rsi(close, rsi_window)
if show_macd:
    macd_line, signal_line, hist = macd(close)
    indicators["MACD"] = macd_line
    indicators["Signal"] = signal_line
    indicators["MACD Hist"] = hist

# ---------- Layout Tabs ----------
tab_overview, tab_backtest, tab_portfolio = st.tabs(
    ["📈 Overview", "🧪 Backtest", "💼 Portfolio"])

# ---------- Overview Tab ----------
with tab_overview:
    st.markdown(f"### {ticker} — {start} to {end} — Interval: {interval}")

    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=prices.index,
            open=prices["Open"], high=prices["High"], low=prices["Low"], close=prices["Close"],
            name="Price"
        )
    )
    # Overlays
    if "SMA Fast" in indicators:
        fig.add_trace(go.Scatter(
            x=prices.index, y=indicators["SMA Fast"], name=f"SMA {sma_fast}", mode="lines"))
    if "SMA Slow" in indicators:
        fig.add_trace(go.Scatter(
            x=prices.index, y=indicators["SMA Slow"], name=f"SMA {sma_slow}", mode="lines"))
    if "EMA Fast" in indicators:
        fig.add_trace(go.Scatter(
            x=prices.index, y=indicators["EMA Fast"], name=f"EMA {ema_fast}", mode="lines"))
    if "EMA Slow" in indicators:
        fig.add_trace(go.Scatter(
            x=prices.index, y=indicators["EMA Slow"], name=f"EMA {ema_slow}", mode="lines"))

    fig.update_layout(
        height=600,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # RSI/MACD subplots
    if show_rsi:
        st.markdown("**RSI**")
        rsi_series = indicators["RSI"].copy()
        rsi_fig = go.Figure()
        rsi_fig.add_trace(go.Scatter(
            x=prices.index, y=rsi_series, name="RSI", mode="lines"))
        rsi_fig.add_hline(y=rsi_overbought, line_dash="dot")
        rsi_fig.add_hline(y=rsi_oversold, line_dash="dot")
        rsi_fig.update_layout(height=200, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(rsi_fig, use_container_width=True)

    if show_macd:
        st.markdown("**MACD**")
        macd_fig = go.Figure()
        macd_fig.add_trace(go.Scatter(
            x=prices.index, y=indicators["MACD"], name="MACD", mode="lines"))
        macd_fig.add_trace(go.Scatter(
            x=prices.index, y=indicators["Signal"], name="Signal", mode="lines"))
        macd_fig.add_trace(
            go.Bar(x=prices.index, y=indicators["MACD Hist"], name="Hist"))
        macd_fig.update_layout(
            height=220, barmode="relative", margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(macd_fig, use_container_width=True)

# ---------- Backtest Tab ----------
with tab_backtest:
    st.subheader("SMA Crossover Strategy (Long-Only)")

    fast = sma(close, int(bt_fast))
    slow = sma(close, int(bt_slow))
    valid = (~fast.isna()) & (~slow.isna())
    signal_long = (fast > slow) & valid
    signal_prev = signal_long.shift(1).fillna(False)

    entries = (~signal_prev) & (signal_long)  # cross up
    exits = (signal_prev) & (~signal_long)    # cross down

    bt_df = pd.DataFrame({"Close": close, "FastSMA": fast, "SlowSMA": slow})
    bt_df["Position"] = np.where(signal_long, 1.0, 0.0)

    if use_rsi_filter:
        rsi_series = rsi(close, 14).fillna(50)
        enter_filter = rsi_series > 50
        exit_filter = rsi_series < 50
        bt_df["Position"] = np.where(enter_filter, bt_df["Position"], 0.0)
        bt_df.loc[exit_filter, "Position"] = 0.0

    # returns
    bt_df["Return"] = close.pct_change().fillna(0.0)
    bt_df["StrategyReturn"] = bt_df["Position"].shift(
        1).fillna(0.0) * bt_df["Return"]
    eq = equity_curve(bt_df["StrategyReturn"])
    bench = equity_curve(bt_df["Return"])

    # Metrics
    total_ret = eq.iloc[-1] - 1.0
    bench_ret = bench.iloc[-1] - 1.0
    ann_factor = 252
    vol = bt_df["StrategyReturn"].std() * np.sqrt(ann_factor)
    avg = bt_df["StrategyReturn"].mean() * ann_factor
    sharpe = (avg / vol) if vol > 0 else np.nan
    cagr = (eq.iloc[-1]) ** (252 / max(len(bt_df), 1)) - \
        1 if len(bt_df) > 0 else np.nan

    col1, col2, col
