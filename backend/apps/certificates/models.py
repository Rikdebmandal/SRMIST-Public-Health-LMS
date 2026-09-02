"""Certificates with public verification (brief section 39).

The verification endpoint is deliberately public and read-only: it confirms a
certificate id, the holder's name and the title, and nothing else.
"""
import secrets

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


def generate_certificate_id() -> str:
    return "SPH-%s" % secrets.token_hex(6).upper()


class Certificate(BaseModel):
    class CertificateType(models.TextChoices):
        PARTICIPATION = "PARTICIPATION", "Participation"
        COMPLETION = "COMPLETION", "Course completion"
        INTERNSHIP = "INTERNSHIP", "Internship"
        WORKSHOP = "WORKSHOP", "Workshop"
        MERIT = "MERIT", "Merit"
        BONAFIDE = "BONAFIDE", "Bonafide"

    class Status(models.TextChoices):
        ISSUED = "ISSUED", "Issued"
        REVOKED = "REVOKED", "Revoked"

    certificate_id = models.CharField(
        max_length=30, unique=True, default=generate_certificate_id, db_index=True
    )
    holder = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="certificates"
    )
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    certificate_type = models.CharField(
        max_length=15, choices=CertificateType.choices, default=CertificateType.PARTICIPATION
    )
    issued_on = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    issuing_department = models.ForeignKey(
        "academics.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="certificates",
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="issued_certificates",
    )
    document = models.FileField(upload_to="certificates/%Y/", null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ISSUED)
    revoked_reason = models.CharField(max_length=250, blank=True)
    verification_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-issued_on"]

    def __str__(self):
        return "%s - %s" % (self.certificate_id, self.holder.full_name)

    @property
    def verification_url(self) -> str:
        from django.conf import settings as dj_settings

        return "%s/verify/certificate/%s" % (dj_settings.FRONTEND_BASE_URL, self.certificate_id)
