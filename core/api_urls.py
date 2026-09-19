from django.urls import path

from .api_views import (
    RequestListCreateAPIView,
    RequestDetailAPIView,
)
from .api_views import (
    RequestListCreateAPIView,
    RequestDetailAPIView,
    RequestTransitionAPIView,
)

urlpatterns = [
    path("requests/", RequestListCreateAPIView.as_view(), name="api_request_list"),
    path("requests/<int:pk>/", RequestDetailAPIView.as_view(), name="api_request_detail"),
    path(
    "requests/<int:pk>/transition/",
    RequestTransitionAPIView.as_view(),
    name="api_request_transition",
),
]