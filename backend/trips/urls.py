from django.urls import path

from . import views

urlpatterns = [
    path("geocode/", views.geocode, name="geocode"),
    path("trips/", views.trip_list, name="trip-list"),
    path("trips/<uuid:trip_id>/", views.trip_detail, name="trip-detail"),
    path("trips/<uuid:trip_id>/heatmap/", views.trip_heatmap, name="trip-heatmap"),
    path("health/", views.health, name="health"),
]
