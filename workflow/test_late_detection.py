from datetime import date

import pytest

from workflow.late_detection import working_days_between, is_late


def test_same_day_is_zero_working_days():
    d = date(2026, 9, 14)  # a Monday
    assert working_days_between(d, d) == 0


def test_friday_to_monday_is_one_working_day():
    # This is the exact edge case called out in the spec (§7): going from
    # Friday to the following Monday must count as 1 working day, not 3,
    # since Saturday and Sunday aren't working days at all.
    friday = date(2026, 9, 11)
    monday = date(2026, 9, 14)
    assert working_days_between(friday, monday) == 1


def test_monday_to_tuesday_is_one_working_day():
    monday = date(2026, 9, 14)
    tuesday = date(2026, 9, 15)
    assert working_days_between(monday, tuesday) == 1


def test_monday_to_next_monday_is_five_working_days():
    monday = date(2026, 9, 14)
    next_monday = date(2026, 9, 21)
    assert working_days_between(monday, next_monday) == 5


def test_saturday_to_sunday_is_zero_working_days():
    saturday = date(2026, 9, 19)
    sunday = date(2026, 9, 20)
    assert working_days_between(saturday, sunday) == 0


def test_end_date_before_start_date_raises_error():
    start = date(2026, 9, 14)
    end = date(2026, 9, 10)
    with pytest.raises(ValueError):
        working_days_between(start, end)


def test_is_late_true_when_over_target():
    from datetime import datetime, timezone as dt_timezone

    step_entered_at = datetime(2026, 9, 11, 9, 0, tzinfo=dt_timezone.utc)  # Friday
    now = datetime(2026, 9, 16, 9, 0, tzinfo=dt_timezone.utc)  # following Wednesday
    assert is_late(step_entered_at, target_days_for_step=2, now=now) is True


def test_is_late_false_when_within_target():
    from datetime import datetime, timezone as dt_timezone

    step_entered_at = datetime(2026, 9, 14, 9, 0, tzinfo=dt_timezone.utc)  # Monday
    now = datetime(2026, 9, 15, 9, 0, tzinfo=dt_timezone.utc)  # Tuesday
    assert is_late(step_entered_at, target_days_for_step=2, now=now) is False