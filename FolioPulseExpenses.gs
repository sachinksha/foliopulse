/**
 * ============================================================================
 * FOLIOPULSE EXPENSE ENGINE — single source of truth for expense math in
 * this spreadsheet.
 * ============================================================================
 *
 * This mirrors `expense_calculator.py` (compute_trade_expenses_detailed) from
 * the FolioPulse app line-for-line, so numbers in this sheet always agree
 * with numbers the app would show for the same qty/buy/sell/type.
 *
 * WHY ONE FUNCTION: every column that needs an expense number — HM Logs
 * "Expenses (₹)", TradesExit "Contract Note Charges" / "DP Charges" /
 * "Total Expenses" — calls the same FOLIOPULSE_EXPENSES() custom function
 * below. The math itself lives in exactly one place (foliopulseComputeExpenses_).
 * If Zerodha's charge structure ever changes, edit the CONFIG objects once
 * and every cell in every sheet that uses this function recalculates
 * correctly.
 *
 * HOW TO INSTALL:
 *   1. In your Google Sheet: Extensions → Apps Script.
 *   2. Paste this whole file in (or add it as a new .gs file in the project).
 *   3. Save. No deployment needed — custom functions are available in the
 *      sheet immediately.
 *
 * USAGE (see the bottom of this file for exact per-column formulas):
 *   =FOLIOPULSE_EXPENSES(qty, buyPrice, sellPrice, tradeType)              -> Total Expenses (₹)
 *   =FOLIOPULSE_EXPENSES(qty, buyPrice, sellPrice, tradeType, "CONTRACT")  -> Contract Note Charges (₹)
 *   =FOLIOPULSE_EXPENSES(qty, buyPrice, sellPrice, tradeType, "DP")        -> DP Charges (₹)
 *   =FOLIOPULSE_EXPENSES(qty, buyPrice, sellPrice, tradeType, "BREAKEVEN") -> Break-even price (₹)
 *
 * If you ever change expense_calculator.py, mirror the change here too —
 * these two files are meant to always match. foliopulseSelfTest_() at the
 * bottom re-checks the same two cases as tests/test_compute_trade_expenses.py;
 * run it from the Apps Script editor (select it in the function dropdown,
 * click Run) any time you touch the CONFIG values or the math below, and
 * check the log output.
 */

// ---------------------------------------------------------------------------
// Charge schedule — one object per trade type. Keep these in sync with
// DELIVERY_CONFIG / INTRADAY_CONFIG in expense_calculator.py.
// ---------------------------------------------------------------------------

var FOLIOPULSE_DELIVERY_CONFIG_ = {
  brokerageFlat: 0.01,        // ₹0.01 flat, charged on the buy leg only
  brokeragePercentage: 0,     // delivery brokerage isn't percentage-based
  brokerageMax: 0,
  sttPercentage: 0.001,       // STT: 0.1%, charged on BOTH legs for delivery
  txnChargePercentage: 0.0000307,  // NSE exchange transaction charge, both legs
  sebiChargePercentage: 0.000001,  // SEBI turnover fee, both legs
  stampDutyPercentage: 0.00015,    // stamp duty, buy leg only
  gstPercentage: 0.18,             // 18% GST on (brokerage + txn + sebi)
  dpCharge: 15.34              // flat DP charge, sell leg only, GST-inclusive
};

var FOLIOPULSE_INTRADAY_CONFIG_ = {
  brokerageFlat: 0,
  brokeragePercentage: 0.0003,  // 0.03%, capped at brokerageMax, both legs
  brokerageMax: 20,             // ₹20 cap per leg
  sttPercentage: 0.00025,       // STT: 0.025%, SELL leg only for intraday
  txnChargePercentage: 0.0000307,
  sebiChargePercentage: 0.000001,
  stampDutyPercentage: 0.00003, // stamp duty, buy leg only
  gstPercentage: 0.18,
  dpCharge: 0                   // no DP charge on intraday
};

