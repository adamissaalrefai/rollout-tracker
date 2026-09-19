from collections import defaultdict
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .models import Request
from workflow.history import HistoryEntry
from workflow.late_detection import is_late
from .filters import STEP_TARGET_DAYS


def get_step_counts():
    return dict(
        Request.objects.values("current_step")
        .annotate(count=Count("id"))
        .values_list("current_step", "count")
    )
    
def get_late_by_region():
    late_by_region = defaultdict(int)

    requests = Request.objects.select_related("partner")

    for req in requests:
        target_days = STEP_TARGET_DAYS.get(req.current_step)

        if target_days is None:
            continue

        if is_late(req.step_entered_at, target_days):
            late_by_region[req.partner.region] += 1

    return dict(late_by_region)

def get_average_days_by_step():
    step_durations = defaultdict(list)

    requests = Request.objects.all()

    for req in requests:
        step_changes = list(
            HistoryEntry.objects.filter(
                request=req,
                action="STEP_CHANGE",
            ).order_by("timestamp")
        )

        # The request starts in DRAFT when it is created.
        previous_time = req.created_at
        previous_step = "DRAFT"

        for change in step_changes:
            # The time between entering previous_step and leaving it.
            duration = change.timestamp - previous_time
            days = duration.total_seconds() / 86400
            step_durations[previous_step].append(days)

            previous_step = change.new_value
            previous_time = change.timestamp

        # The request's current step is still in progress.
        if req.current_step == previous_step:
            duration = timezone.now() - req.step_entered_at
            days = duration.total_seconds() / 86400
            step_durations[req.current_step].append(days)

    return {
        step: round(sum(durations) / len(durations), 2)
        for step, durations in step_durations.items()
        if durations
    }

def get_go_lives_by_month():
    go_lives = (
        Request.objects
        .filter(actual_go_live_date__isnull=False)
        .values("actual_go_live_date__year", "actual_go_live_date__month")
        .annotate(count=Count("id"))
        .order_by(
            "actual_go_live_date__year",
            "actual_go_live_date__month",
        )
    )

    return [
        {
            "month": f"{item['actual_go_live_date__year']}-"
                     f"{item['actual_go_live_date__month']:02d}",
            "count": item["count"],
        }
        for item in go_lives
    ]
    
def get_my_open_items(user):
    return (
        Request.objects
        .filter(owner=user)
        .exclude(current_step__in=["LIVE", "REJECTED"])
        .select_related("partner")
        .order_by("target_date")
    )