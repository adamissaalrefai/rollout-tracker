from django.contrib import admin
from .models import (
    Partner,
    Request,
    ChecklistTemplateItem,
    ChecklistItem,
    Comment,
    Attachment,
)


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "country", "region", "active")
    list_filter = ("region", "active")
    search_fields = ("code", "name")


@admin.register(ChecklistTemplateItem)
class ChecklistTemplateItemAdmin(admin.ModelAdmin):
    # This is the screen your manager described in §3: an admin can add or
    # change checklist templates here, with no developer touching code.
    list_display = ("service", "step", "label", "required", "order")
    list_filter = ("service", "step")
    ordering = ("service", "step", "order")


# Showing checklist items, comments, and attachments INSIDE the Request
# admin page (rather than as separate top-level lists) makes it much easier
# to look at one request and see everything tied to it at a glance.
class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 0


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "partner",
        "service",
        "current_step",
        "owner",
        "target_date",
        "version",
    )
    list_filter = ("current_step", "service", "direction")
    search_fields = ("partner__name", "partner__code")
    inlines = [ChecklistItemInline, CommentInline, AttachmentInline]

    # §4: "If someone types the URL directly, the app must still refuse
    # them" — that includes the Django admin. Without this, an admin
    # user could drag current_step to LIVE by hand, completely bypassing
    # perform_transition() and skipping every rule, role check, and
    # history entry. These fields can only change through the real
    # engine (or code that calls it) from here on.
    readonly_fields = ("current_step", "on_hold_from_step", "on_hold_reason", "version", "step_entered_at")


# Comment and Attachment are also registered on their own here, in case you
# ever need to browse/search them directly rather than through a Request.
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("request", "author", "timestamp")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("request", "file", "uploaded_by", "uploaded_at")