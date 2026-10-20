from __future__ import annotations

from datetime import date

from src.calendar import business_week, calendar_brief, first_business_days, next_business_week


def test_next_week_from_tuesday_is_monday_to_friday() -> None:
    tuesday = date(2026, 10, 20)
    assert tuesday.strftime("%A") == "Tuesday"

    this_monday, this_friday = business_week(tuesday)
    next_monday, next_friday = next_business_week(tuesday)
    two_start, two_end = first_business_days(next_monday, 2)

    assert (this_monday, this_friday) == (date(2026, 10, 19), date(2026, 10, 23))
    assert (next_monday, next_friday) == (date(2026, 10, 26), date(2026, 10, 30))
    assert (two_start, two_end) == (date(2026, 10, 26), date(2026, 10, 27))

    brief = calendar_brief(tuesday)
    assert "2026-10-26" in brief
    assert "2026-10-30" in brief
    assert "2026-10-27" in brief
    assert "This Friday is 2026-10-23" in brief
    assert "Next Friday is 2026-10-30" in brief
    assert "Public holidays are not excluded." in brief
