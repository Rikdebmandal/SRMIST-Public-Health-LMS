"""Notification fan-out: respects each user's per-event preferences."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.notifications.models import (
    Notification,
    NotificationPreference,
    NotificationTemplate,
)

logger = logging.getLogger(__name__)


def _preference(user, event):
    pref = NotificationPreference.objects.filter(user=user, event=event).first()
    if pref:
        return pref.in_app, pref.email
    template = NotificationTemplate.objects.filter(event=event, is_active=True).first()
    if template:
        return template.in_app_enabled, template.email_enabled
    return True, False


def notify(recipients, event, title, body="", link="", level=Notification.Level.INFO, metadata=None):
    """Create in-app notifications and send email where the user allows it.

    Returns the list of created notifications. Never raises into the caller.
    """
    created = []
    recipients = [user for user in recipients if user is not None]
    template = NotificationTemplate.objects.filter(event=event, is_active=True).first()

    for user in recipients:
        try:
            in_app, by_email = _preference(user, event)
            rendered_title, rendered_body = title, body
            if template:
                rendered_title, rendered_body = template.render(
                    {
                        "student_name": user.full_name,
                        "user_name": user.full_name,
                        "title": title,
                        "body": body,
                    }
                )
                if title:
                    rendered_title = title
                if body:
                    rendered_body = body

            if in_app:
                notification = Notification.objects.create(
                    recipient=user,
                    event=event,
                    title=rendered_title[:200],
                    body=rendered_body,
                    level=level,
                    link=link[:300],
                    metadata=metadata or {},
                )
                created.append(notification)

            if by_email and user.email:
                send_mail(
                    subject=rendered_title[:200],
                    message=rendered_body or rendered_title,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
                if created and created[-1].recipient_id == user.id:
                    created[-1].emailed_at = timezone.now()
                    created[-1].save(update_fields=["emailed_at"])
        except Exception:  # pragma: no cover - notification must not break the caller
            logger.exception("Failed to notify user %s about %s", getattr(user, "pk", "?"), event)
    return created


def build_weekly_digest(user):
    """Assemble one user's weekly academic summary (brief section 24)."""
    from apps.announcements.models import Announcement
    from apps.assignments.models import Assignment, AssignmentSubmission
    from apps.attendance import services as attendance_services
    from apps.calendarapp.models import CalendarEvent
    from apps.courses.models import Enrollment
    from apps.documents.models import Note

    since = timezone.now() - timezone.timedelta(days=7)
    horizon = timezone.now() + timezone.timedelta(days=7)

    section_ids = list(
        Enrollment.objects.filter(student=user, status=Enrollment.Status.ACTIVE).values_list(
            "section_id", flat=True
        )
    )

    new_notes = Note.objects.filter(
        section_id__in=section_ids, is_published=True, created_at__gte=since
    ).select_related("course")[:10]

    upcoming = Assignment.objects.filter(
        section_id__in=section_ids,
        status=Assignment.Status.PUBLISHED,
        due_date__gte=timezone.now(),
        due_date__lte=horizon,
    ).select_related("section__course")[:10]

    submitted_ids = set(
        AssignmentSubmission.objects.filter(student=user).values_list("assignment_id", flat=True)
    )

    announcements = Announcement.objects.filter(
        status=Announcement.Status.PUBLISHED, publish_at__gte=since
    )[:10]

    events = CalendarEvent.objects.filter(
        is_published=True, start_at__gte=timezone.now(), start_at__lte=horizon
    )[:10]

    attendance = attendance_services.student_overall(user)

    return {
        "user": {"id": str(user.pk), "full_name": user.full_name, "email": user.email},
        "period": {"from": since.date().isoformat(), "to": timezone.now().date().isoformat()},
        "new_notes": [
            {"title": note.title, "course": note.course.code, "id": str(note.id)}
            for note in new_notes
        ],
        "upcoming_deadlines": [
            {
                "title": item.title,
                "course": item.section.course.code,
                "due_date": item.due_date.isoformat(),
                "submitted": str(item.id) in {str(x) for x in submitted_ids},
            }
            for item in upcoming
        ],
        "attendance": {
            "percentage": attendance["percentage"],
            "status": attendance["status"],
            "threshold": attendance["warning_threshold"],
        },
        "announcements": [
            {"title": item.title, "priority": item.priority, "id": str(item.id)}
            for item in announcements
            if item.visible_to(user)
        ],
        "events": [
            {"title": event.title, "start_at": event.start_at.isoformat(), "category": event.category}
            for event in events
        ],
    }


def render_digest_text(digest) -> str:
    lines = [
        "Your Weekly Public Health Academic Update",
        "=" * 42,
        "",
        "Hello %s," % digest["user"]["full_name"],
        "",
        "Attendance: %.1f%% (%s)"
        % (digest["attendance"]["percentage"], digest["attendance"]["status"]),
        "",
    ]
    if digest["upcoming_deadlines"]:
        lines.append("Upcoming deadlines:")
        for item in digest["upcoming_deadlines"]:
            marker = "submitted" if item["submitted"] else "not submitted"
            lines.append("  - %s (%s) - %s [%s]" % (item["title"], item["course"], item["due_date"][:10], marker))
        lines.append("")
    if digest["new_notes"]:
        lines.append("New notes this week:")
        for note in digest["new_notes"]:
            lines.append("  - %s (%s)" % (note["title"], note["course"]))
        lines.append("")
    if digest["announcements"]:
        lines.append("Announcements:")
        for item in digest["announcements"]:
            lines.append("  - [%s] %s" % (item["priority"], item["title"]))
        lines.append("")
    if digest["events"]:
        lines.append("Coming up:")
        for event in digest["events"]:
            lines.append("  - %s (%s)" % (event["title"], event["start_at"][:10]))
        lines.append("")
    lines.append("Public Health LMS - School of Public Health, SRMIST")
    return "\n".join(lines)
