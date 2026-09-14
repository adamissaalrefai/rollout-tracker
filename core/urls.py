from django.urls import path

from . import views

urlpatterns = [
    path("", views.request_list, name="request_list"),
    path("new/", views.request_create, name="request_create"),
    path("<int:pk>/edit/", views.request_edit, name="request_edit"),
    path("<int:pk>/", views.request_detail, name="request_detail"),
    path("export/csv/", views.export_requests_csv, name="export_requests_csv"),
]