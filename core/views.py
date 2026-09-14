from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .models import Request
from .forms import RequestForm, CommentForm, AttachmentForm
from .filters import RequestFilter
from .csv_export import export_requests_csv  # re-exported here so urls.py has one place to import views from


@login_required
def request_list(request):
    """
    The request list screen (§5.1). Every view in this file is wrapped
    in @login_required, since the spec (§5.5) says everything requires
    being logged in — this decorator redirects anyone not logged in to
    Django's default login page instead of showing the page.
    """
    filtered = RequestFilter(request.GET, queryset=Request.objects.all())
    return render(request, "core/request_list.html", {"filter": filtered})


@login_required
def request_create(request):
    """The create form (§5.3). On success, redirects to the new
    request's detail page rather than re-showing the form."""
    if request.method == "POST":
        form = RequestForm(request.POST)
        if form.is_valid():
            new_request = form.save(commit=False)
            new_request.requester = request.user
            # current_step defaults to DRAFT already, via the model —
            # nothing further happens here. Moving it to Submitted is a
            # TRANSITION, not part of creating it, so that goes through
            # perform_transition() later, not this view.
            new_request.save()
            return redirect("request_detail", pk=new_request.pk)
    else:
        form = RequestForm()

    return render(request, "core/request_form.html", {"form": form})


@login_required
def request_edit(request, pk):
    """Same form as create, but bound to an existing instance."""
    req = get_object_or_404(Request, pk=pk)

    if request.method == "POST":
        form = RequestForm(request.POST, instance=req)
        if form.is_valid():
            form.save()
            return redirect("request_detail", pk=req.pk)
    else:
        form = RequestForm(instance=req)

    return render(request, "core/request_form.html", {"form": form, "request_obj": req})


@login_required
def request_detail(request, pk):
    """
    The detail screen (§5.2): request info, checklist, comments,
    attachments, history. Also handles the comment-posting and
    file-upload forms on the same page, since they're simple enough not
    to need their own separate pages.

    NOTE: the buttons to actually MOVE this request forward (Submit,
    Approve, etc.) aren't built yet — those depend on perform_transition()
    having its user parameter added first. This view only covers
    viewing + commenting + attaching, which don't need that.
    """
    req = get_object_or_404(Request, pk=pk)

    comment_form = CommentForm()
    attachment_form = AttachmentForm()

    if request.method == "POST":
        if "submit_comment" in request.POST:
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.request = req
                comment.author = request.user
                comment.save()
                return redirect("request_detail", pk=req.pk)

        elif "submit_attachment" in request.POST:
            attachment_form = AttachmentForm(request.POST, request.FILES)
            if attachment_form.is_valid():
                attachment = attachment_form.save(commit=False)
                attachment.request = req
                attachment.uploaded_by = request.user
                attachment.save()
                return redirect("request_detail", pk=req.pk)

    return render(
        request,
        "core/request_detail.html",
        {
            "req": req,
            "comment_form": comment_form,
            "attachment_form": attachment_form,
        },
    )