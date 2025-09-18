"""Streamlit entry point for the Stock Market Analytics Dashboard."""
from __future__ import annotations

import io
from datetime import date
from typing import Dict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from stock_dashboard.backtesting import BacktestResult, ma_crossover_backtest
from stock_dashboard.data import fetch_price_data
from stock_dashboard.indicators import calculate_ema, calculate_macd, calculate_rsi, calculate_sma
from stock_dashboard.portfolio import PortfolioManager, Trade


st.set_page_config(
    page_title="Stock Market Analytics Dashboard",
    page_icon="📈",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Streamlit cache helpers
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_price_data(symbol: str, period: str, interval: str) -> pd.DataFrame:
    return fetch_price_data(symbol, period=period, interval=interval)



def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv().encode("utf-8")


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "data") -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name=sheet_name)
    return buffer.getvalue()


def prepare_indicator_data(
    price_data: pd.DataFrame, sma_window: int, ema_window: int, rsi_period: int
) -> pd.DataFrame:
    data = price_data.copy()
    data[f"SMA_{sma_window}"] = calculate_sma(data["Close"], window=sma_window)
    data[f"EMA_{ema_window}"] = calculate_ema(data["Close"], span=ema_window)
    data["RSI"] = calculate_rsi(data["Close"], period=rsi_period)
    macd_line, signal_line, hist = calculate_macd(data["Close"])
    data["MACD"] = macd_line
    data["MACD_Signal"] = signal_line
    data["MACD_Hist"] = hist
    data["Daily Change %"] = data["Close"].pct_change() * 100
    return data


def build_price_chart(
    data: pd.DataFrame,
    ticker: str,
    show_sma: bool,
    sma_window: int,
    show_ema: bool,
    ema_window: int,
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name=f"{ticker} price",
        )
    )

    if show_sma:
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data[f"SMA_{sma_window}"],
                mode="lines",
                name=f"SMA {sma_window}",
            )
        )

    if show_ema:
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data[f"EMA_{ema_window}"],
                mode="lines",
                name=f"EMA {ema_window}",
            )
        )

    fig.update_layout(
        title=f"{ticker} Candlestick Chart",
        yaxis_title="Price",
        xaxis_title="Date",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=600,
    )
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(showgrid=True)
    return fig


def build_rsi_chart(data: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data["RSI"], name="RSI", mode="lines"))
    fig.add_hline(y=70, line_dash="dash", line_color="red")
    fig.add_hline(y=30, line_dash="dash", line_color="green")
    fig.update_layout(
        title="Relative Strength Index",
        yaxis_title="RSI",
        xaxis_title="Date",
        template="plotly_white",
        height=300,
    )
    return fig


def build_macd_chart(data: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data["MACD"], name="MACD", mode="lines"))
    fig.add_trace(
        go.Scatter(x=data.index, y=data["MACD_Signal"], name="Signal", mode="lines")
    )
    fig.add_trace(
        go.Bar(x=data.index, y=data["MACD_Hist"], name="Histogram", opacity=0.4)
    )
    fig.update_layout(
        title="MACD",
        xaxis_title="Date",
        yaxis_title="Value",
        template="plotly_white",
        height=300,
        barmode="group",
    )
    return fig


def render_market_overview(data: pd.DataFrame, ticker: str) -> None:
    latest_close = float(data["Close"].iloc[-1])
    previous_close = float(data["Close"].iloc[-2]) if len(data) > 1 else latest_close
    percent_change = (
        ((latest_close - previous_close) / previous_close) * 100 if previous_close else 0.0
    )

    volume_value = data["Volume"].iloc[-1] if "Volume" in data.columns else None

    col1, col2, col3 = st.columns(3)
    col1.metric("Last close", f"${latest_close:,.2f}", f"{percent_change:+.2f}%")
    if volume_value is not None:
        col2.metric("Volume", f"{volume_value:,.0f}")
    if "Daily Change %" in data.columns and not pd.isna(data["Daily Change %"].iloc[-1]):
        col3.metric("Daily change", f"{data['Daily Change %'].iloc[-1]:+.2f}%")