// ---------------------------------------------------------------------------
// Private helpers (trailing underscore keeps them out of the formula
// autocomplete / not usable as cell functions — internal only).
// ---------------------------------------------------------------------------

/** Round-half-up to the nearest whole rupee. Mirrors Python's math.floor(v + 0.5). */
function foliopulseRoundNearestRupee_(value) {
  return Math.floor(value + 0.5);
}

/** Round to 2 decimals, nudged by a tiny epsilon to dodge float-precision edge cases. */
function foliopulseRoundTwoDecimals_(value) {
  return Math.round((value + 1e-9) * 100) / 100;
}

/**
 * Charges for a single leg (the buy side or the sell side) of a trade.
 * `value` is turnover for that leg (qty * price for that leg).
 */
function foliopulseLegExpenses_(value, config, isBuy, isIntraday) {
  var brokerage;
  if (isIntraday) {
    brokerage = Math.min(config.brokerageMax, value * config.brokeragePercentage);
  } else {
    brokerage = isBuy ? config.brokerageFlat : 0;
  }

  var stampDuty = isBuy ? foliopulseRoundNearestRupee_(value * config.stampDutyPercentage) : 0;
  var sebi = value * config.sebiChargePercentage;

  var stt;
  if (isIntraday) {
    stt = !isBuy ? foliopulseRoundNearestRupee_(value * config.sttPercentage) : 0;
  } else {
    stt = foliopulseRoundNearestRupee_(value * config.sttPercentage); // delivery: both legs
  }

  var txn = value * config.txnChargePercentage;
  var gst = (brokerage + txn + sebi) * config.gstPercentage; // GST applies to brokerage + txn + sebi only

  return brokerage + stampDuty + sebi + stt + txn + gst;
}

/**
 * Core calculation — the one place the actual math lives. Returns all four
 * derived numbers so every column can pull from the same computation.
 */
function foliopulseComputeExpenses_(qty, buyPrice, sellPrice, tradeType) {
  qty = Number(qty);
  buyPrice = Number(buyPrice);
  sellPrice = Number(sellPrice);

  if (!(qty > 0) || !(buyPrice > 0)) {
    return {
      contractNoteCharges: 0,
      dpCharges: 0,
      totalExpenses: 0,
      breakevenPrice: foliopulseRoundTwoDecimals_(buyPrice || 0)
    };
  }

  var type = (tradeType || '').toString().toUpperCase().trim();
  var isIntraday = (type === 'INTRADAY');
  var config = isIntraday ? FOLIOPULSE_INTRADAY_CONFIG_ : FOLIOPULSE_DELIVERY_CONFIG_;

  var buyValue = qty * buyPrice;
  var sellValue = qty * sellPrice;

  var buyExpenses = foliopulseLegExpenses_(buyValue, config, true, isIntraday);
  var sellExpenses = foliopulseLegExpenses_(sellValue, config, false, isIntraday);

  var contractNoteCharges = buyExpenses + sellExpenses;
  var dpCharges = isIntraday ? 0 : config.dpCharge;
  var totalExpenses = contractNoteCharges + dpCharges;
  var breakevenPrice = buyPrice + (totalExpenses / qty);

  return {
    contractNoteCharges: foliopulseRoundTwoDecimals_(contractNoteCharges),
    dpCharges: foliopulseRoundTwoDecimals_(dpCharges),
    totalExpenses: foliopulseRoundTwoDecimals_(totalExpenses),
    breakevenPrice: foliopulseRoundTwoDecimals_(breakevenPrice)
  };
}

// ---------------------------------------------------------------------------
// PUBLIC — the one function every sheet formula calls.
// ---------------------------------------------------------------------------

