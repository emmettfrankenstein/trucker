"""One error shape for every API failure: ``{"error": {"code", "message", "details"}}``."""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from providers.base import ProviderError


def api_exception_handler(exc, context):
    if isinstance(exc, ProviderError):
        return Response(
            {"error": {"code": "upstream_error", "message": str(exc), "details": None}},
            status=exc.status,
        )
    response = exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    if isinstance(data, dict) and "detail" in data and len(data) <= 2:
        message, details = str(data["detail"]), None
    else:
        message, details = "Invalid input.", data
    detail = data.get("detail") if isinstance(data, dict) else None
    code = getattr(detail, "code", None) or getattr(exc, "default_code", "error")
    if response.status_code == status.HTTP_400_BAD_REQUEST:
        code = "invalid"
    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
