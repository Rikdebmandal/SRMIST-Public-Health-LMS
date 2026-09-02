from django.db.models import F
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.certificates.models import Certificate
from apps.certificates.serializers import CertificateSerializer, PublicVerificationSerializer
from apps.core.permissions import Perm
from apps.core.viewsets import AuditedModelViewSet


class CertificateViewSet(AuditedModelViewSet):
    queryset = Certificate.objects.select_related(
        "holder", "issuing_department", "issued_by"
    ).all()
    serializer_class = CertificateSerializer
    required_permission = Perm.CERTIFICATE_VIEW
    required_write_permission = Perm.CERTIFICATE_MANAGE
    filterset_fields = ["holder", "certificate_type", "status", "issuing_department"]
    search_fields = ["certificate_id", "title", "holder__full_name"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    audit_object_type = "certificate"

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.has_perm_code(Perm.CERTIFICATE_MANAGE):
            qs = qs.filter(holder=self.request.user)
        return qs

    def perform_create(self, serializer):
        return serializer.save(
            issued_by=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        certificate = self.get_object()
        certificate.status = Certificate.Status.REVOKED
        certificate.revoked_reason = request.data.get("reason", "")[:250]
        certificate.save(update_fields=["status", "revoked_reason", "updated_at"])
        return Response(CertificateSerializer(certificate).data)


class CertificateVerificationView(APIView):
    """Public endpoint backing /verify/certificate/{id} - no authentication."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, certificate_id):
        certificate = Certificate.objects.filter(
            certificate_id__iexact=certificate_id
        ).select_related("holder", "issuing_department").first()
        if certificate is None:
            return Response(
                {
                    "valid": False,
                    "message": "No certificate exists with that identifier.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        Certificate.objects.filter(pk=certificate.pk).update(
            verification_count=F("verification_count") + 1
        )
        valid = certificate.status == Certificate.Status.ISSUED
        return Response(
            {
                "valid": valid,
                "message": "This certificate is genuine."
                if valid
                else "This certificate has been revoked by the issuing department.",
                "certificate": PublicVerificationSerializer(certificate).data,
            }
        )
