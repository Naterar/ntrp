# Stock Market Analytics Dashboard

An easy-to-follow Streamlit project designed for new developers who want to explore
real-time market data, backtesting, and simple portfolio tracking in one place.

## Features

- **Live market data** – pull equities and futures quotes from Yahoo Finance with
  adjustable history and intervals.
- **Interactive charts** – Plotly candlesticks with optional moving averages, RSI,
  and MACD overlays.
- **Strategy backtesting** – simulate a moving-average crossover strategy and
  compare it to a buy-and-hold benchmark.
- **Portfolio tracker** – log trades into a lightweight SQLite database and view
  mark-to-market P&L.
- **Export tools** – download prices, backtest results, and trade history as CSV
  or Excel files for further analysis.

## Project structure

```
.
├── app.py                     # Streamlit application entry point
├── requirements.txt           # Python dependencies
└── stock_dashboard
    ├── __init__.py
    ├── backtesting.py         # Strategy simulator
    ├── data.py                # Market data helpers
    ├── indicators.py          # Technical indicator calculations
    └── portfolio.py           # SQLite-backed trade ledger
```

## Getting started

1. Create and activate a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Launch the Streamlit dashboard:

   ```bash
   streamlit run app.py
   ```

4. Streamlit will open a new browser tab. Use the sidebar to select a ticker, change the
   date range, and toggle indicators. The main page updates automatically.

## Working with the dashboard

### Market overview

- Choose a ticker (e.g., `AAPL`, `NQ=F`) and pick a history period plus interval.
- The headline metrics show the latest closing price, volume, and daily change.
- Download the displayed price data as CSV or Excel with a single click.

### Technical indicators

- Toggle simple or exponential moving averages to overlay on the candlestick chart.
- Enable the RSI and MACD panels to judge momentum and trend strength.
- Indicator look-back periods can be customised from the sidebar.

### Backtesting a moving-average crossover

- In the **Strategy Backtesting** section, choose fast/slow MA windows and click
  **Run backtest**.
- The dashboard compares the crossover strategy against buy-and-hold performance,
  highlighting total return, drawdown, Sharpe ratio, and win rate.
- Download the backtest equity curve and signal table as CSV or Excel for more
detailed analysis.

### Portfolio tracker

- Log trades using the **Add a trade** form. The tracker is geared toward long-only
  positions and stores data in `stock_dashboard/data/portfolio.db`.
- View the running trade ledger and portfolio summary, including realised and
  unrealised P&L. Trades can be exported just like the price data.
- Use the **Danger zone** expander to clear all stored trades if you want to start over.

## Notes & tips

- Yahoo Finance limits request rates; if data fails to load, wait a moment and try again.
- Futures symbols typically end with `=F` (e.g., `ES=F` for S&P 500 E-mini futures).
- The project is intentionally simple so you can extend it—try adding new indicators,
  risk metrics, or alternate data sources.
- For production use you should secure the SQLite database and add authentication.

Enjoy experimenting and building your market intuition!
