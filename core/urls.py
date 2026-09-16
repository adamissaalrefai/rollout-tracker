from django.urls import path

from . import views

urlpatterns = [
    path("", views.request_list, name="request_list"),
    path("new/", views.request_create, name="request_create"),
    path("<int:pk>/edit/", views.request_edit, name="request_edit"),
    path("<int:pk>/", views.request_detail, name="request_detail"),
    path("<int:pk>/transition/<str:target_step>/", views.request_transition, name="request_transition"),
    path("checklist-item/<int:pk>/update/", views.checklist_item_update, name="checklist_item_update"),
    path("import/csv/", views.request_csv_import, name="request_csv_import"),
    path("export/csv/", views.export_requests_csv, name="export_requests_csv"),
]