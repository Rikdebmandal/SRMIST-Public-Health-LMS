"""Access-control tests.

Section 9 of the brief requires that authorisation is enforced on the server,
not merely hidden in the UI. These tests attack the API directly.
"""
from datetime import date, timedelta

from django.urls import reverse
from rest_framework.test import APITestCase

from apps.academics.models import AcademicSession, Department, Semester
from apps.accounts.models import StudentProfile, User
from apps.assessments.models import AssessmentComponent, ComponentScore
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.core.rbac import Roles
from apps.courses.models import (
    Course,
    CourseSection,
    Enrollment,
    FacultyCourseAssignment,
)


class AccessControlTestCase(APITestCase):
    """Two students, two faculty and one section - enough to prove isolation."""

    @classmethod
    def setUpTestData(cls):
        cls.department = Department.objects.create(name="School of Public Health", code="SPH")
        cls.other_department = Department.objects.create(name="Epidemiology", code="EPI")

        cls.session = AcademicSession.objects.create(
            name="2026-27", start_date=date(2026, 6, 1), end_date=date(2027, 5, 31), is_current=True
        )
        cls.semester = Semester.objects.create(
            session=cls.session,
            number=1,
            name="Semester 1",
            start_date=date(2026, 6, 15),
            end_date=date(2026, 11, 15),
            is_current=True,
        )

        cls.course = Course.objects.create(
            code="PHS5101", name="Epidemiology", department=cls.department, credits=4
        )
        cls.section = CourseSection.objects.create(
            course=cls.course, semester=cls.semester, name="A", capacity=40
        )

        cls.faculty = cls._user("faculty@test.local", Roles.FACULTY, cls.department)
        cls.other_faculty = cls._user("faculty2@test.local", Roles.FACULTY, cls.department)
        FacultyCourseAssignment.objects.create(section=cls.section, faculty=cls.faculty)

        cls.student = cls._user("student@test.local", Roles.STUDENT, cls.department)
        cls.peer = cls._user("peer@test.local", Roles.STUDENT, cls.department)
        StudentProfile.objects.create(user=cls.student, enrollment_number="RA001")
        StudentProfile.objects.create(user=cls.peer, enrollment_number="RA002")
        Enrollment.objects.create(student=cls.student, section=cls.section)
        Enrollment.objects.create(student=cls.peer, section=cls.section)

        cls.admin = cls._user("hod@test.local", Roles.ADMIN, cls.department)
        cls.dean = cls._user("dean@test.local", Roles.DEAN, cls.department)
        cls.alumni = cls._user("alumni@test.local", Roles.ALUMNI, cls.department)

    @classmethod
    def _user(cls, email, role, department):
        user = User.objects.create_user(
            email=email, password="TestPass!2345", full_name=email.split("@")[0], role=role
        )
        user.department = department
        user.save()
        return user

    def auth(self, user):
        self.client.force_authenticate(user=user)


