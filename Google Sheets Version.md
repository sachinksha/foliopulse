A Google Sheets implementation designed to replace your Streamlit app with native Google Finance data feeds, automated Zerodha expense logic, and visual risk alerts.

---

## 1. Portfolio Header (Summary KPI Cards)

Place these summary metrics at the top of your sheet (Rows 1 to 3) to mirror the app’s top header row:

| Cell | Label | Formula / Value |
| --- | --- | --- |
| **A2:B2** | **Total Invested** | `=SUM(E6:E100)` |
| **C2:D2** | **Current Value** | `=SUM(H6:H100)` |
| **E2:F2** | **Net P&L (₹)** | `=SUM(Q6:Q100)` |
| **G2:H2** | **Net Return (%)** | `=E2/A2` |
| **I2:J2** | **Day's Change (₹)** | `=SUM(I6:I100)` |

---

## 2. Main Portfolio Table Structure

Starting at **Row 5**, set up your table headers and copy these exact formulas down your stock rows (starting at Row 6):

### Table Schema & Formulas (Row 6 Example)

| Col | Column Name | Sample Value / Formula |
| --- | --- | --- |
| **A** | **Symbol** | `LT` *(or `TITAN`)* |
| **B** | **Type** | `DELIVERY` *(or `INTRADAY`)* |
| **C** | **Qty** | `10` |
| **D** | **Avg Buy (₹)** | `2400.00` |
| **E** | **Invested (₹)** | `=C6*D6` |
| **F** | **Live LTP (₹)** | `=GOOGLEFINANCE("NSE:"&A6, "price")` |
| **G** | **Prev Close (₹)** | `=GOOGLEFINANCE("NSE:"&A6, "closeyest")` |
| **H** | **Current Val (₹)** | `=C6*F6` |
| **I** | **Day's Gain (₹)** | `=(F6-G6)*C6` |
| **J** | **Day's Gain (%)** | `=IF(G6>0, (F6-G6)/G6, 0)` |
| **K** | **Stop Loss (₹)** | `2200.00` |
| **L** | **Trailing SL (₹)** | `2200.00` |
| **M** | **Target 1 (₹)** | `4800.00` |
| **N** | **Target 2 (₹)** | `4800.00` |
| **O** | **Expenses (₹)** | *(See Zerodha Expense Formula Below)* |
| **P** | **Gross P&L (₹)** | `=H6-E6` |
| **Q** | **Net P&L (₹)** | `=P6-O6` |
| **R** | **Net P&L (%)** | `=Q6/E6` |
| **S** | **Alert Status** | `=IF(F6<=K6, "🔴 SL HIT", IF(F6>=N6, "🟢 T2 HIT", IF(F6>=M6, "🟢 T1 HIT", "🟢 HOLD")))` |

---

## 3. Zerodha Expense Formula (Column O)

To mirror the exact Zerodha brokerage, STT, GST, Stamp Duty, and DP charges calculation, paste this formula into **Cell O6** and pull it down:

```excel
=LET(
  buy_turnover, E6,
  sell_turnover, H6,
  tot_turnover, buy_turnover + sell_turnover,
  is_intraday, (UPPER(B6)="INTRADAY"),
  
  brokerage, IF(is_intraday, MIN(20, buy_turnover*0.0003) + MIN(20, sell_turnover*0.0003), 0),
  stt, IF(is_intraday, ROUND(sell_turnover*0.00025), ROUND((buy_turnover + sell_turnover)*0.001)),
  stamp_duty, IF(is_intraday, buy_turnover*0.00003, buy_turnover*0.00015),
  exchange_fee, tot_turnover * 0.0000307,
  sebi_fee, tot_turnover * 0.000001,
  dp_charge, IF(is_intraday, 0, 15.34),
  gst, (brokerage + exchange_fee + sebi_fee) * 0.18,
  
  ROUND(brokerage + stt + stamp_duty + exchange_fee + sebi_fee + dp_charge + gst, 2)
)

```

---

## 4. Conditional Formatting Rules

Highlight gains, losses, and risk triggers automatically:

1. **Net P&L (Columns Q & R):**
* **Format Cells If:** *Greater than or equal to* `0` $\rightarrow$ **Fill:** Dark Green / **Text:** Light Green (`#00CC96`)
* **Format Cells If:** *Less than* `0` $\rightarrow$ **Fill:** Dark Red / **Text:** Light Red (`#FF2B2B`)


2. **Alert Status (Column S):**
* **Text contains:** `🔴 SL HIT` $\rightarrow$ **Fill:** Light Red / **Text:** Dark Red / **Bold**
* **Text contains:** `🟢 T1 HIT` or `🟢 T2 HIT` $\rightarrow$ **Fill:** Light Green / **Text:** Dark Green / **Bold**


3. **Live LTP (Column F):**
* **Format Cells If:** *Less than or equal to* `=K6` (Stop Loss) $\rightarrow$ **Text:** Red / **Bold**



---

## 5. Google Apps Script for Auto-Refresh (Optional)

By default, `=GOOGLEFINANCE()` updates every 2–20 minutes. To force a hard refresh of live prices every 1 minute without cloud IP blocking:

1. In Google Sheets, click **Extensions** $\rightarrow$ **Apps Script**.
2. Replace the code with the following snippet:

```javascript
function refreshGoogleFinance() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var range = sheet.getRange("F6:F100"); // Live LTP range
  var formulas = range.getFormulas();
  
  // Temporarily clear and restore formulas to force a fresh fetch
  range.clearContent();
  SpreadsheetApp.flush();
  range.setFormulas(formulas);
}

```

3. Click **Triggers (Clock icon)** on the left menu $\rightarrow$ **Add Trigger**:
* **Function to run:** `refreshGoogleFinance`
* **Select event source:** `Time-driven`
* **Select type of time based trigger:** `Minutes timer` $\rightarrow$ `Every minute`