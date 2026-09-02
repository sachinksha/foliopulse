import unittest
from expense_calculator import compute_trade_expenses_detailed, price_for_target_net_pnl_pct


class TestExpenseCalculator(unittest.TestCase):
    def test_delivery_trade_expenses(self):
        res = compute_trade_expenses_detailed(100, 100.0, 105.0, "DELIVERY")
        self.assertEqual(res["dp_charges"], 15.34)

    def test_intraday_trade_expenses(self):
        result = compute_trade_expenses_detailed(qty=100, buy_price=100.0, sell_price=105.0, trade_type="INTRADAY")

        self.assertEqual(result["dp_charges"], 0.0)
        self.assertGreater(result["contract_note_charges"], 0.0)
        self.assertAlmostEqual(result["total_expenses"], result["contract_note_charges"], places=2)
        self.assertAlmostEqual(result["breakeven_price"], 100.0 + (result["total_expenses"] / 100), places=2)


class TestPriceForTargetNetPnlPct(unittest.TestCase):
    def test_zero_target_matches_breakeven_price_delivery(self):
        breakeven = compute_trade_expenses_detailed(100, 100.0, 100.0, "DELIVERY")["breakeven_price"]
        price = price_for_target_net_pnl_pct(100, 100.0, target_pct=0, trade_type="DELIVERY")
        self.assertAlmostEqual(price, breakeven, places=2)
        self.assertAlmostEqual(price, 100.37, places=2)

    def test_zero_target_matches_breakeven_price_intraday(self):
        breakeven = compute_trade_expenses_detailed(qty=100, buy_price=100.0, sell_price=100.0, trade_type="INTRADAY")["breakeven_price"]
        price = price_for_target_net_pnl_pct(qty=100, buy_price=100.0, target_pct=0, trade_type="INTRADAY")
        self.assertEqual(price, breakeven)
        self.assertEqual(price, 100.11)

    def test_stop_loss_2pct_delivery(self):
        price = price_for_target_net_pnl_pct(100, 100.0, target_pct=-2, trade_type="DELIVERY")
        self.assertAlmostEqual(price, 98.37, places=2)

    def test_target_5pct_delivery(self):
        price = price_for_target_net_pnl_pct(100, 100.0, target_pct=5, trade_type="DELIVERY")
        self.assertAlmostEqual(price, 105.38, places=2)

    def test_stop_loss_2pct_intraday(self):
        price = price_for_target_net_pnl_pct(qty=100, buy_price=100.0, target_pct=-2, trade_type="INTRADAY")
        self.assertEqual(price, 98.1)
        self.assertLess(price, 100.0)

    def test_target_5pct_intraday(self):
        price = price_for_target_net_pnl_pct(qty=100, buy_price=100.0, target_pct=5, trade_type="INTRADAY")
        self.assertEqual(price, 105.11)
        self.assertGreater(price, 100.0)

    def test_invalid_inputs_fall_back_to_buy_price(self):
        self.assertEqual(price_for_target_net_pnl_pct(qty=0, buy_price=100.0, target_pct=-2), 100.0)
        self.assertEqual(price_for_target_net_pnl_pct(qty=100, buy_price=0, target_pct=-2), 0.0)


if __name__ == "__main__":
    unittest.main()
