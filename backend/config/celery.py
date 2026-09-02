import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("public_health_lms")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "weekly-academic-digest": {
        "task": "notifications.send_weekly_digest",
        "schedule": crontab(hour=7, minute=0, day_of_week="mon"),
    },
    "assignment-deadline-reminders": {
        "task": "notifications.assignment_deadline_reminders",
        "schedule": crontab(hour=18, minute=0),
    },
    "attendance-alert-sweep": {
        "task": "notifications.evaluate_attendance_alerts",
        "schedule": crontab(hour=20, minute=0),
    },
    "expire-stale-content": {
        "task": "notifications.expire_stale_content",
        "schedule": crontab(hour=1, minute=0),
    },
    "refresh-risk-snapshots": {
        "task": "analytics.refresh_risk_snapshots",
        "schedule": crontab(hour=2, minute=0, day_of_week="sun"),
    },
}
