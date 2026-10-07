"""--row (the job's ROWS) names one row, or a whole scenario."""
from pathlib import Path

from mobiletest.run import Row, row_wanted


def _row(platform, case_id, example):
    return Row(Path("features") / platform / "KEY", platform, "KEY", case_id, example, "name", Path("f.feature"), [])


def test_a_row_entry_names_one_row_or_a_whole_scenario():
    usd = _row("android", "buy-foreign-currency", "USD")
    eur = _row("ios", "buy-foreign-currency", "EUR")
    other = _row("android", "over-daily-limit", "USD-limit")
    assert row_wanted(usd, {"buy-foreign-currency#USD"}) and not row_wanted(eur, {"buy-foreign-currency#USD"})
    assert row_wanted(usd, {"android/buy-foreign-currency#USD"}) and not row_wanted(eur, {"android/buy-foreign-currency#USD"})
    assert row_wanted(usd, {"buy-foreign-currency"}) and row_wanted(eur, {"buy-foreign-currency"}) and not row_wanted(other, {"buy-foreign-currency"})
    assert row_wanted(eur, {"ios/buy-foreign-currency"}) and not row_wanted(usd, {"ios/buy-foreign-currency"})
