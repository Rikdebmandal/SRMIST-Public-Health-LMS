"""Central RBAC registry.

Permissions are declared here as stable string codes and mapped to roles.
The mapping is only the *default* - `apps.accounts.models.RolePermission` rows
override it at runtime so administrators can reconfigure roles from the admin
panel without a code change (brief sections 9 and 41).
"""


class Roles:
    DEAN = "DEAN"
    ADMIN = "ADMIN"
    FACULTY = "FACULTY"
    SCHOLAR = "SCHOLAR"
    STUDENT = "STUDENT"
    ALUMNI = "ALUMNI"

    CHOICES = [
        (DEAN, "Dean"),
        (ADMIN, "HOD / Staff Admin"),
        (FACULTY, "Professor / Faculty"),
        (SCHOLAR, "Research Scholar"),
        (STUDENT, "Student"),
        (ALUMNI, "Alumni"),
    ]
    ALL = [DEAN, ADMIN, FACULTY, SCHOLAR, STUDENT, ALUMNI]
    STAFF = [DEAN, ADMIN, FACULTY, SCHOLAR]


class Perm:
    """Permission codes. Format: <domain>.<action>."""

    # People and structure
    USER_VIEW = "user.view"
    USER_MANAGE = "user.manage"
    ROLE_MANAGE = "role.manage"
    DEPARTMENT_VIEW = "department.view"
    DEPARTMENT_MANAGE = "department.manage"
    ACADEMIC_MANAGE = "academic.manage"  # sessions, semesters, programs, curriculum

    # Courses
    COURSE_VIEW = "course.view"
    COURSE_MANAGE = "course.manage"
    COURSE_TEACH = "course.teach"  # own assigned sections
    ENROLLMENT_MANAGE = "enrollment.manage"

    # Teaching artefacts
    NOTE_VIEW = "note.view"
    NOTE_MANAGE = "note.manage"
    QUESTION_VIEW = "question.view"
    QUESTION_MANAGE = "question.manage"
    ASSIGNMENT_VIEW = "assignment.view"
    ASSIGNMENT_MANAGE = "assignment.manage"
    ASSIGNMENT_SUBMIT = "assignment.submit"
    ASSIGNMENT_GRADE = "assignment.grade"

    # Attendance and assessment
    ATTENDANCE_VIEW_OWN = "attendance.view_own"
    ATTENDANCE_VIEW_ALL = "attendance.view_all"
    ATTENDANCE_MARK = "attendance.mark"
    ATTENDANCE_CONFIGURE = "attendance.configure"
    MARKS_VIEW_OWN = "marks.view_own"
    MARKS_VIEW_ALL = "marks.view_all"
    MARKS_ENTER = "marks.enter"
    MARKS_PUBLISH = "marks.publish"
    MARKS_CONFIGURE = "marks.configure"
    EXTERNAL_MARKS_ENTER = "marks.enter_external"

    # Communication
    ANNOUNCEMENT_VIEW = "announcement.view"
    ANNOUNCEMENT_MANAGE = "announcement.manage"
    EVENT_VIEW = "event.view"
    EVENT_MANAGE = "event.manage"
    FORUM_PARTICIPATE = "forum.participate"
    FORUM_MODERATE = "forum.moderate"
    FEEDBACK_SUBMIT = "feedback.submit"
    FEEDBACK_MANAGE = "feedback.manage"

    # Analytics
    ANALYTICS_VIEW_SELF = "analytics.view_self"
    ANALYTICS_VIEW_COURSE = "analytics.view_course"
    ANALYTICS_VIEW_DEPARTMENT = "analytics.view_department"
    ANALYTICS_VIEW_INSTITUTION = "analytics.view_institution"
    RISK_VIEW = "risk.view"
    RISK_CONFIGURE = "risk.configure"

    # Research, alumni, careers
    RESEARCH_VIEW = "research.view"
    RESEARCH_MANAGE = "research.manage"
    ALUMNI_VIEW = "alumni.view"
    ALUMNI_MANAGE = "alumni.manage"
    MENTORSHIP_PARTICIPATE = "mentorship.participate"
    JOB_VIEW = "job.view"
    JOB_MANAGE = "job.manage"

    # Platform
    LIBRARY_VIEW = "library.view"
    LIBRARY_MANAGE = "library.manage"
    CERTIFICATE_VIEW = "certificate.view"
    CERTIFICATE_MANAGE = "certificate.manage"
    REPORT_EXPORT = "report.export"
    AUDIT_VIEW = "audit.view"
    SETTINGS_MANAGE = "settings.manage"