class AuthenticationTests(AccessControlTestCase):
    def test_anonymous_access_is_refused(self):
        for path in ["/api/v1/courses", "/api/v1/users", "/api/v1/gradebook/me"]:
            self.assertEqual(self.client.get(path).status_code, 401, path)

    def test_health_and_verification_are_public(self):
        self.assertEqual(self.client.get("/api/v1/health").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/settings/public").status_code, 200)

    def test_login_rejects_a_bad_password_without_revealing_the_account(self):
        response = self.client.post(
            "/api/v1/auth/login",
            {"email": "student@test.local", "password": "wrong"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid email or password", response.data["error"]["message"])

    def test_login_of_an_unknown_account_gives_the_same_message(self):
        response = self.client.post(
            "/api/v1/auth/login",
            {"email": "nobody@test.local", "password": "wrong"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid email or password", response.data["error"]["message"])

    def test_disabled_account_cannot_sign_in(self):
        self.student.is_active = False
        self.student.save()
        response = self.client.post(
            "/api/v1/auth/login",
            {"email": "student@test.local", "password": "TestPass!2345"},
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))


class StudentIsolationTests(AccessControlTestCase):
    """A student must never reach another student's academic record."""

    def test_student_cannot_read_a_peers_marks(self):
        self.auth(self.student)
        response = self.client.get(f"/api/v1/gradebook/student/{self.peer.id}")
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_read_a_peers_attendance(self):
        self.auth(self.student)
        response = self.client.get(f"/api/v1/attendance/summary/student/{self.peer.id}")
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_read_a_peers_risk_indicator(self):
        self.auth(self.student)
        response = self.client.get(f"/api/v1/analytics/risk/student/{self.peer.id}")
        self.assertEqual(response.status_code, 403)

    def test_student_can_read_their_own_record(self):
        self.auth(self.student)
        self.assertEqual(
            self.client.get(f"/api/v1/gradebook/student/{self.student.id}").status_code, 200
        )
        self.assertEqual(self.client.get("/api/v1/gradebook/me").status_code, 200)

    def test_student_score_list_contains_only_their_own_rows(self):
        component = AssessmentComponent.objects.create(
            section=self.section, name="Quiz", max_marks=20, weight=10
        )
        ComponentScore.objects.create(
            component=component,
            student=self.peer,
            marks_obtained=15,
            status=ComponentScore.Status.PUBLISHED,
        )
        ComponentScore.objects.create(
            component=component,
            student=self.student,
            marks_obtained=12,
            status=ComponentScore.Status.PUBLISHED,
        )
        self.auth(self.student)
        response = self.client.get("/api/v1/scores")
        owners = {str(row["student"]) for row in response.data["results"]}
        self.assertEqual(owners, {str(self.student.id)})

    def test_student_cannot_list_users(self):
        self.auth(self.student)
        self.assertEqual(self.client.get("/api/v1/users").status_code, 403)

    def test_student_cannot_read_audit_logs(self):
        self.auth(self.student)
        self.assertEqual(self.client.get("/api/v1/audit-logs").status_code, 403)

    def test_student_cannot_create_a_course(self):
        self.auth(self.student)
        response = self.client.post(
            "/api/v1/courses",
            {"code": "HACK", "name": "Hack", "department": str(self.department.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_escalate_their_own_role(self):
        self.auth(self.student)
        response = self.client.post(
            f"/api/v1/users/{self.student.id}/change-role", {"role": "ADMIN"}, format="json"
        )
        self.assertIn(response.status_code, (403, 404))
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, Roles.STUDENT)


class FacultyScopingTests(AccessControlTestCase):
    """Faculty reach only the sections they are actually assigned to."""

    def test_assigned_faculty_can_open_the_gradebook(self):
        self.auth(self.faculty)
        response = self.client.get(f"/api/v1/gradebook/section/{self.section.id}")
        self.assertEqual(response.status_code, 200)

    def test_unassigned_faculty_cannot_open_the_gradebook(self):
        self.auth(self.other_faculty)
        response = self.client.get(f"/api/v1/gradebook/section/{self.section.id}")
        self.assertEqual(response.status_code, 403)

    def test_unassigned_faculty_cannot_open_the_attendance_register(self):
        self.auth(self.other_faculty)
        response = self.client.get(f"/api/v1/attendance/summary/section/{self.section.id}")
        self.assertEqual(response.status_code, 403)

    def test_unassigned_faculty_cannot_create_an_attendance_session(self):
        self.auth(self.other_faculty)
        response = self.client.post(
            "/api/v1/attendance/sessions",
            {"section": str(self.section.id), "date": "2026-07-01", "period": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_assigned_faculty_can_create_an_attendance_session(self):
        self.auth(self.faculty)
        response = self.client.post(
            "/api/v1/attendance/sessions",
            {"section": str(self.section.id), "date": "2026-07-01", "period": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        # Every enrolled student gets a prepopulated row.
        session = AttendanceSession.objects.get(pk=response.data["id"])
        self.assertEqual(AttendanceRecord.objects.filter(session=session).count(), 2)

    def test_faculty_cannot_publish_marks_without_the_permission(self):
        component = AssessmentComponent.objects.create(
            section=self.section, name="Quiz", max_marks=20, weight=10
        )
        self.auth(self.faculty)
        response = self.client.post(
            "/api/v1/scores/publish", {"component": str(component.id)}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_publish_marks(self):
        component = AssessmentComponent.objects.create(
            section=self.section, name="Quiz", max_marks=20, weight=10
        )
        self.auth(self.admin)
        response = self.client.post(
            "/api/v1/scores/publish", {"component": str(component.id)}, format="json"
        )
        self.assertEqual(response.status_code, 200)


class RoleBoundaryTests(AccessControlTestCase):
    def test_dean_sees_institution_analytics(self):
        self.auth(self.dean)
        self.assertEqual(
            self.client.get("/api/v1/analytics/dashboard/institution").status_code, 200
        )

    def test_faculty_cannot_see_institution_analytics(self):
        self.auth(self.faculty)
        self.assertEqual(
            self.client.get("/api/v1/analytics/dashboard/institution").status_code, 403
        )

    def test_dean_cannot_manage_users(self):
        """The Dean is deliberately read-heavy (brief section 8.1)."""
        self.auth(self.dean)
        response = self.client.post(
            "/api/v1/users",
            {"email": "new@test.local", "full_name": "New", "role": "STUDENT"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_alumni_hold_no_academic_record_permissions(self):
        self.auth(self.alumni)
        self.assertNotIn("attendance.view_own", self.alumni.permission_codes)
        self.assertNotIn("marks.view_own", self.alumni.permission_codes)

    def test_alumni_cannot_reach_student_data(self):
        self.auth(self.alumni)
        self.assertEqual(self.client.get("/api/v1/scores").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/enrollments").status_code, 403)

    def test_role_permission_override_takes_effect(self):
        from apps.accounts.models import RolePermission

        RolePermission.objects.create(
            role=Roles.STUDENT, permission_code="user.view", is_granted=True
        )
        self.student.refresh_from_db()
        # The override replaces the default set entirely.
        self.assertIn("user.view", self.student.permission_codes)
        self.assertNotIn("marks.view_own", self.student.permission_codes)
