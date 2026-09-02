"""Consistent API error envelope (brief section 55).

Every failure returns::

    {"error": {"code": "validation_error", "message": "...", "details": {...}}}

Stack traces are never exposed to API consumers.
"""
import logging

from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

STATUS_CODE_NAMES = {
    400: "bad_request",
    401: "authentication_required",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "server_error",
}


def _envelope(code, message, details=None, http_status=400):
    payload = {"error": {"code": code, "message": message}}
    if details:
        payload["error"]["details"] = details
    return Response(payload, status=http_status)


def api_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        return _envelope(
            "validation_error",
            "The submitted data is invalid.",
            getattr(exc, "message_dict", {"non_field_errors": exc.messages}),
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if isinstance(exc, IntegrityError):
        logger.warning("Integrity error: %s", exc)
        return _envelope(
            "conflict",
            "This action conflicts with existing data.",
            None,
            status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, Http404):
        return _envelope("not_found", "The requested resource was not found.", None, 404)
    if isinstance(exc, PermissionDenied):
        return _envelope("permission_denied", "You do not have access to this resource.", None, 403)

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled server error", exc_info=exc)
        return _envelope(
            "server_error",
            "An unexpected error occurred. The incident has been logged.",
            None,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    code = STATUS_CODE_NAMES.get(response.status_code, "error")
    detail = response.data
    message = "Request failed."
    details = None

    if isinstance(detail, dict):
        if "detail" in detail:
            message = str(detail["detail"])
        else:
            message = "The submitted data is invalid."
            details = detail
            if response.status_code == 400:
                code = "validation_error"
    elif isinstance(detail, list):
        message = "; ".join(str(item) for item in detail)

    response.data = {"error": {"code": code, "message": message}}
    if details:
        response.data["error"]["details"] = details
    return response
