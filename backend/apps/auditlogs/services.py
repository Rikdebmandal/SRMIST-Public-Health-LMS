"""The single entry point for writing audit history."""
import logging

from apps.auditlogs.middleware import get_client_ip, get_current_request
from apps.auditlogs.models import AuditAction, AuditLog

logger = logging.getLogger(__name__)

#: Never persisted into audit metadata.
SENSITIVE_KEYS = {
    "password", "new_password", "old_password", "token", "refresh", "access",
    "secret", "authorization", "api_key", "otp",
}


def scrub(data):
    """Recursively strip credentials before anything is written to storage."""
    if isinstance(data, dict):
        return {
            key: ("[redacted]" if key.lower() in SENSITIVE_KEYS else scrub(value))
            for key, value in data.items()
        }
    if isinstance(data, (list, tuple)):
        return [scrub(item) for item in data]
    return data


def record(
    action,
    actor=None,
    obj=None,
    description="",
    metadata=None,
    object_type="",
    object_id="",
    object_label="",
):
    """Write one audit entry. Never raises into the caller's request."""
    request = get_current_request()
    if actor is None and request is not None:
        candidate = getattr(request, "user", None)
        if candidate is not None and getattr(candidate, "is_authenticated", False):
            actor = candidate

    if obj is not None:
        object_type = object_type or obj.__class__.__name__
        object_id = object_id or str(getattr(obj, "pk", ""))
        object_label = object_label or str(obj)[:250]

    try:
        return AuditLog.objects.create(
            actor=actor if getattr(actor, "pk", None) else None,
            actor_email=getattr(actor, "email", "") or "",
            actor_role=getattr(actor, "role", "") or "",
            action=action,
            object_type=object_type[:80],
            object_id=str(object_id)[:64],
            object_label=object_label[:250],
            description=description[:400],
            metadata=scrub(metadata or {}),
            ip_address=get_client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT", "")[:300] if request else ""),
        )
    except Exception:  # pragma: no cover - auditing must never break a request
        logger.exception("Failed to write audit entry for action=%s", action)
        return None


__all__ = ["record", "AuditAction", "scrub"]