#: Human-readable labels used by the admin panel role editor.
PERMISSION_LABELS = {
    Perm.USER_VIEW: "View users",
    Perm.USER_MANAGE: "Create and edit users",
    Perm.ROLE_MANAGE: "Configure roles and permissions",
    Perm.DEPARTMENT_VIEW: "View departments",
    Perm.DEPARTMENT_MANAGE: "Manage departments",
    Perm.ACADEMIC_MANAGE: "Manage sessions, semesters, programs, curriculum",
    Perm.COURSE_VIEW: "View courses",
    Perm.COURSE_MANAGE: "Create and edit courses",
    Perm.COURSE_TEACH: "Teach assigned course sections",
    Perm.ENROLLMENT_MANAGE: "Manage enrolments",
    Perm.NOTE_VIEW: "View notes and resources",
    Perm.NOTE_MANAGE: "Upload and manage notes",
    Perm.QUESTION_VIEW: "View question bank",
    Perm.QUESTION_MANAGE: "Manage question bank",
    Perm.ASSIGNMENT_VIEW: "View assignments",
    Perm.ASSIGNMENT_MANAGE: "Create and edit assignments",
    Perm.ASSIGNMENT_SUBMIT: "Submit assignments",
    Perm.ASSIGNMENT_GRADE: "Grade assignment submissions",
    Perm.ATTENDANCE_VIEW_OWN: "View own attendance",
    Perm.ATTENDANCE_VIEW_ALL: "View attendance of others",
    Perm.ATTENDANCE_MARK: "Mark attendance",
    Perm.ATTENDANCE_CONFIGURE: "Configure attendance rules",
    Perm.MARKS_VIEW_OWN: "View own marks",
    Perm.MARKS_VIEW_ALL: "View marks of others",
    Perm.MARKS_ENTER: "Enter internal marks",
    Perm.MARKS_PUBLISH: "Publish and lock marks",
    Perm.MARKS_CONFIGURE: "Configure assessment components and grading",
    Perm.EXTERNAL_MARKS_ENTER: "Enter external / university marks",
    Perm.ANNOUNCEMENT_VIEW: "View announcements",
    Perm.ANNOUNCEMENT_MANAGE: "Publish announcements",
    Perm.EVENT_VIEW: "View calendar events",
    Perm.EVENT_MANAGE: "Manage calendar events",
    Perm.FORUM_PARTICIPATE: "Participate in discussions",
    Perm.FORUM_MODERATE: "Moderate discussions",
    Perm.FEEDBACK_SUBMIT: "Submit feedback",
    Perm.FEEDBACK_MANAGE: "Create feedback forms and view results",
    Perm.ANALYTICS_VIEW_SELF: "View own analytics",
    Perm.ANALYTICS_VIEW_COURSE: "View course analytics",
    Perm.ANALYTICS_VIEW_DEPARTMENT: "View department analytics",
    Perm.ANALYTICS_VIEW_INSTITUTION: "View institution-wide analytics",
    Perm.RISK_VIEW: "View academic support risk indicators",
    Perm.RISK_CONFIGURE: "Configure risk rules",
    Perm.RESEARCH_VIEW: "View research records",
    Perm.RESEARCH_MANAGE: "Manage research projects and publications",
    Perm.ALUMNI_VIEW: "View alumni directory",
    Perm.ALUMNI_MANAGE: "Manage alumni records",
    Perm.MENTORSHIP_PARTICIPATE: "Send or receive mentorship requests",
    Perm.JOB_VIEW: "View jobs and internships",
    Perm.JOB_MANAGE: "Post jobs and internships",
    Perm.LIBRARY_VIEW: "View e-resources",
    Perm.LIBRARY_MANAGE: "Manage e-resources",
    Perm.CERTIFICATE_VIEW: "View certificates",
    Perm.CERTIFICATE_MANAGE: "Issue certificates",
    Perm.REPORT_EXPORT: "Export reports",
    Perm.AUDIT_VIEW: "View audit logs",
    Perm.SETTINGS_MANAGE: "Manage system settings and branding",
}

