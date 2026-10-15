from django.contrib import admin

from .models import Checkpoint, Route, Trip


class RouteInline(admin.TabularInline):
    model = Route
    extra = 0
    fields = ["label", "rank", "is_recommended", "distance_mi", "duration_s", "avg_risk", "max_level", "summary"]
    readonly_fields = fields
    show_change_link = True


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ["__str__", "user", "load_weight_lb", "sample_interval_mi", "recommendation_safe", "created_at"]
    list_filter = ["recommendation_safe", "sample_interval_mi"]
    search_fields = ["origin_label", "destination_label", "user__username"]
    inlines = [RouteInline]


class CheckpointInline(admin.TabularInline):
    model = Checkpoint
    extra = 0
    fields = ["seq", "mile", "eta", "wind_mph", "rain_in_hr", "snow_in_hr", "risk_level", "reasons"]
    readonly_fields = fields


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ["__str__", "rank", "is_recommended", "distance_mi", "avg_risk", "max_level"]
    inlines = [CheckpointInline]
