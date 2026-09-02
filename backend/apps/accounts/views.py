"""Authentication and user administration endpoints."""
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import (
    AlumniProfile,
    LoginAttempt,
    PasswordResetToken,
    RolePermission,
    User,
)
from apps.accounts.serializers import (
    AlumniProfileSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PreferencesSerializer,
    RolePermissionSerializer,
    UserSerializer,
    UserWriteSerializer,
)
from apps.auditlogs import services as audit
from apps.auditlogs.middleware import get_client_ip
from apps.auditlogs.models import AuditAction
from apps.core.permissions import HasPerm
from apps.core.rbac import ALL_PERMISSIONS, PERMISSION_LABELS, Perm, Roles
from apps.core.viewsets import AuditedModelViewSet


def set_refresh_cookie(response, refresh_token):
    """Refresh tokens live in an httpOnly cookie so JavaScript cannot read them."""
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        str(refresh_token),
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path="/api/v1/auth",
    )
    return response


def issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["name"] = user.full_name
    return refresh


class LoginView(APIView):
    """POST /api/v1/auth/login"""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower().strip()
        password = serializer.validated_data["password"]
        ip = get_client_ip(request)

        # Brute-force lockout: too many recent failures for this address.
        window_start = timezone.now() - timezone.timedelta(
            minutes=settings.LOGIN_LOCKOUT_MINUTES
        )
        recent_failures = LoginAttempt.objects.filter(
            email=email, successful=False, created_at__gte=window_start
        ).count()
        if recent_failures >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
            audit.record(
                AuditAction.LOGIN_FAILED,
                description="Login blocked - too many attempts",
                metadata={"email": email},
            )
            return Response(
                {
                    "error": {
                        "code": "account_locked",
                        "message": "Too many failed attempts. Try again in %s minutes."
                        % settings.LOGIN_LOCKOUT_MINUTES,
                    }
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        user = authenticate(request, username=email, password=password)
        LoginAttempt.objects.create(
            email=email,
            ip_address=ip,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
            successful=bool(user),
        )

        if user is None:
            audit.record(
                AuditAction.LOGIN_FAILED,
                description="Failed login",
                metadata={"email": email},
            )
            # Identical message whether the account exists or not.
            return Response(
                {"error": {"code": "invalid_credentials", "message": "Invalid email or password."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {
                    "error": {
                        "code": "account_disabled",
                        "message": "This account has been deactivated. Contact your administrator.",
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        LoginAttempt.objects.filter(email=email, successful=False).delete()
        user.last_active_at = timezone.now()
        user.save(update_fields=["last_active_at"])
        audit.record(AuditAction.LOGIN, actor=user, description="Successful login")

        refresh = issue_tokens(user)
        response = Response(
            {
                "access": str(refresh.access_token),
                "user": UserSerializer(user).data,
                "must_change_password": user.must_change_password,
            }
        )
        return set_refresh_cookie(response, refresh)


class RefreshView(APIView):
    """POST /api/v1/auth/refresh - reads the httpOnly cookie, or a body token."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME) or request.data.get("refresh")
        if not raw:
            return Response(
                {"error": {"code": "authentication_required", "message": "No active session."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            refresh = RefreshToken(raw)
            access = str(refresh.access_token)
            user = User.objects.filter(pk=refresh.get("user_id"), is_active=True).first()
            if user is None:
                raise TokenError("User is not available.")
            payload = {"access": access, "user": UserSerializer(user).data}
            response = Response(payload)
            if settings.SIMPLE_JWT.get("ROTATE_REFRESH_TOKENS"):
                try:
                    refresh.blacklist()
                except AttributeError:
                    pass
                new_refresh = issue_tokens(user)
                response.data["access"] = str(new_refresh.access_token)
                set_refresh_cookie(response, new_refresh)
            return response
        except TokenError:
            response = Response(
                {"error": {"code": "session_expired", "message": "Your session has expired."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/api/v1/auth")
            return response


class LogoutView(APIView):
    """POST /api/v1/auth/logout"""

    permission_classes = [AllowAny]

    def post(self, request):
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME) or request.data.get("refresh")
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except (TokenError, AttributeError):
                pass
        if request.user and request.user.is_authenticated:
            audit.record(AuditAction.LOGOUT, actor=request.user, description="Logout")
        response = Response({"detail": "Signed out."})
        response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/api/v1/auth")
        return response


class MeView(APIView):
    """GET/PATCH /api/v1/auth/me"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = PreferencesSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        audit.record(AuditAction.PASSWORD_CHANGE, actor=user, description="Password changed")
        return Response({"detail": "Password updated."})


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        user = User.objects.filter(email=email, is_active=True).first()
        if user:
            raw_token = PasswordResetToken.issue(user)
            link = "%s/reset-password?token=%s" % (settings.FRONTEND_BASE_URL, raw_token)
            send_mail(
                subject="Reset your Public Health LMS password",
                message=(
                    "Hello %s,\n\nUse the link below to set a new password. "
                    "It expires in 2 hours.\n\n%s\n\nIf you did not request this, ignore this email."
                    % (user.full_name, link)
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        # Always the same response - never reveal whether an account exists.
        return Response(
            {"detail": "If an account exists for that address, a reset link has been sent."}
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = PasswordResetToken.resolve(serializer.validated_data["token"])
        if token is None:
            return Response(
                {"error": {"code": "invalid_token", "message": "This reset link is invalid or has expired."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = token.user
        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        token.consume()
        audit.record(AuditAction.PASSWORD_RESET, actor=user, description="Password reset completed")
        return Response({"detail": "Your password has been reset. You can now sign in."})


class UserViewSet(AuditedModelViewSet):
    """/api/v1/users - administrator user management (brief section 84)."""

    queryset = User.objects.select_related("department").all()
    required_permission = Perm.USER_VIEW
    required_write_permission = Perm.USER_MANAGE
    filterset_fields = ["role", "department", "is_active"]
    search_fields = ["full_name", "email", "student_profile__enrollment_number"]
    ordering_fields = ["full_name", "date_joined", "role"]
    audit_object_type = "user"

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return UserWriteSerializer
        return UserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        # Department admins only see their own department.
        if user.role == Roles.ADMIN and user.department_id:
            qs = qs.filter(Q(department=user.department) | Q(pk=user.pk))
        return qs

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        user = self.get_object()
        if user.pk == request.user.pk:
            return Response(
                {"error": {"code": "invalid_operation", "message": "You cannot deactivate your own account."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = False
        user.deactivated_at = timezone.now()
        user.save(update_fields=["is_active", "deactivated_at"])
        audit.record(AuditAction.UPDATE, obj=user, description="Account deactivated")
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.deactivated_at = None
        user.save(update_fields=["is_active", "deactivated_at"])
        audit.record(AuditAction.UPDATE, obj=user, description="Account activated")
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="reset-password")
    def admin_reset_password(self, request, pk=None):
        from django.utils.crypto import get_random_string

        user = self.get_object()
        temporary = get_random_string(12)
        user.set_password(temporary)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password"])
        audit.record(AuditAction.PASSWORD_RESET, obj=user, description="Administrator reset password")
        return Response(
            {
                "detail": "A temporary password has been generated. Share it securely; "
                "the user must change it at next sign-in.",
                "temporary_password": temporary,
            }
        )

    @action(detail=True, methods=["post"], url_path="change-role")
    def change_role(self, request, pk=None):
        if not request.user.has_perm_code(Perm.ROLE_MANAGE):
            return Response(
                {"error": {"code": "permission_denied", "message": "You cannot change roles."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        user = self.get_object()
        new_role = request.data.get("role")
        if new_role not in Roles.ALL:
            return Response(
                {"error": {"code": "validation_error", "message": "Unknown role."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        previous = user.role
        user.role = new_role
        user.save(update_fields=["role"])
        audit.record(
            AuditAction.ROLE_CHANGE,
            obj=user,
            description="Role changed from %s to %s" % (previous, new_role),
            metadata={"from": previous, "to": new_role},
        )
        return Response(UserSerializer(user).data)


class RolePermissionViewSet(viewsets.ModelViewSet):
    """/api/v1/roles/permissions - configure the RBAC matrix."""

    queryset = RolePermission.objects.all()
    serializer_class = RolePermissionSerializer
    permission_classes = [IsAuthenticated, HasPerm]
    required_permission = Perm.ROLE_MANAGE
    required_write_permission = Perm.ROLE_MANAGE
    filterset_fields = ["role"]
    pagination_class = None

    @action(detail=False, methods=["get"], url_path="catalogue")
    def catalogue(self, request):
        """The full permission catalogue plus each role's effective grants."""
        from apps.core.rbac import default_permissions_for

        effective = {}
        for role in Roles.ALL:
            overrides = RolePermission.objects.filter(role=role)
            if overrides.exists():
                effective[role] = sorted(
                    overrides.filter(is_granted=True).values_list("permission_code", flat=True)
                )
            else:
                effective[role] = default_permissions_for(role)
        return Response(
            {
                "permissions": [
                    {"code": code, "label": PERMISSION_LABELS[code], "domain": code.split(".")[0]}
                    for code in ALL_PERMISSIONS
                ],
                "roles": [{"code": code, "label": label} for code, label in Roles.CHOICES],
                "matrix": effective,
            }
        )

    @action(detail=False, methods=["post"], url_path="bulk-set")
    def bulk_set(self, request):
        """Replace one role's permission set in a single call."""
        role = request.data.get("role")
        codes = request.data.get("permissions", [])
        if role not in Roles.ALL:
            return Response(
                {"error": {"code": "validation_error", "message": "Unknown role."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        unknown = [code for code in codes if code not in ALL_PERMISSIONS]
        if unknown:
            return Response(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "Unknown permission codes: %s" % ", ".join(unknown),
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        RolePermission.objects.filter(role=role).delete()
        RolePermission.objects.bulk_create(
            [RolePermission(role=role, permission_code=code, is_granted=True) for code in codes]
        )
        audit.record(
            AuditAction.SETTINGS_CHANGE,
            description="Permissions updated for role %s" % role,
            metadata={"role": role, "count": len(codes)},
        )
        return Response({"role": role, "permissions": sorted(codes)})


class AlumniProfileViewSet(AuditedModelViewSet):
    """/api/v1/alumni/profiles - directory with privacy filtering."""

    queryset = AlumniProfile.objects.select_related("user", "program").all()
    serializer_class = AlumniProfileSerializer
    required_permission = Perm.ALUMNI_VIEW
    required_write_permission = Perm.ALUMNI_MANAGE
    filterset_fields = ["graduation_year", "program", "is_available_for_mentorship"]
    search_fields = ["user__full_name", "current_organization", "job_title", "location"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.has_perm_code(Perm.ALUMNI_MANAGE):
            qs = qs.filter(Q(show_in_directory=True) | Q(user=user))
        return qs
