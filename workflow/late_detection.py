from datetime import date, timedelta


def working_days_between(start_date, end_date):
    """
    Counts working days (Mon-Fri) between two dates, skipping weekends.
    Public holidays are explicitly ignored per the spec.

    The spec's own edge case: Friday to Monday should count as 1 working
    day, not 3 — because only ONE working day (Monday) was actually
    crossed. This function counts FULL DAYS ELAPSED on the calendar,
    then subtracts the weekend days that fall within that range — it
    does NOT count the start_date itself as a day that has "passed".

    Examples:
        Friday -> the following Monday   = 1 working day
        Monday -> the following Tuesday  = 1 working day
        Monday -> the following Monday   = 5 working days (one full week)
        Same day -> same day             = 0 working days
    """
    if end_date < start_date:
        raise ValueError("end_date cannot be before start_date")

    total_days = (end_date - start_date).days
    working_days = 0

    for i in range(1, total_days + 1):
        current_day = start_date + timedelta(days=i)
        # Monday = 0 ... Sunday = 6
        if current_day.weekday() < 5:
            working_days += 1

    return working_days


def days_in_current_step(step_entered_at, now=None):
    """
    Convenience wrapper: given when a Request entered its current step,
    returns how many working days it's been sitting there, up to now.
    Pass `now` explicitly in tests to keep them deterministic; defaults
    to the real current time in production use.
    """
    from django.utils import timezone

    if now is None:
        now = timezone.now()

    return working_days_between(step_entered_at.date(), now.date())


def is_late(step_entered_at, target_days_for_step, now=None):
    """
    Returns True if a request has been sitting in its current step longer
    than the target number of working days allowed for that step.
    """
    days_spent = days_in_current_step(step_entered_at, now=now)
    return days_spent > target_days_for_step