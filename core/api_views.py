from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Request
from .serializers import RequestSerializer
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from .filters import RequestFilter

from workflow.engine import perform_transition


class RequestListCreateAPIView(generics.ListCreateAPIView):
    queryset = Request.objects.select_related(
        "partner",
        "requester",
        "owner",
    ).all()
    serializer_class = RequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = RequestFilter


class RequestDetailAPIView(generics.RetrieveUpdateAPIView):
    queryset = Request.objects.select_related(
        "partner",
        "requester",
        "owner",
    ).all()
    serializer_class = RequestSerializer
    permission_classes = [IsAuthenticated]

class RequestTransitionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            rollout_request = Request.objects.get(pk=pk)
        except Request.DoesNotExist:
            return Response(
                {"detail": "Request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        target_step = request.data.get("target_step")
        reason = request.data.get("reason")
        expected_version = request.data.get("expected_version")

        if not target_step:
            return Response(
                {"detail": "target_step is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            updated_request = perform_transition(
                request=rollout_request,
                target_step=target_step,
                actor=request.user,
                reason=reason,
                expected_version=expected_version,
            )
        except Exception as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            RequestSerializer(updated_request).data,
            status=status.HTTP_200_OK,
        )