# 📈 FolioPulse — Live Portfolio & Risk Monitor

**FolioPulse** is a real-time portfolio tracking and visual risk management dashboard designed for Indian stock market traders and investors (NSE/BSE). Built with **Streamlit**, **Plotly**, and **yfinance**, it combines live P&L analytics with interactive 10-day candlestick charts that feature overlaid entry, stop-loss, and profit target levels.

App is live, go to - https://foliopulse.streamlit.app/
---

## ✨ Key Features

* **💼 Live P&L & Portfolio Analytics:** Real-time tracking of invested capital, current market value, individual & net P&L ($\text{₹}$ and $\%$), asset weights, and profit summaries.
* **📊 TradingView-Style 10-Day Candlestick Charts:** Native OHLC daily candlestick charts for every stock in your watchlist with zero clipped borders.
* **🎯 Visualized Risk & Target Levels:**
* **Buy Price (`BUY`):** Floating badge displaying live position quantity and active P&L ($\text{₹}$ and $\%$).
* **Targets (`TARGET 1` / `TARGET 2`):** Projected profit target lines with potential P&L calculations ($\text{₹}$ and $\%$) if hit.
* **Stop Losses (`SL` / `TSL`):** Color-coded risk bounds displaying maximum potential loss ($\text{₹}$ and $\%$). Auto-deduplicates if SL and Trailing SL are identical.
* **Live Price (`LTP`):** High-visibility red reference line with a right Y-axis price tag. Features **relative horizontal offset** so the LTP label never gets hidden under adjacent stop-loss or target badges.


* **🛠️ Modal Watchlist & Script Manager (`@st.dialog`):**
* **Single-Row Inline Editing:** Edit any script row in-place Excel-style via the **✏️ Pencil** icon, complete with **💾 Save** and **❌ Cancel** controls.
* **⣿ Reorder Controls:** Move scripts up and down using grabber controls to customize both table sequence and chart layout order.
* **🔍 Auto-Complete Search:** Powered by `yfinance.Search` to search and add stocks by ticker or company name with full exchange descriptions (e.g., `TATA CONSULTANCY SERV (TCS.NS) — NSE`).
* **📥 Download / 📤 Upload Config:** Export your portfolio configuration as a JSON file or restore a saved `config.json` directly through the modal interface.


* **🧠 Smart Auto-Pause & Manual Override:**
* **Market-Hours Engine:** Auto-detects NSE trading hours (09:15 AM – 03:30 PM IST), weekends, and official trading holidays to pause API polling when markets are closed.
* **Master Manual Override Toggle:** Switch ON manual override to completely pause API calls and force the dashboard to use user-fed prices. Auto-prefills inputs with the latest API prices when active.



---

## 🚀 Quick Start Guide

### 1. Prerequisites

Ensure you have Python **3.9+** installed.

### 2. Installation

Clone the repository and install the dependencies:

```bash
# Clone repository
git clone https://github.com/your-username/foliopulse.git
cd foliopulse

# Install required dependencies
pip install streamlit pandas plotly yfinance pytz streamlit-autorefresh

```

### 3. Launch the Application

Run the Streamlit application locally:

```bash
streamlit run app.py

```

The app will open automatically in your browser at `http://localhost:8501`.

---

## ⚙️ Configuration File (`config.json`)

On the first run, FolioPulse automatically creates a `config.json` file in your root folder. You can edit your portfolio via the **Sidebar ⚙️ -> Manage Watchlist & Reorder** popup or edit `config.json` manually:

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
      "manual_ltp": 3450.00
    }
  ]
}

```

> **NSE Ticker Format:** Append `.NS` to symbols traded on the National Stock Exchange of India (e.g., `RELIANCE.NS`, `TCS.NS`, `INFY.NS`).

---

## 🎨 Chart Color & Level Reference

| Reference Level | Line Style | Color Code | Badge Content & Logic |
| --- | --- | --- | --- |
| **Buy Price (`BUY`)** | Solid (`—`) | 🔵 `#1F77B4` | Live position Qty and P&L ($\text{₹}$ / $\%$) |
| **Last Traded Price (`LTP`)** | Dotted (`····`) | 🔴 `#FF0000` | Right-offset label to prevent overlap |
| **Stop Loss (`SL`)** | Dashed (`--`) | 🟠 `#FF872B` | Risk level with potential loss ($\text{₹}$ / $\%$) |
| **Trailing SL (`TSL`)** | Dashed (`--`) | 🟡 `#77671F` | Trailing stop level (Hidden if equal to SL) |
| **Target 1** | Dashed (`--`) | 🟢 `#00CC96` | Primary target with projected P&L ($\text{₹}$ / $\%$) |
| **Target 2** | Dashed (`--`) | 🟢 `#00FF7F` | Secondary target with projected P&L ($\text{₹}$ / $\%$) |