def render_backtest_section(price_data: pd.DataFrame, ticker: str) -> None:
    st.subheader("Strategy Backtesting")
    st.markdown(
        "Test a simple moving average crossover strategy. A position is opened when the"
        " fast moving average crosses above the slow moving average and closed when it"
        " falls back below."
    )

    with st.form("backtest_form"):
        col1, col2, col3 = st.columns(3)
        fast_window = col1.number_input("Fast MA window", min_value=5, max_value=200, value=20)
        slow_window = col2.number_input("Slow MA window", min_value=10, max_value=300, value=50)
        initial_cash = col3.number_input(
            "Starting capital (for context)", min_value=1000.0, value=10000.0, step=500.0
        )
        run_backtest = st.form_submit_button("Run backtest")

    if not run_backtest:
        return

    try:
        result: BacktestResult = ma_crossover_backtest(
            price_data, fast_window=int(fast_window), slow_window=int(slow_window)
        )
    except ValueError as exc:
        st.error(str(exc))
        return

    st.success("Backtest completed.")

    stats = result.statistics
    col1, col2, col3 = st.columns(3)
    col1.metric("Strategy return", f"{stats['strategy_return_pct']:.2f}%")
    col2.metric("Market return", f"{stats['market_return_pct']:.2f}%")
    col3.metric("Sharpe ratio", f"{stats['sharpe_ratio']:.2f}")

    col4, col5, col6 = st.columns(3)
    col4.metric("Total trades", f"{stats['total_trades']:.0f}")
    col5.metric("Max drawdown", f"{stats['max_drawdown_pct']:.2f}%")
    col6.metric("Win rate", f"{stats['win_rate'] * 100:.2f}%")

    equity = result.equity_curve
    ending_value_strategy = initial_cash * float(equity["Cumulative Strategy"].iloc[-1])
    ending_value_market = initial_cash * float(equity["Cumulative Market"].iloc[-1])

    col7, col8 = st.columns(2)
    col7.metric("Strategy ending value", f'${ending_value_strategy:,.2f}')
    col8.metric("Buy & Hold ending value", f'${ending_value_market:,.2f}')

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=equity.index,
            y=equity["Cumulative Market"],
            name="Buy & Hold",
            mode="lines",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=equity.index,
            y=equity["Cumulative Strategy"],
            name="MA Crossover",
            mode="lines",
        )
    )
    fig.update_layout(
        title=f"{ticker} – Backtest Equity Curve",
        xaxis_title="Date",
        yaxis_title="Growth of $1",
        template="plotly_white",
        height=450,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Trade signals and returns")
    display_columns = [
        "Close",
        "FastMA",
        "SlowMA",
        "Signal",
        "Position",
        "Market Return",
        "Strategy Return",
    ]
    st.dataframe(equity[display_columns].tail(20))

    st.download_button(
        label="Download backtest (CSV)",
        data=dataframe_to_csv_bytes(equity),
        file_name=f"{ticker}_backtest.csv",
        mime="text/csv",
    )
    st.download_button(
        label="Download backtest (Excel)",
        data=dataframe_to_excel_bytes(equity, sheet_name="backtest"),
        file_name=f"{ticker}_backtest.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def render_portfolio_section(ticker: str, latest_close: float | None) -> None:
    st.subheader("Portfolio Tracker")
    st.markdown(
        "Log trades to keep track of position sizes and P&L. The tracker assumes"
        " long positions by default."
    )

    manager = PortfolioManager()

    with st.expander("Add a trade", expanded=True):
        with st.form("trade_form"):
            col1, col2 = st.columns(2)
            symbol = col1.text_input("Ticker", value=ticker).upper()
            trade_date = col2.date_input("Trade date", value=date.today())

            col3, col4, col5 = st.columns(3)
            quantity = col3.number_input("Quantity", min_value=0.0, value=1.0, step=1.0)
            price = col4.number_input("Price", min_value=0.0, value=latest_close or 0.0, step=0.5)
            side = col5.selectbox("Side", options=["BUY", "SELL"], index=0)
            fees = st.number_input("Fees (optional)", min_value=0.0, value=0.0, step=0.5)

            submitted = st.form_submit_button("Save trade")

        if submitted:
            try:
                trade = Trade(
                    symbol=symbol,
                    trade_date=trade_date,
                    quantity=float(quantity),
                    price=float(price),
                    side=side,
                    fees=float(fees),
                )
                manager.add_trade(trade)
                st.success("Trade saved. Scroll down to see the updated ledger.")
            except ValueError as exc:
                st.error(str(exc))

    with st.expander("Danger zone"):
        if st.button("Clear all trades"):
            manager.clear_trades()
            st.warning("Trade history cleared.")

    trades = manager.get_trades()
    if trades.empty:
        st.info("No trades recorded yet. Use the form above to add your first trade.")
        return

    st.markdown("### Trade history")
    st.dataframe(trades)
    st.download_button(
        label="Download trades (CSV)",
        data=dataframe_to_csv_bytes(trades),
        file_name="trade_history.csv",
        mime="text/csv",
    )
    st.download_button(
        label="Download trades (Excel)",
        data=dataframe_to_excel_bytes(trades, sheet_name="trades"),
        file_name="trade_history.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    latest_prices: Dict[str, float | None] = {}
    if latest_close is not None and ticker:
        latest_prices[ticker.upper()] = latest_close

    summary = manager.get_portfolio_summary(latest_prices=latest_prices)
    st.markdown("### Positions overview")
    st.dataframe(summary)

    if not summary.empty:
        total_value = summary["market_value"].replace({pd.NA: 0}).fillna(0).sum()
        total_unrealized = summary["unrealized_pl"].replace({pd.NA: 0}).fillna(0).sum()
        total_realized = summary["realized_pl"].replace({pd.NA: 0}).fillna(0).sum()

        col1, col2, col3 = st.columns(3)
        col1.metric("Portfolio market value", f"${total_value:,.2f}")
        col2.metric("Unrealized P&L", f"${total_unrealized:,.2f}")
        col3.metric("Realized P&L", f"${total_realized:,.2f}")


def main() -> None:
    st.title("Stock Market Analytics Dashboard — Real-Time Trading Insights")
    st.write(
        "Monitor live markets, run quick strategy experiments, and keep a simple log of"
        " your portfolio without leaving this page. Perfect for new traders exploring"
        " quantitative analysis."
    )

    with st.sidebar:
        st.header("Market data")
        ticker = st.text_input("Ticker symbol", value="AAPL").upper()
        period = st.selectbox(
            "History", options=["5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3
        )
        interval = st.selectbox(
            "Interval",
            options=["15m", "30m", "60m", "1d", "1wk"],
            index=3,
        )
        st.caption("Prices are retrieved from Yahoo Finance via the yfinance package.")

        with st.expander("Indicator settings", expanded=True):
            show_sma = st.checkbox("Show SMA", value=True)
            sma_window = st.slider("SMA window", min_value=5, max_value=200, value=20)
            show_ema = st.checkbox("Show EMA", value=True)
            ema_window = st.slider("EMA window", min_value=5, max_value=200, value=50)
            show_rsi = st.checkbox("Show RSI", value=True)
            show_macd = st.checkbox("Show MACD", value=True)
            rsi_period = st.slider("RSI period", min_value=5, max_value=50, value=14)

    if not ticker:
        st.info("Enter a ticker symbol to begin.")
        return

    try:
        price_data = load_price_data(ticker, period, interval)
    except ValueError as exc:
        st.error(str(exc))
        return
    except ConnectionError as exc:
        st.error(str(exc))
        return

    indicator_data = prepare_indicator_data(price_data, sma_window, ema_window, rsi_period)
    latest_close = float(indicator_data["Close"].iloc[-1]) if not indicator_data.empty else None

    render_market_overview(indicator_data, ticker)

    price_chart = build_price_chart(
        indicator_data,
        ticker=ticker,
        show_sma=show_sma,
        sma_window=sma_window,
        show_ema=show_ema,
        ema_window=ema_window,
    )
    st.plotly_chart(price_chart, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="Download prices (CSV)",
            data=dataframe_to_csv_bytes(indicator_data),
            file_name=f"{ticker}_prices.csv",
            mime="text/csv",
        )
    with col2:
        st.download_button(
            label="Download prices (Excel)",
            data=dataframe_to_excel_bytes(indicator_data, sheet_name="prices"),
            file_name=f"{ticker}_prices.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    if show_rsi:
        st.plotly_chart(build_rsi_chart(indicator_data), use_container_width=True)
    if show_macd:
        st.plotly_chart(build_macd_chart(indicator_data), use_container_width=True)

    render_backtest_section(price_data, ticker)

    st.markdown("---")
    render_portfolio_section(ticker, latest_close)


if __name__ == "__main__":
    main()
