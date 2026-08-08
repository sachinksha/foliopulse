import unittest
from expense_calculator import compute_trade_expenses_detailed


class TestExpenseCalculator(unittest.TestCase):
    def test_delivery_trade_expenses(self):
        result = compute_trade_expenses_detailed(qty=100, buy_price=100.0, sell_price=105.0, trade_type="DELIVERY")

        self.assertEqual(result["dp_charges"], 15.34)
        self.assertGreater(result["contract_note_charges"], 0.0)
        self.assertAlmostEqual(result["total_expenses"], result["contract_note_charges"] + result["dp_charges"], places=2)
        self.assertAlmostEqual(result["total_expenses"], 38.12, places=2)
        self.assertAlmostEqual(result["breakeven_price"], 100.0 + (result["total_expenses"] / 100), places=2)

    def test_intraday_trade_expenses(self):
        result = compute_trade_expenses_detailed(qty=100, buy_price=100.0, sell_price=105.0, trade_type="INTRADAY")

        self.assertEqual(result["dp_charges"], 0.0)
        self.assertGreater(result["contract_note_charges"], 0.0)
        self.assertAlmostEqual(result["total_expenses"], result["contract_note_charges"], places=2)
        self.assertAlmostEqual(result["breakeven_price"], 100.0 + (result["total_expenses"] / 100), places=2)


if __name__ == "__main__":
    unittest.main()
