from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from .models import Checkpoint, RiskLevel, Route, Trip


class PlaceSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=255)
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)


class TripPlanSerializer(serializers.Serializer):
    """Input for planning a trip. Places come from the geocode endpoint's results."""

    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure_at = serializers.DateTimeField()
    load_weight_lb = serializers.IntegerField(min_value=1, max_value=200_000)
    sample_interval_mi = serializers.ChoiceField(choices=Trip.SampleInterval.choices, default=25)

    def validate_departure_at(self, value):
        now = timezone.now()
        if value < now - timedelta(hours=1):
            raise serializers.ValidationError("Departure can't be in the past.")
        if value > now + timedelta(days=settings.MAX_DEPARTURE_DAYS_AHEAD):
            raise serializers.ValidationError(
                f"Departure must be within {settings.MAX_DEPARTURE_DAYS_AHEAD} days (forecast horizon)."
            )
        return value

    def validate(self, attrs):
        o, d = attrs["origin"], attrs["destination"]
        if abs(o["lat"] - d["lat"]) < 1e-4 and abs(o["lon"] - d["lon"]) < 1e-4:
            raise serializers.ValidationError("Origin and destination must be different places.")
        return attrs


class CheckpointSerializer(serializers.ModelSerializer):
    risk_label = serializers.SerializerMethodField()

    class Meta:
        model = Checkpoint
        fields = [
            "seq",
            "lat",
            "lon",
            "mile",
            "span_start_mi",
            "span_end_mi",
            "eta",
            "wind_mph",
            "gust_mph",
            "rain_in_hr",
            "snow_in_hr",
            "risk_level",
            "risk_label",
            "reasons",
        ]

    def get_risk_label(self, obj) -> str:
        return RiskLevel(obj.risk_level).label


class RouteSerializer(serializers.ModelSerializer):
    checkpoints = CheckpointSerializer(many=True, read_only=True)
    max_level_label = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = [
            "label",
            "rank",
            "is_recommended",
            "distance_mi",
            "duration_s",
            "traffic_delay_s",
            "geometry",
            "miles_by_level",
            "avg_risk",
            "max_level",
            "max_level_label",
            "summary",
            "checkpoints",
        ]

    def get_max_level_label(self, obj) -> str:
        return RiskLevel(obj.max_level).label


class TripSummarySerializer(serializers.ModelSerializer):
    """Lightweight shape for history lists (no geometry or checkpoints)."""

    class Meta:
        model = Trip
        fields = [
            "id",
            "origin_label",
            "destination_label",
            "departure_at",
            "load_weight_lb",
            "sample_interval_mi",
            "recommendation_safe",
            "created_at",
        ]


class TripDetailSerializer(serializers.ModelSerializer):
    routes = RouteSerializer(many=True, read_only=True)
    origin = serializers.SerializerMethodField()
    destination = serializers.SerializerMethodField()
    recommendation = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = [
            "id",
            "origin",
            "destination",
            "departure_at",
            "load_weight_lb",
            "sample_interval_mi",
            "routing_provider",
            "recommendation",
            "routes",
            "created_at",
        ]

    def get_origin(self, obj) -> dict:
        return {"label": obj.origin_label, "lat": obj.origin_lat, "lon": obj.origin_lon}

    def get_destination(self, obj) -> dict:
        return {"label": obj.destination_label, "lat": obj.destination_lat, "lon": obj.destination_lon}

    def get_recommendation(self, obj) -> dict:
        best = next((r for r in obj.routes.all() if r.is_recommended), None)
        return {
            "route": best.label if best else None,
            "safe": obj.recommendation_safe,
            "explanation": obj.recommendation_explanation,
        }
