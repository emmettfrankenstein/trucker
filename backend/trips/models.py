import uuid

from django.conf import settings
from django.db import models


class RiskLevel(models.IntegerChoices):
    LOW = 0, "Low"
    MODERATE = 1, "Moderate"
    HIGH = 2, "High"
    SEVERE = 3, "Severe"
    NO_TRAVEL = 4, "No Travel"


class Trip(models.Model):
    class SampleInterval(models.IntegerChoices):
        TEN = 10, "10 miles"
        TWENTY_FIVE = 25, "25 miles"
        FIFTY = 50, "50 miles"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="trips"
    )
    origin_label = models.CharField(max_length=255)
    origin_lat = models.FloatField()
    origin_lon = models.FloatField()
    destination_label = models.CharField(max_length=255)
    destination_lat = models.FloatField()
    destination_lon = models.FloatField()
    departure_at = models.DateTimeField()
    load_weight_lb = models.PositiveIntegerField()
    sample_interval_mi = models.PositiveSmallIntegerField(
        choices=SampleInterval.choices, default=SampleInterval.TWENTY_FIVE
    )
    routing_provider = models.CharField(max_length=32, default="tomtom")
    recommendation_safe = models.BooleanField(default=True)
    recommendation_explanation = models.TextField(blank=True)
    heatmap = models.JSONField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(load_weight_lb__gt=0), name="trip_load_positive"),
        ]

    def __str__(self):
        return f"{self.origin_label} → {self.destination_label} ({self.departure_at:%Y-%m-%d %H:%M})"


class Route(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="routes")
    label = models.CharField(max_length=1)  # A, B, C in the order the router returned them
    rank = models.PositiveSmallIntegerField()  # 1 = recommended
    is_recommended = models.BooleanField(default=False)
    distance_mi = models.FloatField()
    duration_s = models.PositiveIntegerField()
    traffic_delay_s = models.PositiveIntegerField(default=0)
    geometry = models.TextField(help_text="Encoded polyline (precision 5)")
    miles_by_level = models.JSONField(help_text="Miles at each risk level, keyed by level name")
    avg_risk = models.FloatField()
    max_level = models.PositiveSmallIntegerField(choices=RiskLevel.choices)
    summary = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["trip", "label"]
        constraints = [models.UniqueConstraint(fields=["trip", "label"], name="route_unique_label")]

    def __str__(self):
        return f"Route {self.label} of {self.trip_id}"


class Checkpoint(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="checkpoints")
    seq = models.PositiveIntegerField()
    lat = models.FloatField()
    lon = models.FloatField()
    mile = models.FloatField()
    span_start_mi = models.FloatField()
    span_end_mi = models.FloatField()
    eta = models.DateTimeField()
    wind_mph = models.FloatField()
    gust_mph = models.FloatField()
    rain_in_hr = models.FloatField()
    snow_in_hr = models.FloatField()
    risk_level = models.PositiveSmallIntegerField(choices=RiskLevel.choices)
    reasons = models.JSONField(default=list)

    class Meta:
        ordering = ["route", "seq"]
        constraints = [models.UniqueConstraint(fields=["route", "seq"], name="checkpoint_unique_seq")]

    def __str__(self):
        return f"Checkpoint {self.seq} (mile {self.mile:.0f}) on route {self.route_id}"