ALL_PERMISSIONS = sorted(PERMISSION_LABELS.keys())

#: Baseline every signed-in user holds, whatever their role.
_COMMON = [
    Perm.ANNOUNCEMENT_VIEW,
    Perm.EVENT_VIEW,
    Perm.LIBRARY_VIEW,
    Perm.CERTIFICATE_VIEW,
]

#: Seeing one's *own* attendance and marks. Held by every role that has an
#: academic record - which excludes alumni, who have graduated out of one.
#: The queryset scoping in each view decides what "own" resolves to.
_ACADEMIC_BASE = _COMMON + [
    Perm.ATTENDANCE_VIEW_OWN,
    Perm.MARKS_VIEW_OWN,
]

#: Default role -> permission mapping. Overridable per deployment.
DEFAULT_ROLE_PERMISSIONS = {
    # The Dean is read-heavy: institutional oversight, no routine grading.
    Roles.DEAN: _ACADEMIC_BASE
    + [
        Perm.USER_VIEW,
        Perm.DEPARTMENT_VIEW,
        Perm.COURSE_VIEW,
        Perm.NOTE_VIEW,
        Perm.ASSIGNMENT_VIEW,
        Perm.ATTENDANCE_VIEW_ALL,
        Perm.MARKS_VIEW_ALL,
        Perm.ANNOUNCEMENT_MANAGE,
        Perm.ANALYTICS_VIEW_COURSE,
        Perm.ANALYTICS_VIEW_DEPARTMENT,
        Perm.ANALYTICS_VIEW_INSTITUTION,
        Perm.RISK_VIEW,
        Perm.RESEARCH_VIEW,
        Perm.ALUMNI_VIEW,
        Perm.JOB_VIEW,
        Perm.FEEDBACK_MANAGE,
        Perm.REPORT_EXPORT,
        Perm.AUDIT_VIEW,
    ],
    Roles.ADMIN: _ACADEMIC_BASE
    + [
        Perm.USER_VIEW,
        Perm.USER_MANAGE,
        Perm.ROLE_MANAGE,
        Perm.DEPARTMENT_VIEW,
        Perm.DEPARTMENT_MANAGE,
        Perm.ACADEMIC_MANAGE,
        Perm.COURSE_VIEW,
        Perm.COURSE_MANAGE,
        Perm.ENROLLMENT_MANAGE,
        Perm.NOTE_VIEW,
        Perm.NOTE_MANAGE,
        Perm.QUESTION_VIEW,
        Perm.QUESTION_MANAGE,
        Perm.ASSIGNMENT_VIEW,
        Perm.ASSIGNMENT_MANAGE,
        Perm.ATTENDANCE_VIEW_ALL,
        Perm.ATTENDANCE_MARK,
        Perm.ATTENDANCE_CONFIGURE,
        Perm.MARKS_VIEW_ALL,
        Perm.MARKS_ENTER,
        Perm.MARKS_PUBLISH,
        Perm.MARKS_CONFIGURE,
        Perm.EXTERNAL_MARKS_ENTER,
        Perm.ANNOUNCEMENT_MANAGE,
        Perm.EVENT_MANAGE,
        Perm.FORUM_PARTICIPATE,
        Perm.FORUM_MODERATE,
        Perm.FEEDBACK_MANAGE,
        Perm.ANALYTICS_VIEW_COURSE,
        Perm.ANALYTICS_VIEW_DEPARTMENT,
        Perm.RISK_VIEW,
        Perm.RISK_CONFIGURE,
        Perm.RESEARCH_VIEW,
        Perm.RESEARCH_MANAGE,
        Perm.ALUMNI_VIEW,
        Perm.ALUMNI_MANAGE,
        Perm.JOB_VIEW,
        Perm.JOB_MANAGE,
        Perm.LIBRARY_MANAGE,
        Perm.CERTIFICATE_MANAGE,
        Perm.REPORT_EXPORT,
        Perm.AUDIT_VIEW,
        Perm.SETTINGS_MANAGE,
    ],
    Roles.FACULTY: _ACADEMIC_BASE
    + [
        Perm.USER_VIEW,
        Perm.DEPARTMENT_VIEW,
        Perm.COURSE_VIEW,
        Perm.COURSE_TEACH,
        Perm.NOTE_VIEW,
        Perm.NOTE_MANAGE,
        Perm.QUESTION_VIEW,
        Perm.QUESTION_MANAGE,
        Perm.ASSIGNMENT_VIEW,
        Perm.ASSIGNMENT_MANAGE,
        Perm.ASSIGNMENT_GRADE,
        Perm.ATTENDANCE_VIEW_ALL,
        Perm.ATTENDANCE_MARK,
        Perm.MARKS_VIEW_ALL,
        Perm.MARKS_ENTER,
        Perm.ANNOUNCEMENT_MANAGE,
        Perm.EVENT_MANAGE,
        Perm.FORUM_PARTICIPATE,
        Perm.FORUM_MODERATE,
        Perm.FEEDBACK_SUBMIT,
        Perm.ANALYTICS_VIEW_COURSE,
        Perm.RISK_VIEW,
        Perm.RESEARCH_VIEW,
        Perm.ALUMNI_VIEW,
        Perm.JOB_VIEW,
        Perm.REPORT_EXPORT,
    ],
    Roles.SCHOLAR: _ACADEMIC_BASE
    + [
        Perm.COURSE_VIEW,
        Perm.COURSE_TEACH,
        Perm.NOTE_VIEW,
        Perm.NOTE_MANAGE,
        Perm.QUESTION_VIEW,
        Perm.ASSIGNMENT_VIEW,
        Perm.ATTENDANCE_MARK,
        Perm.ATTENDANCE_VIEW_ALL,
        Perm.FORUM_PARTICIPATE,
        Perm.FORUM_MODERATE,
        Perm.FEEDBACK_SUBMIT,
        Perm.ANALYTICS_VIEW_SELF,
        Perm.RESEARCH_VIEW,
        Perm.RESEARCH_MANAGE,
        Perm.MENTORSHIP_PARTICIPATE,
        Perm.ALUMNI_VIEW,
        Perm.JOB_VIEW,
    ],
    Roles.STUDENT: _ACADEMIC_BASE
    + [
        Perm.COURSE_VIEW,
        Perm.NOTE_VIEW,
        Perm.QUESTION_VIEW,
        Perm.ASSIGNMENT_VIEW,
        Perm.ASSIGNMENT_SUBMIT,
        Perm.ATTENDANCE_VIEW_OWN,
        Perm.MARKS_VIEW_OWN,
        Perm.FORUM_PARTICIPATE,
        Perm.FEEDBACK_SUBMIT,
        Perm.ANALYTICS_VIEW_SELF,
        Perm.JOB_VIEW,
    ],
    Roles.ALUMNI: _COMMON
    + [
        Perm.ALUMNI_VIEW,
        Perm.MENTORSHIP_PARTICIPATE,
        Perm.JOB_VIEW,
        Perm.JOB_MANAGE,
        Perm.FEEDBACK_SUBMIT,
    ],
}


def default_permissions_for(role: str) -> list:
    return sorted(set(DEFAULT_ROLE_PERMISSIONS.get(role, [])))
