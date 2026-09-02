"""Research scholar module (brief section 33)."""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class ResearchProject(BaseModel):
    class Status(models.TextChoices):
        PROPOSED = "PROPOSED", "Proposed"
        ONGOING = "ONGOING", "Ongoing"
        COMPLETED = "COMPLETED", "Completed"
        ON_HOLD = "ON_HOLD", "On hold"

    title = models.CharField(max_length=300)
    abstract = models.TextField(blank=True)
    principal_investigator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="led_projects"
    )
    collaborators = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="collaborating_projects"
    )
    department = models.ForeignKey(
        "academics.Department", on_delete=models.CASCADE, related_name="research_projects"
    )
    research_area = models.CharField(max_length=200, blank=True)
    funding_agency = models.CharField(max_length=200, blank=True)
    funding_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    start_date = models.DateField(null=True, blank=True)
    expected_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PROPOSED)
    dataset_references = models.JSONField(default=list, blank=True)
    ethics_approval_reference = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title[:80]


class ResearchMilestone(BaseModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"
        DELAYED = "DELAYED", "Delayed"

    project = models.ForeignKey(
        ResearchProject, on_delete=models.CASCADE, related_name="milestones"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "due_date"]

    def __str__(self):
        return self.title


class Publication(BaseModel):
    class PublicationType(models.TextChoices):
        JOURNAL = "JOURNAL", "Journal article"
        CONFERENCE = "CONFERENCE", "Conference paper"
        BOOK = "BOOK", "Book"
        CHAPTER = "CHAPTER", "Book chapter"
        PREPRINT = "PREPRINT", "Preprint"
        REPORT = "REPORT", "Technical report"
        THESIS = "THESIS", "Thesis"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        ACCEPTED = "ACCEPTED", "Accepted"
        PUBLISHED = "PUBLISHED", "Published"

    title = models.CharField(max_length=400)
    authors = models.CharField(max_length=500, help_text="Comma-separated author list.")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="publications"
    )
    project = models.ForeignKey(
        ResearchProject,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="publications",
    )
    venue = models.CharField(max_length=300, blank=True, help_text="Journal or conference name.")
    publication_type = models.CharField(
        max_length=15, choices=PublicationType.choices, default=PublicationType.JOURNAL
    )
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    doi = models.CharField(max_length=120, blank=True)
    url = models.URLField(blank=True)
    abstract = models.TextField(blank=True)
    citation_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PUBLISHED)
    document = models.FileField(upload_to="publications/%Y/", null=True, blank=True)

    class Meta:
        ordering = ["-year", "title"]
        indexes = [models.Index(fields=["owner", "year"])]

    def __str__(self):
        return self.title[:80]


class ConferenceParticipation(BaseModel):
    class Role(models.TextChoices):
        PRESENTER = "PRESENTER", "Presenter"
        ATTENDEE = "ATTENDEE", "Attendee"
        ORGANISER = "ORGANISER", "Organiser"
        PANELLIST = "PANELLIST", "Panellist"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conferences"
    )
    name = models.CharField(max_length=300)
    organiser = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=150, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    participation_role = models.CharField(
        max_length=12, choices=Role.choices, default=Role.ATTENDEE
    )
    paper_title = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return self.name[:80]
