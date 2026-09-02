"""Dashboards, the analytics workspace and the risk indicator API."""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.academics.models import Department
from apps.accounts.models import User
from apps.analytics import services
from apps.analytics.models import ActivityLog, RiskRule, RiskSnapshot
from apps.analytics.serializers import (
    ActivityLogSerializer,
    RiskRuleSerializer,
    RiskSnapshotSerializer,
)
from apps.auditlogs import services as audit
from apps.auditlogs.models import AuditAction
from apps.core.permissions import HasPerm, Perm, Roles
from apps.core.viewsets import AuditedModelViewSet


class DashboardViewSet(viewsets.ViewSet):
    """/api/v1/analytics/dashboard - one endpoint per role."""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Return the dashboard appropriate to the caller's role."""
        user = request.user
        ActivityLog.objects.create(user=user, action="dashboard.view")

        if user.role == Roles.STUDENT:
            return Response({"type": "student", "data": services.student_dashboard(user)})
        if user.role in (Roles.FACULTY, Roles.SCHOLAR):
            payload = {"type": "faculty", "data": services.faculty_dashboard(user)}
            if user.role == Roles.SCHOLAR:
                payload["type"] = "scholar"
                payload["research"] = self._scholar_research(user)
            return Response(payload)
        if user.role == Roles.ADMIN:
            department = user.department
            if department is None:
                return Response({"type": "institution", "data": services.institution_dashboard()})
            return Response({"type": "department", "data": services.department_dashboard(department)})
        if user.role == Roles.DEAN:
            return Response({"type": "institution", "data": services.institution_dashboard()})
        if user.role == Roles.ALUMNI:
            return Response({"type": "alumni", "data": self._alumni_dashboard(user)})
        return Response({"type": "generic", "data": {}})

    def _scholar_research(self, user):
        from apps.research.models import Publication, ResearchProject

        return {
            "projects": ResearchProject.objects.filter(principal_investigator=user).count(),
            "publications": Publication.objects.filter(owner=user).count(),
            "supervised": user.supervised_scholars.count(),
        }

    def _alumni_dashboard(self, user):
        from apps.alumni.models import JobPosting, MentorshipRequest
        from apps.calendarapp.models import CalendarEvent
        from django.utils import timezone

        return {
            "kpis": {
                "open_opportunities": JobPosting.objects.filter(
                    status=JobPosting.Status.PUBLISHED
                ).count(),
                "my_postings": JobPosting.objects.filter(posted_by=user).count(),
                "mentorship_requests": MentorshipRequest.objects.filter(
                    mentor=user, status=MentorshipRequest.Status.PENDING
                ).count(),
                "upcoming_events": CalendarEvent.objects.filter(
                    is_published=True, start_at__gte=timezone.now()
                ).count(),
            },
            "requests": [
                {
                    "id": str(item.id),
                    "requester": item.requester.full_name,
                    "topic": item.topic,
                    "status": item.status,
                    "created_at": item.created_at.isoformat(),
                }
                for item in MentorshipRequest.objects.filter(mentor=user).select_related(
                    "requester"
                )[:10]
            ],
        }

    @action(detail=False, methods=["get"], url_path="department/(?P<department_id>[^/.]+)")
    def department(self, request, department_id=None):
        if not request.user.has_perm_code(Perm.ANALYTICS_VIEW_DEPARTMENT):
            return Response(
                {"error": {"code": "permission_denied", "message": "Department analytics are restricted."}},
                status=403,
            )
        department = Department.objects.filter(pk=department_id).first()
        if department is None:
            return Response({"error": {"code": "not_found", "message": "Department not found."}}, status=404)
        if request.user.role == Roles.ADMIN and request.user.department_id != department.id:
            return Response(
                {"error": {"code": "permission_denied", "message": "You may only view your own department."}},
                status=403,
            )
        return Response(services.department_dashboard(department))

    @action(detail=False, methods=["get"])
    def institution(self, request):
        if not request.user.has_perm_code(Perm.ANALYTICS_VIEW_INSTITUTION):
            return Response(
                {"error": {"code": "permission_denied", "message": "Institution analytics are restricted."}},
                status=403,
            )
        return Response(services.institution_dashboard())


