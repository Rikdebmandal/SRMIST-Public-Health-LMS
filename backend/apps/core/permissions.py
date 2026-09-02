"""DRF permission classes that enforce RBAC on the server.

Frontend route guards are a convenience only - every protected endpoint runs
through one of these classes (brief section 9).
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.core.rbac import Perm, Roles


class HasPerm(BasePermission):
    """Requires a single permission code declared on the view.

    Usage::

        class CourseViewSet(...):
            permission_classes = [IsAuthenticated, HasPerm]
            required_permission = Perm.COURSE_VIEW
            required_write_permission = Perm.COURSE_MANAGE
            # Custom actions that need something other than the write permission:
            action_permissions = {"enrol": Perm.ENROLLMENT_MANAGE}

    Without ``action_permissions`` a custom POST action inherits the viewset's
    write permission, which is wrong whenever the action is meant for a
    different audience - a student submitting feedback on a form only staff can
    edit, or a marker grading a submission only students can create.
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False

        overrides = getattr(view, "action_permissions", None) or {}
        action = getattr(view, "action", None)
        if action in overrides:
            code = overrides[action]
            return code is None or user.has_perm_code(code)

        if request.method in SAFE_METHODS:
            code = getattr(view, "required_permission", None)
        else:
            code = getattr(view, "required_write_permission", None) or getattr(
                view, "required_permission", None
            )
        if code is None:
            return True
        return user.has_perm_code(code)


class HasAnyPerm(BasePermission):
    """Allows access when the user holds any of `required_permissions`."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        codes = getattr(view, "required_permissions", None)
        if not codes:
            return True
        return any(user.has_perm_code(code) for code in codes)


class IsRole(BasePermission):
    """Allows access to an explicit list of roles declared on the view."""

    def has_permission(self, request, view):
        user = request.user
        allowed = getattr(view, "allowed_roles", Roles.ALL)
        return bool(user and user.is_authenticated and user.role in allowed)


class IsStaffRole(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in Roles.STAFF)


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


class IsOwnerOrHasPerm(BasePermission):
    """Object-level guard preventing IDOR.

    An object is accessible when the requester owns it (via the attribute named
    by ``owner_field``) or holds ``override_permission``.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        owner_field = getattr(view, "owner_field", "user")
        override = getattr(view, "override_permission", None)
        owner = obj
        for part in owner_field.split("."):
            owner = getattr(owner, part, None)
            if owner is None:
                break
        if owner is not None and getattr(owner, "pk", None) == user.pk:
            return True
        return bool(override and user.has_perm_code(override))


def can_manage_department(user, department_id) -> bool:
    """Department scoping: admins are bound to their own department."""
    if user.role == Roles.DEAN or user.is_superuser:
        return True
    if user.role == Roles.ADMIN:
        return user.department_id is not None and str(user.department_id) == str(department_id)
    return False


def teaches_section(user, section) -> bool:
    """True when the user is assigned to teach the given course section."""
    if user.is_superuser or user.role in (Roles.ADMIN, Roles.DEAN):
        return True
    if section is None:
        return False
    return section.faculty_assignments.filter(faculty=user, is_active=True).exists()


def visible_student_ids(user):
    """Queryset of student user ids the requester may legitimately see."""
    from apps.accounts.models import User
    from apps.courses.models import Enrollment

    if user.is_superuser or user.role in (Roles.DEAN,):
        return User.objects.filter(role=Roles.STUDENT).values_list("id", flat=True)
    if user.role == Roles.ADMIN:
        return User.objects.filter(role=Roles.STUDENT, department=user.department).values_list(
            "id", flat=True
        )
    if user.role in (Roles.FACULTY, Roles.SCHOLAR):
        return (
            Enrollment.objects.filter(
                section__faculty_assignments__faculty=user,
                section__faculty_assignments__is_active=True,
                status=Enrollment.Status.ACTIVE,
            )
            .values_list("student_id", flat=True)
            .distinct()
        )
    return User.objects.filter(pk=user.pk).values_list("id", flat=True)


__all__ = [
    "HasPerm",
    "HasAnyPerm",
    "IsRole",
    "IsStaffRole",
    "ReadOnly",
    "IsOwnerOrHasPerm",
    "can_manage_department",
    "teaches_section",
    "visible_student_ids",
    "Perm",
    "Roles",
]
