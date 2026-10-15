from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from providers.base import Place

from . import services
from .models import Checkpoint, Route, Trip
from .serializers import PlaceSerializer, TripDetailSerializer, TripPlanSerializer, TripSummarySerializer


class _UserOrIpThrottle(SimpleRateThrottle):
    """Rate-limit per user when signed in, per IP otherwise."""

    methods: tuple[str, ...] = ()

    def get_cache_key(self, request, view):
        if self.methods and request.method not in self.methods:
            return None
        ident = request.user.pk if request.user.is_authenticated else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class PlanThrottle(_UserOrIpThrottle):
    """Planning fans out to the routing and weather APIs, so it gets a tighter budget."""

    scope = "plan"
    methods = ("POST",)


class GeocodeThrottle(_UserOrIpThrottle):
    scope = "geocode"


def _trip_queryset():
    return Trip.objects.prefetch_related(
        Prefetch(
            "routes",
            queryset=Route.objects.order_by("label").prefetch_related(
                Prefetch("checkpoints", queryset=Checkpoint.objects.order_by("seq"))
            ),
        )
    )


def _get_visible_trip(request, trip_id) -> Trip:
    """Anonymous trips are readable by anyone holding their UUID; owned trips only by the owner."""
    trip = get_object_or_404(_trip_queryset(), pk=trip_id)
    if trip.user_id and trip.user_id != getattr(request.user, "pk", None):
        raise NotFound()
    return trip


@extend_schema(
    parameters=[OpenApiParameter("q", str, required=True, description="Free-text place, min 3 chars")],
    responses=PlaceSerializer(many=True),
)
@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([GeocodeThrottle])
def geocode(request):
    query = request.query_params.get("q", "").strip()
    if len(query) < 3:
        return Response([])
    places = services.search_places(query[:120])
    return Response(PlaceSerializer(places, many=True).data)


@extend_schema(
    methods=["GET"],
    responses=TripSummarySerializer(many=True),
    description="Trips saved by the signed-in user, newest first.",
)
@extend_schema(
    methods=["POST"],
    request=TripPlanSerializer,
    responses={201: TripDetailSerializer},
    description="Plan a trip: fetch up to three truck routes, score weather risk at each checkpoint's ETA, "
    "and recommend one. Works anonymously; signed-in users get the trip saved to their history.",
)
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
@throttle_classes([PlanThrottle])
def trip_list(request):
    if request.method == "GET":
        if not request.user.is_authenticated:
            return Response(
                {"error": {"code": "not_authenticated", "message": "Sign in to see saved trips.", "details": None}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        trips = Trip.objects.filter(user=request.user)[:50]
        return Response(TripSummarySerializer(trips, many=True).data)

    serializer = TripPlanSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    trip = services.plan_trip(
        user=request.user,
        origin=Place(**data["origin"]),
        destination=Place(**data["destination"]),
        departure_at=data["departure_at"],
        load_weight_lb=data["load_weight_lb"],
        sample_interval_mi=data["sample_interval_mi"],
    )
    trip = _trip_queryset().get(pk=trip.pk)
    return Response(TripDetailSerializer(trip).data, status=status.HTTP_201_CREATED)


@extend_schema(methods=["GET"], responses=TripDetailSerializer)
@extend_schema(methods=["DELETE"], responses={204: None})
@api_view(["GET", "DELETE"])
@permission_classes([AllowAny])
def trip_detail(request, trip_id):
    trip = _get_visible_trip(request, trip_id)
    if request.method == "DELETE":
        if not request.user.is_authenticated or trip.user_id != request.user.pk:
            raise NotFound()
        trip.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(TripDetailSerializer(trip).data)


@extend_schema(
    responses=inline_serializer(
        "Heatmap",
        {
            "start": serializers.DateTimeField(),
            "hours": serializers.IntegerField(),
            "step_deg": serializers.FloatField(),
            "cells": serializers.ListField(child=serializers.ListField(child=serializers.FloatField())),
            "frames": serializers.DictField(),
        },
    ),
    description="Corridor grid with hourly frames 0..48 h from departure: risk level, wind mph, "
    "rain in/hr and snow in/hr, indexed frames[metric][hour][cell].",
)
@api_view(["GET"])
@permission_classes([AllowAny])
def trip_heatmap(request, trip_id):
    trip = _get_visible_trip(request, trip_id)
    response = Response(services.build_heatmap(trip))
    response["Cache-Control"] = "private, max-age=900"
    return response


@extend_schema(responses=inline_serializer("Health", {"status": serializers.CharField()}))
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})
