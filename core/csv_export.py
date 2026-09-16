import csv

from django.http import HttpResponse

from .filters import RequestFilter
from .models import Request


def export_requests_csv(request):
    """
    Exports the CURRENTLY FILTERED request list as a downloadable CSV
    (§5.1 — "a button to download the current filtered list as CSV").

    Reuses the exact same RequestFilter as the list page, so whatever
    the user has searched/filtered for on screen is exactly what gets
    exported — not the whole unfiltered table.
    """
    filtered = RequestFilter(request.GET, queryset=Request.objects.all())
    queryset = filtered.qs  # .qs applies all the filters and returns the resulting queryset

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="requests_export.csv"'

    writer = csv.writer(response)

    # Header row
    writer.writerow([
        "ID", "Partner Code", "Partner Name", "Service", "Direction",
        "Priority", "Current Step", "Target Date", "Actual Go-Live Date",
        "Requester", "Owner", "Created At",
    ])

    # One row per request
    for req in queryset.select_related("partner", "requester", "owner"):
        writer.writerow([
            req.id,
            req.partner.code,
            req.partner.name,
            req.get_service_display(),
            req.get_direction_display(),
            req.priority,
            req.get_current_step_display(),
            req.target_date,
            req.actual_go_live_date or "",
            req.requester.username,
            req.owner.username if req.owner else "",
            req.created_at.strftime("%Y-%m-%d %H:%M"),
        ])

    return response