from rest_framework import serializers

from .models import Request


class RequestSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source="partner.name", read_only=True)
    requester_username = serializers.CharField(
        source="requester.username",
        read_only=True,
    )
    owner_username = serializers.CharField(
        source="owner.username",
        read_only=True,
    )

    class Meta:
        model = Request
        fields = [
            "id",
            "partner",
            "partner_name",
            "service",
            "direction",
            "priority",
            "target_date",
            "actual_go_live_date",
            "requester",
            "requester_username",
            "owner",
            "owner_username",
            "current_step",
            "description",
            "version",
            "on_hold_from_step",
            "on_hold_reason",
            "step_entered_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "version",
            "step_entered_at",
            "created_at",
            "updated_at",
        ]