"""Mentorship and the job / internship board (brief sections 34, 35)."""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class MentorshipRequest(BaseModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        DECLINED = "DECLINED", "Declined"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mentorship_requests_sent"
    )
    mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentorship_requests_received",
    )
    topic = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    responded_at = models.DateTimeField(null=True, blank=True)
    response_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["mentor", "status"])]

    def __str__(self):
        return "%s -> %s" % (self.requester.full_name, self.mentor.full_name)


class JobPosting(BaseModel):
    class OpportunityType(models.TextChoices):
        JOB = "JOB", "Job"
        INTERNSHIP = "INTERNSHIP", "Internship"
        RESEARCH = "RESEARCH", "Research opportunity"
        FELLOWSHIP = "FELLOWSHIP", "Fellowship"

    class WorkMode(models.TextChoices):
        ONSITE = "ONSITE", "On-site"
        REMOTE = "REMOTE", "Remote"
        HYBRID = "HYBRID", "Hybrid"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        CLOSED = "CLOSED", "Closed"
        EXPIRED = "EXPIRED", "Expired"

    title = models.CharField(max_length=200)
    organization = models.CharField(max_length=200)
    opportunity_type = models.CharField(
        max_length=15, choices=OpportunityType.choices, default=OpportunityType.JOB
    )
    work_mode = models.CharField(max_length=10, choices=WorkMode.choices, default=WorkMode.ONSITE)
    location = models.CharField(max_length=150, blank=True)
    description = models.TextField()
    eligibility = models.TextField(blank=True)
    skills_required = models.JSONField(default=list, blank=True)
    stipend_or_salary = models.CharField(max_length=100, blank=True)
    application_url = models.URLField(blank=True)
    contact_email = models.EmailField(blank=True)
    deadline = models.DateField(null=True, blank=True, db_index=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_postings"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PUBLISHED)
    view_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "deadline"])]

    def __str__(self):
        return "%s @ %s" % (self.title, self.organization)

    @property
    def is_open(self) -> bool:
        if self.status != self.Status.PUBLISHED:
            return False
        return self.deadline is None or self.deadline >= timezone.localdate()
