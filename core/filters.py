import django_filters
from django import forms

from .models import Request, STEP_CHOICES, SERVICE_CHOICES
from workflow.late_detection import is_late


# NOTE: the spec (§7) says "each step has a target number of days" but
# doesn't give the actual numbers anywhere in the brief. These are
# placeholder values so the "late only" filter below has something to
# compare against — replace with real numbers once your manager/spec
# confirms them, or once your teammate defines them in workflow/.
STEP_TARGET_DAYS = {
    "DRAFT": 2,
    "SUBMITTED": 1,
    "TESTING": 5,
    "APPROVAL": 3,
    "DEPLOYMENT": 3,
}


REGION_CHOICES = [
    ("EMEA", "EMEA"),
    ("APAC", "APAC"),
    ("AMER", "AMER"),
]


class RequestFilter(django_filters.FilterSet):
    """
    Powers the request list screen's search/filter bar (§5.1): search by
    partner name or code, filter by step, service, region, priority,
    owner, and a "late only" switch.
    """

    # Search box — matches partner name OR partner code, whichever hits.
    search = django_filters.CharFilter(
        method="filter_search",
        label="Search (partner name or code)",
    )

    step = django_filters.ChoiceFilter(
        field_name="current_step", choices=STEP_CHOICES
    )

    service = django_filters.ChoiceFilter(choices=SERVICE_CHOICES)

    region = django_filters.ChoiceFilter(
        field_name="partner__region", choices=REGION_CHOICES
    )

    priority = django_filters.CharFilter()

    owner = django_filters.ModelChoiceFilter(
        queryset=None  # set in __init__ below, needs the User model
    )

    late_only = django_filters.BooleanFilter(
        method="filter_late_only",
        label="Late only",
        widget=forms.CheckboxInput,
    )

    class Meta:
        model = Request
        fields = ["step", "service", "region", "priority", "owner"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth.models import User
        self.filters["owner"].queryset = User.objects.all()

    def filter_search(self, queryset, name, value):
        from django.db.models import Q
        return queryset.filter(
            Q(partner__name__icontains=value) | Q(partner__code__icontains=value)
        )

    def filter_late_only(self, queryset, name, value):
        if not value:
            return queryset

        # Late detection needs a per-row check (each request's own
        # step_entered_at against its own step's target), which isn't
        # something a normal database filter can express directly — so
        # this pulls matching IDs in Python instead of a single query.
        late_ids = [
            req.id
            for req in queryset
            if req.current_step in STEP_TARGET_DAYS
            and is_late(req.step_entered_at, STEP_TARGET_DAYS[req.current_step])
        ]
        return queryset.filter(id__in=late_ids)