"""Course discussion and doubt-clearing forum (brief section 36)."""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class DiscussionThread(BaseModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        ANSWERED = "ANSWERED", "Answered"
        CLOSED = "CLOSED", "Closed"
        HIDDEN = "HIDDEN", "Hidden by moderator"

    section = models.ForeignKey(
        "courses.CourseSection", on_delete=models.CASCADE, related_name="threads"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="threads"
    )
    title = models.CharField(max_length=250)
    body = models.TextField()
    tags = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    is_pinned = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)
    reply_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]
        indexes = [models.Index(fields=["section", "status"])]

    def __str__(self):
        return self.title[:80]


class DiscussionReply(BaseModel):
    thread = models.ForeignKey(
        DiscussionThread, on_delete=models.CASCADE, related_name="replies"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="replies"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    body = models.TextField()
    is_accepted_answer = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    helpful_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return "Reply by %s" % self.author.full_name


class ReplyVote(BaseModel):
    reply = models.ForeignKey(DiscussionReply, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reply_votes"
    )

    class Meta:
        unique_together = [("reply", "user")]


class ContentReport(BaseModel):
    """Abuse / spam reporting for moderator review."""

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        REVIEWED = "REVIEWED", "Reviewed"
        DISMISSED = "DISMISSED", "Dismissed"
        ACTIONED = "ACTIONED", "Actioned"

    thread = models.ForeignKey(
        DiscussionThread, null=True, blank=True, on_delete=models.CASCADE, related_name="reports"
    )
    reply = models.ForeignKey(
        DiscussionReply, null=True, blank=True, on_delete=models.CASCADE, related_name="reports"
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="content_reports"
    )
    reason = models.CharField(max_length=300)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    resolution_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
