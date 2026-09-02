"""Shared viewset behaviour: actor stamping, auditing and scoped querysets."""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.auditlogs import services as audit
from apps.auditlogs.models import AuditAction
from apps.core.permissions import HasPerm


class AuditedModelViewSet(viewsets.ModelViewSet):
    """Stamps created_by/updated_by and writes an audit entry for every write.

    Subclasses declare ``required_permission`` (read) and
    ``required_write_permission`` (create/update/delete); :class:`HasPerm`
    enforces them server-side.
    """

    permission_classes = [IsAuthenticated, HasPerm]
    audit_object_type = ""

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        audit.record(
            AuditAction.CREATE,
            obj=instance,
            description="Created %s" % (self.audit_object_type or instance.__class__.__name__),
        )
        return instance

    def perform_update(self, serializer):
        instance = serializer.save(updated_by=self.request.user)
        audit.record(
            AuditAction.UPDATE,
            obj=instance,
            description="Updated %s" % (self.audit_object_type or instance.__class__.__name__),
            metadata={"changed_fields": list(serializer.validated_data.keys())},
        )
        return instance

    def perform_destroy(self, instance):
        audit.record(
            AuditAction.DELETE,
            obj=instance,
            description="Deleted %s" % (self.audit_object_type or instance.__class__.__name__),
        )
        instance.delete()


class ReadOnlyAuditedViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, HasPerm]
