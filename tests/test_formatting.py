from foliopulse.charts import format_chart_date_label
from foliopulse.formatting import format_compact_inr


def test_none_and_non_numbers_show_dash():
    assert format_compact_inr(None) == "-"
    assert format_compact_inr("abc") == "-"


def test_small_amounts_plain():
    assert format_compact_inr(500) == "₹500"
    assert format_compact_inr(1234567) == "₹12.35L"


def test_thousands_lakhs_crores():
    assert format_compact_inr(1500) == "₹1.5K"
    assert format_compact_inr(150000) == "₹1.50L"
    assert format_compact_inr(25000000) == "₹2.50Cr"


def test_negative_amounts_keep_sign():
    assert format_compact_inr(-1500) == "-₹1.5K"


def test_chart_date_label():
    assert format_chart_date_label("2026-10-15") == "15 Oct"
    assert format_chart_date_label("not-a-date") == "not-a-date"
