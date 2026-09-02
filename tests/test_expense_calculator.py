import unittest
from expense_calculator import compute_trade_expenses_detailed

class TestExpenseCalculatorSync(unittest.TestCase):
    def test_delivery_trade_asianpaint(self):
        res = compute_trade_expenses_detailed(270, 2857.56, 2695.02, "DELIVERY")
        self.assertEqual(res["brokerage"], 0.0)
        self.assertEqual(res["stamp_duty"], 116.0)
        self.assertEqual(res["stt"], 1500.0)
        self.assertEqual(res["dp_charges"], 15.34)
        self.assertAlmostEqual(res["total_expenses"], 1687.42, places=2)
        self.assertAlmostEqual(res["net_pnl"], -45573.22, places=2)
        # Verify whole integer display rounding for main table
        self.assertEqual(round(res["net_pnl"]), -45573)

    def test_intraday_trade_tvsmotor(self):
        # Qty: 339, Buy: 4255.00, Sell: 4321.00 (Intraday)
        res = compute_trade_expenses_detailed(339, 4255.0, 4321.0, "INTRADAY")
        self.assertEqual(res["brokerage"], 40.0)
        self.assertEqual(res["stamp_duty"], 43.0)
        self.assertEqual(res["stt"], 366.0)
        self.assertEqual(res["dp_charges"], 0.0)
        self.assertEqual(res["total_expenses"], 564.95)
        self.assertEqual(res["gross_pnl"], 22374.0)
        self.assertEqual(res["net_pnl"], 21809.05)
        self.assertEqual(res["breakeven_price"], 4256.65)

    def test_zero_quantity(self):
        res = compute_trade_expenses_detailed(0, 100.0, 105.0, "DELIVERY")
        self.assertEqual(res["total_expenses"], 0.0)
        self.assertEqual(res["breakeven_price"], 100.0)


if __name__ == "__main__":
    unittest.main()