class AnalyticsWorkspaceViewSet(viewsets.ViewSet):
    """Exploratory analytics for Health Data Science users (brief section 32)."""

    permission_classes = [IsAuthenticated]

    def _scope_department(self, request):
        if request.user.role in (Roles.DEAN,) or request.user.is_superuser:
            department_id = request.query_params.get("department")
            return Department.objects.filter(pk=department_id).first() if department_id else None
        return request.user.department

    @action(detail=False, methods=["get"], url_path="attendance-vs-performance")
    def attendance_vs_performance(self, request):
        if not request.user.has_perm_code(Perm.ANALYTICS_VIEW_COURSE):
            return Response(
                {"error": {"code": "permission_denied", "message": "Analytics are restricted."}},
                status=403,
            )
        points = services.correlation_workspace(self._scope_department(request))
        n = len(points)
        correlation = None
        if n >= 3:
            mean_x = sum(p["attendance"] for p in points) / n
            mean_y = sum(p["performance"] for p in points) / n
            numerator = sum(
                (p["attendance"] - mean_x) * (p["performance"] - mean_y) for p in points
            )
            denom_x = sum((p["attendance"] - mean_x) ** 2 for p in points) ** 0.5
            denom_y = sum((p["performance"] - mean_y) ** 2 for p in points) ** 0.5
            if denom_x and denom_y:
                correlation = round(numerator / (denom_x * denom_y), 3)
        return Response(
            {
                "points": points,
                "sample_size": n,
                "pearson_r": correlation,
                "note": "Correlation is descriptive only and does not imply causation.",
            }
        )

    @action(detail=False, methods=["get"], url_path="grade-distribution")
    def grade_distribution(self, request):
        from django.db.models import Count

        from apps.assessments.models import CourseResult

        qs = CourseResult.objects.all()
        department = self._scope_department(request)
        if department is not None:
            qs = qs.filter(section__course__department=department)
        section_id = request.query_params.get("section")
        if section_id:
            qs = qs.filter(section_id=section_id)
        rows = qs.exclude(grade_letter="").values("grade_letter").annotate(count=Count("id"))
        return Response(sorted(rows, key=lambda row: row["grade_letter"]))

    @action(detail=False, methods=["get"], url_path="submission-rates")
    def submission_rates(self, request):
        from apps.assignments.models import Assignment, AssignmentSubmission
        from apps.courses.models import Enrollment

        department = self._scope_department(request)
        assignments = Assignment.objects.filter(status=Assignment.Status.PUBLISHED)
        if department is not None:
            assignments = assignments.filter(section__course__department=department)

        rows = []
        for assignment in assignments.select_related("section__course")[:50]:
            enrolled = assignment.section.enrollments.filter(
                status=Enrollment.Status.ACTIVE
            ).count()
            submitted = AssignmentSubmission.objects.filter(assignment=assignment).count()
            rows.append(
                {
                    "assignment": assignment.title,
                    "course": assignment.section.course.code,
                    "enrolled": enrolled,
                    "submitted": submitted,
                    "rate": round(submitted / enrolled * 100, 2) if enrolled else 0,
                }
            )
        return Response(rows)

    @action(detail=False, methods=["get"], url_path="engagement")
    def engagement(self, request):
        from django.db.models import Count
        from django.db.models.functions import TruncDate

        rows = (
            ActivityLog.objects.all()
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(events=Count("id"), users=Count("user", distinct=True))
            .order_by("day")[:60]
        )
        return Response(
            [
                {
                    "day": row["day"].isoformat() if row["day"] else None,
                    "events": row["events"],
                    "users": row["users"],
                }
                for row in rows
            ]
        )


