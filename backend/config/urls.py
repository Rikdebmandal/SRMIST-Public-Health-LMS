"""Versioned API routing: everything lives under /api/v1/."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.accounts import views as accounts_views
from apps.academics import views as academics_views
from apps.alumni import views as alumni_views
from apps.analytics import views as analytics_views
from apps.announcements import views as announcements_views
from apps.assessments import views as assessments_views
from apps.assignments import views as assignments_views
from apps.attendance import views as attendance_views
from apps.auditlogs import views as auditlogs_views
from apps.calendarapp import views as calendar_views
from apps.certificates import views as certificates_views
from apps.core import views as core_views
from apps.courses import views as courses_views
from apps.documents import views as documents_views
from apps.feedback import views as feedback_views
from apps.forums import views as forums_views
from apps.library import views as library_views
from apps.notifications import views as notifications_views
from apps.question_bank import views as question_views
from apps.research import views as research_views
from apps.settings_app import views as settings_views

# Paths carry no trailing slash, matching the API design in the brief
# (e.g. GET /api/v1/courses).
router = DefaultRouter(trailing_slash=False)

# People and structure
router.register("users", accounts_views.UserViewSet, basename="user")
router.register("roles/permissions", accounts_views.RolePermissionViewSet, basename="role-permission")
router.register("alumni/profiles", accounts_views.AlumniProfileViewSet, basename="alumni-profile")
router.register("departments", academics_views.DepartmentViewSet, basename="department")
router.register("programs", academics_views.ProgramViewSet, basename="program")
router.register("academic-sessions", academics_views.AcademicSessionViewSet, basename="academic-session")
router.register("semesters", academics_views.SemesterViewSet, basename="semester")
router.register("batches", academics_views.BatchViewSet, basename="batch")
router.register("curriculum", academics_views.CurriculumItemViewSet, basename="curriculum")
router.register("holidays", academics_views.HolidayViewSet, basename="holiday")

# Courses
router.register("course-types", courses_views.CourseTypeViewSet, basename="course-type")
router.register("courses", courses_views.CourseViewSet, basename="course")
router.register("sections", courses_views.CourseSectionViewSet, basename="section")
router.register("faculty-assignments", courses_views.FacultyAssignmentViewSet, basename="faculty-assignment")
router.register("enrollments", courses_views.EnrollmentViewSet, basename="enrollment")

# Teaching artefacts
router.register("notes", documents_views.NoteViewSet, basename="note")
router.register("question-topics", question_views.QuestionTopicViewSet, basename="question-topic")
router.register("questions", question_views.QuestionViewSet, basename="question")
router.register("assignments", assignments_views.AssignmentViewSet, basename="assignment")
router.register("submissions", assignments_views.AssignmentSubmissionViewSet, basename="submission")

# Attendance
router.register("attendance/policies", attendance_views.AttendancePolicyViewSet, basename="attendance-policy")
router.register("attendance/sessions", attendance_views.AttendanceSessionViewSet, basename="attendance-session")
router.register("attendance/records", attendance_views.AttendanceRecordViewSet, basename="attendance-record")
router.register("attendance/alerts", attendance_views.AttendanceAlertViewSet, basename="attendance-alert")
router.register("attendance/summary", attendance_views.AttendanceSummaryView, basename="attendance-summary")

# Assessment
router.register("grade-scales", assessments_views.GradeScaleViewSet, basename="grade-scale")
router.register("grade-bands", assessments_views.GradeBandViewSet, basename="grade-band")
router.register("assessment-components", assessments_views.AssessmentComponentViewSet, basename="assessment-component")
router.register("scores", assessments_views.ComponentScoreViewSet, basename="score")
router.register("external-marks", assessments_views.ExternalMarkViewSet, basename="external-mark")
router.register("gradebook", assessments_views.GradebookViewSet, basename="gradebook")

# Communication
router.register("announcement-categories", announcements_views.AnnouncementCategoryViewSet, basename="announcement-category")
router.register("announcements", announcements_views.AnnouncementViewSet, basename="announcement")
router.register("notifications", notifications_views.NotificationViewSet, basename="notification")
router.register("notification-preferences", notifications_views.NotificationPreferenceViewSet, basename="notification-preference")
router.register("notification-templates", notifications_views.NotificationTemplateViewSet, basename="notification-template")
router.register("digest", notifications_views.DigestViewSet, basename="digest")
router.register("events", calendar_views.CalendarEventViewSet, basename="event")
router.register("threads", forums_views.DiscussionThreadViewSet, basename="thread")
router.register("replies", forums_views.DiscussionReplyViewSet, basename="reply")
router.register("content-reports", forums_views.ContentReportViewSet, basename="content-report")
router.register("feedback/forms", feedback_views.FeedbackFormViewSet, basename="feedback-form")
router.register("feedback/questions", feedback_views.FeedbackQuestionViewSet, basename="feedback-question")

# Analytics
router.register("analytics/dashboard", analytics_views.DashboardViewSet, basename="dashboard")
router.register("analytics/workspace", analytics_views.AnalyticsWorkspaceViewSet, basename="workspace")
router.register("analytics/risk", analytics_views.RiskViewSet, basename="risk")
router.register("analytics/risk-rules", analytics_views.RiskRuleViewSet, basename="risk-rule")
router.register("analytics/risk-snapshots", analytics_views.RiskSnapshotViewSet, basename="risk-snapshot")
router.register("analytics/activity", analytics_views.ActivityLogViewSet, basename="activity")

# Research, alumni, careers
router.register("research/projects", research_views.ResearchProjectViewSet, basename="research-project")
router.register("research/milestones", research_views.ResearchMilestoneViewSet, basename="research-milestone")
router.register("research/publications", research_views.PublicationViewSet, basename="publication")
router.register("research/conferences", research_views.ConferenceViewSet, basename="conference")
router.register("mentorship", alumni_views.MentorshipRequestViewSet, basename="mentorship")
router.register("jobs", alumni_views.JobPostingViewSet, basename="job")

# Platform
router.register("library/categories", library_views.ResourceCategoryViewSet, basename="resource-category")
router.register("library/resources", library_views.ResourceLinkViewSet, basename="resource")
router.register("certificates", certificates_views.CertificateViewSet, basename="certificate")
router.register("audit-logs", auditlogs_views.AuditLogViewSet, basename="audit-log")
router.register("settings", settings_views.SystemSettingViewSet, basename="system-setting")
router.register("dashboard-widgets", settings_views.DashboardWidgetViewSet, basename="dashboard-widget")
router.register("exports", core_views.ExportViewSet, basename="export")

auth_patterns = [
    path("login", accounts_views.LoginView.as_view(), name="login"),
    path("logout", accounts_views.LogoutView.as_view(), name="logout"),
    path("refresh", accounts_views.RefreshView.as_view(), name="refresh"),
    path("me", accounts_views.MeView.as_view(), name="me"),
    path("password/change", accounts_views.PasswordChangeView.as_view(), name="password-change"),
    path("password/reset", accounts_views.PasswordResetRequestView.as_view(), name="password-reset"),
    path(
        "password/reset/confirm",
        accounts_views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
]

api_patterns = [
    path("auth/", include(auth_patterns)),
    path("health", core_views.HealthCheckView.as_view(), name="health"),
    path("search", core_views.GlobalSearchView.as_view(), name="search"),
    path(
        "verify/certificate/<str:certificate_id>",
        certificates_views.CertificateVerificationView.as_view(),
        name="verify-certificate",
    ),
    path("", include(router.urls)),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_patterns)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
