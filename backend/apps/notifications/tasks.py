"""Background jobs (brief sections 24, 69).

These run under Celery in production; with CELERY_TASK_ALWAYS_EAGER they also
run inline, which keeps local development dependency-free.
"""
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="notifications.send_weekly_digest")
def send_weekly_digest(user_id=None):
    """Build and deliver the weekly academic digest."""
    from apps.accounts.models import User
    from apps.core.rbac import Roles
    from apps.notifications.models import DigestSubscription, Notification
    from apps.notifications.services import build_weekly_digest, notify, render_digest_text

    users = User.objects.filter(is_active=True, role__in=[Roles.STUDENT, Roles.SCHOLAR])
    if user_id:
        users = users.filter(pk=user_id)

    sent = 0
    for user in users:
        subscription = DigestSubscription.objects.filter(user=user).first()
        if subscription and subscription.frequency == DigestSubscription.Frequency.OFF:
            continue
        digest = build_weekly_digest(user)
        body = render_digest_text(digest)
        notify(
            [user],
            event="WEEKLY_DIGEST",
            title="Your Weekly Public Health Academic Update",
            body=body,
            link="/dashboard",
            level=Notification.Level.INFO,
            metadata={"counts": {
                "notes": len(digest["new_notes"]),
                "deadlines": len(digest["upcoming_deadlines"]),
            }},
        )
        if subscription and subscription.send_email and user.email:
            send_mail(
                subject="Your Weekly Public Health Academic Update",
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            subscription.last_sent_at = timezone.now()
            subscription.save(update_fields=["last_sent_at"])
        sent += 1
    logger.info("Weekly digest delivered to %s users", sent)
    return sent


@shared_task(name="notifications.assignment_deadline_reminders")
def assignment_deadline_reminders(hours_ahead=24):
    """Remind students about assignments falling due soon."""
    from apps.assignments.models import Assignment, AssignmentSubmission
    from apps.courses.models import Enrollment
    from apps.notifications.models import Notification
    from apps.notifications.services import notify

    now = timezone.now()
    window_end = now + timezone.timedelta(hours=hours_ahead)
    assignments = Assignment.objects.filter(
        status=Assignment.Status.PUBLISHED, due_date__gte=now, due_date__lte=window_end
    ).select_related("section__course")

    reminded = 0
    for assignment in assignments:
        submitted = set(
            AssignmentSubmission.objects.filter(assignment=assignment).values_list(
                "student_id", flat=True
            )
        )
        pending = [
            enrollment.student
            for enrollment in assignment.section.enrollments.filter(
                status=Enrollment.Status.ACTIVE
            ).select_related("student")
            if enrollment.student_id not in submitted
        ]
        if not pending:
            continue
        notify(
            pending,
            event="ASSIGNMENT_DEADLINE",
            title="Deadline approaching: %s" % assignment.title,
            body="%s is due on %s."
            % (assignment.title, timezone.localtime(assignment.due_date).strftime("%d %b %Y, %H:%M")),
            link="/assignments/%s" % assignment.id,
            level=Notification.Level.WARNING,
        )
        reminded += len(pending)
    return reminded


@shared_task(name="notifications.evaluate_attendance_alerts")
def evaluate_attendance_alerts():
    """Sweep active sections and raise attendance alerts."""
    from apps.attendance.services import evaluate_alerts
    from apps.courses.models import CourseSection
    from apps.notifications.models import Notification
    from apps.notifications.services import notify

    total = 0
    for section in CourseSection.objects.filter(is_active=True).select_related("course"):
        alerts = evaluate_alerts(section)
        for alert in alerts:
            notify(
                [alert.student],
                event="ATTENDANCE_WARNING",
                title="Attendance alert - %s" % section.course.code,
                body=alert.message,
                link="/attendance",
                level=Notification.Level.WARNING
                if alert.level == "WARNING"
                else Notification.Level.CRITICAL,
            )
        total += len(alerts)
    return total


@shared_task(name="notifications.expire_stale_content")
def expire_stale_content():
    """Move expired announcements and job postings out of the live feeds."""
    from apps.alumni.models import JobPosting
    from apps.announcements.models import Announcement

    now = timezone.now()
    announcements = Announcement.objects.filter(
        status=Announcement.Status.PUBLISHED, expires_at__isnull=False, expires_at__lt=now
    ).update(status=Announcement.Status.EXPIRED)
    jobs = JobPosting.objects.filter(
        status=JobPosting.Status.PUBLISHED, deadline__lt=timezone.localdate()
    ).update(status=JobPosting.Status.EXPIRED)
    return {"announcements": announcements, "jobs": jobs}


@shared_task(name="analytics.refresh_risk_snapshots")
def refresh_risk_snapshots():
    """Recompute the Academic Support Risk Indicator for every active student."""
    from apps.accounts.models import User
    from apps.analytics.services import evaluate_student_risk
    from apps.core.rbac import Roles

    count = 0
    for student in User.objects.filter(role=Roles.STUDENT, is_active=True):
        evaluate_student_risk(student, persist=True)
        count += 1
    return count