class RiskViewSet(viewsets.ViewSet):
    """The Academic Support Risk Indicator (brief sections 31, 89)."""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        return Response(services.evaluate_student_risk(request.user))

    @action(detail=False, methods=["get"], url_path="students")
    def students(self, request):
        if not request.user.has_perm_code(Perm.RISK_VIEW):
            return Response(
                {"error": {"code": "permission_denied", "message": "Risk indicators are restricted."}},
                status=403,
            )
        department = request.user.department if request.user.role == Roles.ADMIN else None
        if request.user.role == Roles.DEAN and request.query_params.get("department"):
            department = Department.objects.filter(
                pk=request.query_params["department"]
            ).first()
        level = request.query_params.get("level", "moderate")
        results = services.at_risk_students(department=department, minimum_level=level)
        audit.record(
            AuditAction.EXPORT,
            description="Viewed at-risk student list",
            metadata={"count": len(results), "level": level},
        )
        return Response(
            {
                "indicator_name": "Academic Support Risk Indicator",
                "disclaimer": (
                    "Rule-based signal for human review. Not a prediction and not a "
                    "judgement of ability. Every listed factor is shown so staff can "
                    "verify the reasoning before acting."
                ),
                "count": len(results),
                "students": results,
            }
        )

    @action(detail=False, methods=["get"], url_path="student/(?P<student_id>[^/.]+)")
    def student(self, request, student_id=None):
        if str(request.user.pk) != str(student_id) and not request.user.has_perm_code(
            Perm.RISK_VIEW
        ):
            return Response(
                {"error": {"code": "permission_denied", "message": "Risk indicators are restricted."}},
                status=403,
            )
        student = User.objects.filter(pk=student_id).first()
        if student is None:
            return Response({"error": {"code": "not_found", "message": "Student not found."}}, status=404)
        return Response(services.evaluate_student_risk(student))


class RiskRuleViewSet(AuditedModelViewSet):
    queryset = RiskRule.objects.select_related("department").all()
    serializer_class = RiskRuleSerializer
    permission_classes = [IsAuthenticated, HasPerm]
    required_permission = Perm.RISK_VIEW
    required_write_permission = Perm.RISK_CONFIGURE
    filterset_fields = ["department", "is_active", "metric"]
    pagination_class = None
    audit_object_type = "risk rule"

    @action(detail=False, methods=["get"])
    def defaults(self, request):
        from apps.core.calculations import DEFAULT_RISK_RULES

        return Response(DEFAULT_RISK_RULES)


class RiskSnapshotViewSet(AuditedModelViewSet):
    queryset = RiskSnapshot.objects.select_related("student", "reviewed_by").all()
    serializer_class = RiskSnapshotSerializer
    permission_classes = [IsAuthenticated, HasPerm]
    required_permission = Perm.RISK_VIEW
    required_write_permission = Perm.RISK_VIEW
    filterset_fields = ["student", "level"]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.has_perm_code(Perm.RISK_VIEW):
            qs = qs.filter(student=self.request.user)
        return qs

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        """Record that a human has reviewed the signal - required before action."""
        from django.utils import timezone

        snapshot = self.get_object()
        snapshot.reviewed_by = request.user
        snapshot.reviewed_at = timezone.now()
        snapshot.review_note = request.data.get("note", "")[:2000]
        snapshot.save(update_fields=["reviewed_by", "reviewed_at", "review_note", "updated_at"])
        return Response(RiskSnapshotSerializer(snapshot).data)


class ActivityLogViewSet(AuditedModelViewSet):
    queryset = ActivityLog.objects.select_related("user").all()
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated, HasPerm]
    required_permission = Perm.ANALYTICS_VIEW_DEPARTMENT
    http_method_names = ["get"]
    filterset_fields = ["user", "action"]
