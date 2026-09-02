from rest_framework import serializers

from apps.accounts.serializers import UserBriefSerializer
from apps.certificates.models import Certificate


class CertificateSerializer(serializers.ModelSerializer):
    holder_detail = UserBriefSerializer(source="holder", read_only=True)
    type_display = serializers.CharField(source="get_certificate_type_display", read_only=True)
    department_name = serializers.CharField(
        source="issuing_department.name", read_only=True, default=""
    )
    issued_by_name = serializers.CharField(source="issued_by.full_name", read_only=True, default="")
    verification_url = serializers.CharField(read_only=True)

    class Meta:
        model = Certificate
        fields = [
            "id", "certificate_id", "holder", "holder_detail", "title", "description",
            "certificate_type", "type_display", "issued_on", "valid_until",
            "issuing_department", "department_name", "issued_by", "issued_by_name",
            "document", "status", "revoked_reason", "verification_count", "verification_url",
        ]
        read_only_fields = [
            "id", "certificate_id", "verification_count", "verification_url", "issued_by",
        ]

    def validate(self, attrs):
        issued = attrs.get("issued_on", getattr(self.instance, "issued_on", None))
        valid_until = attrs.get("valid_until", getattr(self.instance, "valid_until", None))
        if issued and valid_until and valid_until < issued:
            raise serializers.ValidationError(
                {"valid_until": "The validity date cannot precede the issue date."}
            )
        return attrs


class PublicVerificationSerializer(serializers.ModelSerializer):
    """Deliberately minimal - a verifier sees only what confirms authenticity."""

    holder_name = serializers.CharField(source="holder.full_name", read_only=True)
    department = serializers.CharField(
        source="issuing_department.name", read_only=True, default=""
    )
    type_display = serializers.CharField(source="get_certificate_type_display", read_only=True)

    class Meta:
        model = Certificate
        fields = [
            "certificate_id", "holder_name", "title", "certificate_type", "type_display",
            "issued_on", "valid_until", "department", "status",
        ]
        read_only_fields = fields