/**
 * Zerodha-style expense calculation, matching FolioPulse's
 * compute_trade_expenses_detailed exactly. One function, reused across every
 * sheet and column that needs an expense figure.
 *
 * @param {number} qty Quantity / shares traded.
 * @param {number} buyPrice Buy price (or Avg Buy) per share, in ₹.
 * @param {number} sellPrice Sell price — or current LTP for an open/unrealised position — per share, in ₹.
 * @param {string} tradeType "DELIVERY" or "INTRADAY" (case-insensitive).
 * @param {string} [metric] Which figure to return: "TOTAL" (default), "CONTRACT", "DP", or "BREAKEVEN".
 * @return {number} The requested expense figure, in ₹.
 * @customfunction
 */
function FOLIOPULSE_EXPENSES(qty, buyPrice, sellPrice, tradeType, metric) {
  var r = foliopulseComputeExpenses_(qty, buyPrice, sellPrice, tradeType);
  var m = (metric || 'TOTAL').toString().toUpperCase().trim();

  switch (m) {
    case 'CONTRACT':
    case 'CONTRACT_NOTE':
    case 'CONTRACT_CHARGES':
      return r.contractNoteCharges;
    case 'DP':
    case 'DP_CHARGES':
      return r.dpCharges;
    case 'BREAKEVEN':
    case 'BREAKEVEN_PRICE':
      return r.breakevenPrice;
    case 'TOTAL':
    default:
      return r.totalExpenses;
  }
}

// ---------------------------------------------------------------------------
// FORMULAS TO PASTE IN THE SHEET (row 2 shown — fill down as usual)
// ---------------------------------------------------------------------------
//
// HM Logs (Qty=D, Avg Buy=E, LTP=G, Type=C):
//   N2  Expenses (₹)          =FOLIOPULSE_EXPENSES(D2, E2, G2, C2)
//
// TradesExit (Qty=F, Buy Price=D, Sell Price=E, Trade Type=C):
//   I2  Contract Note Charges =FOLIOPULSE_EXPENSES(F2, D2, E2, C2, "CONTRACT")
//   J2  DP Charges            =FOLIOPULSE_EXPENSES(F2, D2, E2, C2, "DP")
//   K2  Total Expenses        =I2+J2
//        (equivalent to =FOLIOPULSE_EXPENSES(F2,D2,E2,C2,"TOTAL") by construction —
//         I2+J2 is simpler and avoids a third recomputation)
//   L2  Break-Even Sell Price =FOLIOPULSE_EXPENSES(F2, D2, E2, C2, "BREAKEVEN")
//        (optional — replaces the old =ROUND(D2+(K2/F2),2) formula so
//         break-even also comes from the same source-of-truth function)

// ---------------------------------------------------------------------------
// Optional sanity check — run this manually from the Apps Script editor
// (pick foliopulseSelfTest_ in the function dropdown, click Run, check
// View → Logs) any time you edit the CONFIG values or the math above.
// Mirrors tests/test_compute_trade_expenses.py.
// ---------------------------------------------------------------------------
function foliopulseSelfTest_() {
  var delivery = foliopulseComputeExpenses_(100, 100.0, 105.0, 'DELIVERY');
  var intraday = foliopulseComputeExpenses_(100, 100.0, 105.0, 'INTRADAY');

  Logger.log('DELIVERY 100@100->105: %s (expect dp=15.34, total=38.12)', JSON.stringify(delivery));
  Logger.log('INTRADAY 100@100->105: %s (expect dp=0, total=contract)', JSON.stringify(intraday));

  if (Math.abs(delivery.dpCharges - 15.34) > 1e-9) throw new Error('DELIVERY dp_charges mismatch');
  if (Math.abs(delivery.totalExpenses - 38.12) > 1e-9) throw new Error('DELIVERY total_expenses mismatch');
  if (intraday.dpCharges !== 0) throw new Error('INTRADAY dp_charges should be 0');
  if (Math.abs(intraday.totalExpenses - intraday.contractNoteCharges) > 1e-9) throw new Error('INTRADAY total should equal contract charges');

  Logger.log('foliopulseSelfTest_ passed.');
}