# 📈 FolioPulse

**FolioPulse** is a lightweight, real-time stock portfolio tracker and visual risk-monitoring engine built with Python, Streamlit, Plotly, and Firebase. Designed specifically for Indian stock market investors and swing traders, FolioPulse offers live intraday P&L calculations, automated Zerodha expense/tax deductions, and interactive candlestick charts layered with risk levels (Stop-Loss, Trailing-SL, Targets).

---

## ✨ Key Features

* **⚡ Real-Time Price Engine & Gap-Fill:**
  * Live quote polling via `yfinance` with fast market status checking for Indian exchanges (NSE/BSE).
  * Automatic intraday gap-fill engine (5m tick aggregate) that seamlessly patches missing yesterday/today daily bars for high-cap stocks experiencing Yahoo Finance sync lag.

* **🎯 Interactive 10-Day Candlestick Risk Engine:**
  * Clean Plotly candlestick charts with overlaid Horizontal Risk Levels (**Stop-Loss, Trailing-SL, Buy Price, Target 1, Target 2, and Live LTP**).
  * **Net-Based Badge Callouts:** All callout badges compute exact **Net P&L** after deducting all broker levies, STT, and DP charges.
  * **Staggered Callout Placement:** Staggers LTP callout badges to the left and Target/SL badges to the right to eliminate visual overlap during price convergence.
  * **Highest Z-Index LTP Visuals:** Live LTP price lines and axis chips are rendered on top of the visual stack.

* **📊 Dual Table Display Presets:**
  * **`🔍 Main Focus View`:** A streamlined 7-column table designed for quick live scanning during market hours (`Symbol`, `Qty`, `Avg Buy`, `LTP`, `Day's Gain/Loss`, `Net P&L ₹`, `Net P&L %`).
  * **`📋 Full Detail View`:** A structured, 18-column table logically grouped into *User Inputs* $\rightarrow$ *Market Snapshot* $\rightarrow$ *Risk Parameters* $\rightarrow$ *Net Results*.

* **🧮 Precise Zerodha Expense Engine (`compute_trade_expenses_detailed`):**
  * Supports both **`DELIVERY`** and **`INTRADAY`** equity trades.
  * Factors in exact Zerodha brokerage, STT/CTT, Exchange Turnover Charges, Stamp Duty, SEBI turnover fees, 18% GST, and DP charges (₹15.34 per delivery sell transaction).

* **📥 Streamlined EOD Journal CSV Export:**
  * One-click download of daily position logs mapped to a clean 18-column schema, omitting hypothetical projections and redundant fee breakdowns for direct appending into master sheets.

* **☁️ Cloud Sync & Multi-User Auth:**
  * Firebase Firestore integration for seamless watchlist sync across devices.
  * Google OAuth login support for personalized portfolio state persistence.
  * Interactive Watchlist & Sequence Manager modal with drag-and-drop order adjustments and JSON export/import.

---

## 🏗️ Architecture & Project Structure

```text
foliopulse/
├── app.py                   # Main Streamlit application entry point
├── requirements.txt         # Dependencies (streamlit, yfinance, plotly, firebase-admin, etc.)
├── .streamlit/
│   └── secrets.toml         # Firebase Admin SDK credentials & app configuration
└── README.md                # Project documentation
```

## 🛠️ Installation & Setup
1. Prerequisites
   Python 3.10+

   A Firebase Project with Firestore enabled.

2. Clone Repository & Install Dependencies

    ```bash
    git clone [https://github.com/sachinksha/foliopulse.git](https://github.com/sachinksha/foliopulse.git)
    cd foliopulse

    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate

    pip install -r requirements.txt
    ```

3. Configure Environment Secrets
    Create a .streamlit/secrets.toml file in the root directory:

    ```Ini, TOML
    [firebase]
    type = "service_account"
    project_id = "your-firebase-project-id"
    private_key_id = "your-private-key-id"
    private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_KEY_HERE\n-----END PRIVATE KEY-----\n"
    client_email = "firebase-adminsdk-xxx@your-project.iam.gserviceaccount.com"
    client_id = "your-client-id"
    auth_uri = "[https://accounts.google.com/o/oauth2/auth](https://accounts.google.com/o/oauth2/auth)"
    token_uri = "[https://oauth2.googleapis.com/token](https://oauth2.googleapis.com/token)"
    ```

4. Run Application Locally

    ```bash
    streamlit run app.py
    ```

## 📊 Journal Master Sheet Schema & Excel Migration
When exporting daily logs via the 📥 Export EOD Journal button, the CSV follows this standardized 18-column schema:
| Col # | Column Name     | Source   | Description                           |
|-------|-----------------|----------|---------------------------------------|
| 1     | Date            | System   | Record Date (YYYY-MM-DD)              |
| 2     | Symbol          | User     | Stock Ticker (e.g., TITAN)            |
| 3     | Type            | User     | Trade Category (DELIVERY / INTRADAY)  |
| 4     | Qty             | User     | Quantity                              |
| 5     | Avg Buy (₹)     | User     | Average Entry Price                   |
| 6     | Invested (₹)    | Computed | = Qty × Avg Buy                       |
| 7     | LTP (₹)         | Market   | Live / Manual Price                   |
| 8     | Current Val (₹) | Computed | = Qty × LTP                           |
| 9     | Weight (%)      | Computed | = Invested / Total Portfolio Invested |
| 10    | STOP-LOSS       | User     | Stop-Loss Trigger Price               |
| 11    | TRAILING-SL     | User     | Trailing Stop-Loss Price              |
| 12    | TARGET 1        | User     | First Target Price                    |
| 13    | TARGET 2        | User     | Second Target Price                   |
| 14    | Expenses (₹)    | Computed | Total Zerodha Levies + DP Charges     |
| 15    | Gross P&L (₹)   | Computed | = Current Val - Invested              |
| 16    | Gross P&L (%)   | Computed | = Gross P&L / Invested                |
| 17    | Net P&L (₹)     | Computed | = Gross P&L - Expenses                |
| 18    | Net P&L (%)     | Computed | = Net P&L / Invested                  |

## Backfilling Old Records in Excel
To calculate Expenses (Column N) for older historical entries in Excel (where F2 = Invested, H2 = Current Val, C2 = Type):

```Excel
=IF(LOWER(C2)="intraday", MIN(20, F2*0.0003)+MIN(20, H2*0.0003)+ROUND(H2*0.00025, 0)+(F2*0.00003)+((F2+H2)*0.0000307)+((F2+H2)*0.000001)+0.18*(MIN(20, F2*0.0003)+MIN(20, H2*0.0003)+((F2+H2)*0.0000307)+((F2+H2)*0.000001)), 0.01+ROUND((F2+H2)*0.001, 0)+(F2*0.00015)+((F2+H2)*0.0000307)+((F2+H2)*0.000001)+0.18*(0.01+((F2+H2)*0.0000307)+((F2+H2)*0.000001))+15.34)
```