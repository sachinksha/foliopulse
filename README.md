# 📈 FolioPulse — Live Portfolio & Risk Monitor

**FolioPulse** is a real-time portfolio management and visual risk monitoring dashboard designed specifically for Indian stock market traders and investors (NSE/BSE). Built with **Streamlit**, **Plotly**, and **yfinance**, it provides real-time P&L tracking alongside TradingView-style 10-day candlestick charts with overlaid entry, target, and stop-loss levels.

---

## ✨ Features

* **💼 Live P&L & Portfolio Analytics:** Real-time tracking of invested value, current market value, individual & net P&L ($\text{₹}$ and $\%$), position weights, and target returns.
* **📊 TradingView-Style 10-Day Candlestick Charts:** Interactive 10-day daily OHLC candlestick charts for every asset in your watchlist.
* **🎯 Visualized Risk Levels:**
* **Buy Price (`BUY`):** Features a center floating badge with live quantity and position P&L ($\text{₹}$ and $\%$).
* **Stop Loss (`SL`) & Trailing SL (`TSL`):** Color-coded dashed risk bounds (auto-deduplicates if SL and TSL are equal).
* **Targets (`Target 1` & `Target 2`):** Bright target reference lines.
* **Live Price (`LTP`):** Prominent red reference line and right Y-axis price tag.


* **🧠 Smart Auto-Pause Engine:** Automatically detects NSE market hours (09:15 AM – 03:30 PM IST), weekends, and official trading holidays to pause polling when the market is closed to conserve API bandwidth.
* **🔍 Dynamic Auto-Zoom:** Seamlessly toggles chart scale between the active risk zone ($\text{SL} \rightarrow \text{Target 2}$) and full price bounds.
* **🛠️ Sidebar Management:** Dedicated collapsible sidebar for manual LTP price overrides (during API outages) and JSON watchlist editing.

---

## 🚀 Quick Start Guide

### 1. Prerequisites

Ensure you have Python **3.9+** installed on your machine.

### 2. Installation

Clone the repository and install the required dependencies:

```bash
# Clone the repository
git clone https://github.com/your-username/foliopulse.git
cd foliopulse

# Install dependencies
pip install streamlit pandas plotly yfinance pytz streamlit-autorefresh

```

### 3. Run the App

Launch the dashboard locally using Streamlit:

```bash
streamlit run app.py

```

The application will launch automatically in your browser at `http://localhost:8501`.

---

## ⚙️ Configuration & Watchlist Setup

On the first launch, the app auto-generates a `config.json` file in the root directory. You can edit your portfolio directly via the **Sidebar ⚙️ -> Watchlist JSON Editor** or by modifying `config.json` manually:

```json
{
  "refresh_seconds": 10,
  "watchlist": [
    {
      "symbol": "TITAN.NS",
      "avg_buy_price": 3400.00,
      "quantity": 15,
      "stop_loss": 3200.00,
      "trailing_sl": 3300.00,
      "target_1": 3700.00,
      "target_2": 3900.00,
      "manual_ltp": 0.0
    }
  ]
}

```

> **Note on Ticker Symbols:** For Indian National Stock Exchange (NSE) stocks, append `.NS` to the symbol (e.g., `RELIANCE.NS`, `TCS.NS`, `HDFCBANK.NS`).

---

## 🎨 Chart Color Legend

| Level | Line Style | Color | Description |
| --- | --- | --- | --- |
| **Buy Avg** | Solid (`—`) | 🔵 `#1F77B4` | Average purchase price with live Qty/P&L badge |
| **LTP** | Dotted (`····`) | 🔴 `#FF0000` | Current Last Traded Price |
| **Stop Loss (SL)** | Dashed (`--`) | 🟠 `#FF872B` | Hard Stop Loss |
| **Trailing SL (TSL)** | Dashed (`--`) | 🟡 `#77671F` | Trailing Stop Loss |
| **Target 1** | Dashed (`--`) | 🟢 `#00CC96` | Primary Profit Target |
| **Target 2** | Dashed (`--`) | 🟢 `#00FF7F` | Secondary Profit Target |