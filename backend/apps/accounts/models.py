"""Identity, roles and role-specific profiles (brief sections 8, 9, 83)."""
import hashlib
import secrets
import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel, TimeStampedModel
from apps.core.rbac import ALL_PERMISSIONS, Roles, default_permissions_for


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", Roles.ADMIN)
        extra.setdefault("full_name", "System Administrator")
        if extra.get("is_staff") is not True:
            raise ValueError("Superusers must have is_staff=True.")
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Single user table for every role.

    Role-specific attributes live in the four profile models below so the core
    table stays lean and new roles can be added without a schema rewrite.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(r"^[0-9+\-\s()]{6,20}$", "Enter a valid phone number.")],
    )
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", null=True, blank=True)
    role = models.CharField(max_length=20, choices=Roles.CHOICES, default=Roles.STUDENT, db_index=True)
    department = models.ForeignKey(
        "academics.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
    )
    bio = models.TextField(blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    is_staff = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)

    # Preferences (brief sections 43, 63, 65)
    theme_preference = models.CharField(
        max_length=10,
        choices=[("light", "Light"), ("dark", "Dark"), ("system", "System")],
        default="system",
    )
    locale = models.CharField(max_length=10, default="en")
    timezone_name = models.CharField(max_length=64, default="Asia/Kolkata")

    date_joined = models.DateTimeField(default=timezone.now)
    last_active_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["role", "is_active"]),
            models.Index(fields=["department", "role"]),
        ]

    def __str__(self):
        return "%s (%s)" % (self.full_name, self.get_role_display())

    # -- RBAC ---------------------------------------------------------------
    @property
    def permission_codes(self) -> set:
        """Effective permissions: DB overrides, falling back to the defaults."""
        if self.is_superuser:
            return set(ALL_PERMISSIONS)
        overrides = RolePermission.objects.filter(role=self.role)
        if overrides.exists():
            return set(overrides.filter(is_granted=True).values_list("permission_code", flat=True))
        return set(default_permissions_for(self.role))

    def has_perm_code(self, code: str) -> bool:
        return self.is_superuser or code in self.permission_codes

    @property
    def initials(self) -> str:
        parts = [p for p in self.full_name.split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    def touch_activity(self):
        self.last_active_at = timezone.now()
        self.save(update_fields=["last_active_at"])


class RolePermission(TimeStampedModel):
    """Administrator-editable override of the default role permission map."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=Roles.CHOICES, db_index=True)
    permission_code = models.CharField(max_length=64)
    is_granted = models.BooleanField(default=True)

    class Meta:
        unique_together = [("role", "permission_code")]
        ordering = ["role", "permission_code"]

    def __str__(self):
        return "%s -> %s" % (self.role, self.permission_code)


class StudentProfile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    enrollment_number = models.CharField(max_length=30, unique=True)
    program = models.ForeignKey(
        "academics.Program", null=True, blank=True, on_delete=models.SET_NULL, related_name="students"
    )
    batch = models.ForeignKey(
        "academics.Batch", null=True, blank=True, on_delete=models.SET_NULL, related_name="students"
    )
    current_semester = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1)]
    )
    admission_date = models.DateField(null=True, blank=True)
    guardian_name = models.CharField(max_length=150, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ["enrollment_number"]

    def __str__(self):
        return "%s - %s" % (self.enrollment_number, self.user.full_name)


class FacultyProfile(BaseModel):
    class Designation(models.TextChoices):
        PROFESSOR = "PROFESSOR", "Professor"
        ASSOCIATE = "ASSOCIATE", "Associate Professor"
        ASSISTANT = "ASSISTANT", "Assistant Professor"
        LECTURER = "LECTURER", "Lecturer"
        VISITING = "VISITING", "Visiting Faculty"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="faculty_profile")
    employee_id = models.CharField(max_length=30, unique=True)
    designation = models.CharField(
        max_length=20, choices=Designation.choices, default=Designation.ASSISTANT
    )
    specialization = models.CharField(max_length=200, blank=True)
    qualification = models.CharField(max_length=200, blank=True)
    date_of_joining = models.DateField(null=True, blank=True)
    office_location = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return "%s - %s" % (self.employee_id, self.user.full_name)


class ScholarProfile(BaseModel):
    class ScholarType(models.TextChoices):
        FULL_TIME = "FULL_TIME", "Full time"
        PART_TIME = "PART_TIME", "Part time"
        EXTERNAL = "EXTERNAL", "External"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="scholar_profile")
    registration_number = models.CharField(max_length=30, unique=True)
    research_area = models.CharField(max_length=250)
    supervisor = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="supervised_scholars"
    )
    scholar_type = models.CharField(
        max_length=20, choices=ScholarType.choices, default=ScholarType.FULL_TIME
    )
    enrolment_year = models.PositiveSmallIntegerField(null=True, blank=True)
    is_teaching_assistant = models.BooleanField(default=False)
    thesis_title = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return "%s - %s" % (self.registration_number, self.user.full_name)


class AlumniProfile(BaseModel):
    """Alumni records carry per-field privacy switches (brief section 34)."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="alumni_profile")
    graduation_year = models.PositiveSmallIntegerField()
    program = models.ForeignKey(
        "academics.Program", null=True, blank=True, on_delete=models.SET_NULL, related_name="alumni"
    )
    current_organization = models.CharField(max_length=200, blank=True)
    job_title = models.CharField(max_length=150, blank=True)
    location = models.CharField(max_length=150, blank=True)
    skills = models.JSONField(default=list, blank=True)
    linkedin_url = models.URLField(blank=True)
    website_url = models.URLField(blank=True)
    is_available_for_mentorship = models.BooleanField(default=False)
    mentorship_areas = models.JSONField(default=list, blank=True)

    # Privacy controls
    show_email = models.BooleanField(default=False)
    show_phone = models.BooleanField(default=False)
    show_in_directory = models.BooleanField(default=True)

    class Meta:
        ordering = ["-graduation_year", "user__full_name"]

    def __str__(self):
        return "%s (%s)" % (self.user.full_name, self.graduation_year)


class LoginAttempt(models.Model):
    """Brute-force tracking (brief section 7)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    successful = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["email", "successful", "created_at"])]


class PasswordResetToken(models.Model):
    """Only the SHA-256 hash of the token is ever stored."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reset_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def issue(cls, user, ttl_hours: int = 2):
        raw = secrets.token_urlsafe(48)
        cls.objects.create(
            user=user,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=timezone.now() + timezone.timedelta(hours=ttl_hours),
        )
        return raw

    @classmethod
    def resolve(cls, raw_token):
        digest = hashlib.sha256((raw_token or "").encode()).hexdigest()
        return cls.objects.filter(
            token_hash=digest, used_at__isnull=True, expires_at__gt=timezone.now()
        ).first()

    def consume(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])
