# Security and privacy

Academic records are sensitive. This document states what is protected, how, and
what is deliberately not claimed.

## Threat model

The realistic attackers against a university LMS are not sophisticated:

| Threat | Control |
| --- | --- |
| A student reading a classmate's marks or attendance | Object-level checks on every id-addressed endpoint; queryset scoping on every list |
| A student escalating their own role | `role.manage` is required and never granted to students; the change is audited |
| Faculty reaching a section they do not teach | `teaches_section()` on gradebook, register, roster and marking endpoints |
| Guessing ids to enumerate records | UUID primary keys; out-of-scope records return `404`, not `403` |
| Password guessing | Per-address lockout after 5 failures, plus a 10/min login throttle |
| Session theft from XSS | Refresh token in an httpOnly cookie; access token in memory, never `localStorage` |
| Malicious file upload | Extension allow-list, executable deny-list, size cap, MIME check, magic-number sniffing |
| Quietly altering published marks | Publication locks the row; corrections need `marks.publish` and are audited |
| Covering tracks | `AuditLog.save()` and `delete()` raise on any modification |

## Authentication

- Passwords hashed with Django's PBKDF2 (default `PASSWORD_HASHERS`). No
  plaintext password is stored, logged or written to an audit entry.
- Access tokens live 30 minutes; refresh tokens 7 days, rotated on use with the
  previous token blacklisted.
- The refresh token is an httpOnly, `SameSite=Lax` cookie scoped to
  `/api/v1/auth`, and `Secure` outside `DEBUG`. JavaScript cannot read it.
- The access token is held in a module-level variable in the browser, never in
  `localStorage` or `sessionStorage`, so an XSS payload cannot exfiltrate it
  from storage.
- Failed and successful logins are both recorded, with IP and user agent.
- Login failures return an identical message whether or not the account exists.
- Password reset tokens are stored only as SHA-256 hashes, expire in two hours
  and are single-use. The reset request endpoint always returns the same
  response, so it cannot be used to enumerate accounts.

## Authorisation

Four independent layers, described in [ARCHITECTURE.md](ARCHITECTURE.md):
view permission, queryset scoping, object-level guards, serializer validation.

The permission catalogue lives in `apps/core/rbac.py` — 50 codes across ten
domains. `RolePermission` rows override the defaults at runtime.

Two deliberate role decisions:

- **The Dean cannot manage users or grade.** The role is read-heavy oversight by
  design (brief section 8.1), so institutional analytics do not come bundled
  with the ability to alter records.
- **Alumni hold no academic-record permissions.** They have graduated out of
  having attendance or marks, so those permissions are absent rather than
  present-but-empty.

Attempts to read another student's data are written to the audit log with
`PERMISSION_DENIED`, so probing leaves a trail.

## Input validation and injection

- The Django ORM parameterises every query; there is no string-built SQL.
- DRF serializers validate type, range and business rules server-side. Frontend
  Zod schemas are a usability layer, not a control.
- React escapes rendered values by default; no `dangerouslySetInnerHTML` is used.
- `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS = DENY` and a same-origin
  referrer policy are set. HSTS, SSL redirect and secure cookies switch on when
  `DEBUG` is off.
- CORS is an explicit origin allow-list, not a wildcard, and credentials are
  permitted only for those origins.

## File uploads

`apps/core/validators.py` runs four checks in order:

1. **Extension allow-list** — configurable per assignment, with a global default.
2. **Executable deny-list** — `.exe`, `.js`, `.php`, `.sh` and friends are
   refused regardless of configuration.
3. **Size limit** — per-assignment or the global `MAX_UPLOAD_SIZE_MB`.
4. **Content verification** — the declared MIME type must match the extension,
   and for PDF, PNG, JPEG, GIF and ZIP-based formats the magic-number prefix is
   checked. A renamed executable fails here.

Uploads are stored outside the database. Filenames are sanitised against
directory traversal.

## Data protection

| Rule | Implementation |
| --- | --- |
| A student sees only their own record | Queryset filters plus object-level checks on marks, attendance, scores and risk |
| Unpublished marks are invisible to students | Score querysets filter on `status=PUBLISHED` for non-staff |
| Anonymous feedback stays anonymous | `respondent` is `NULL`; participation is tracked in a separate table |
| Small-sample feedback is withheld | Results hidden below three responses |
| Alumni contact details stay private | Per-field privacy switches; the directory excludes opted-out profiles |
| Search cannot leak | Every source in global search reuses its own permission-scoped queryset |
| Exports are checked before generation | Permission and section assignment verified before the first row is written; every export is audited |
| Credentials never reach logs | `scrub()` redacts password, token, secret and key fields recursively |
| Analytics avoid unnecessary identifiers | The correlation scatter plots enrolment numbers, not names |

## Audit trail

`AuditLog` records login, logout, failed login, password change and reset, role
change, mark and attendance modification, publication, file upload and deletion,
export, settings change and denied permission attempts.

Each entry keeps actor id, email, role, action, object type and id, description,
scrubbed metadata, IP and user agent. The email and role are duplicated as plain
text so history survives account deletion.

The model refuses updates and deletes at the application layer. Altering history
requires direct database access, which is the point.

## Responsible analytics

The Academic Support Risk Indicator is a rule-based signal for human review, not
a prediction and not a judgement of ability. Concretely:

- Every response carries the disclaimer, and the UI renders it beside the score.
- Every contributing factor shows the observed value and the threshold crossed.
- Rules use academic behaviour only — attendance, submissions, scores, activity.
  No demographic proxy is available to the engine.
- `RiskSnapshot` supports a human review note, so intervention is recorded.
- Nothing in the system acts on a risk score automatically. It surfaces students
  to staff; staff decide.

## What is not claimed

- No penetration test or third-party audit has been performed.
- No multi-factor authentication. The architecture leaves room for institutional
  SSO but none is implemented.
- No field-level encryption at rest beyond what the database provides.
- Rate limiting is per-process in-memory by default; a multi-instance deployment
  needs the Redis cache backend for it to be effective.
- The PWA does not cache API data offline, and does not claim to.

## Deployment checklist

- [ ] `DJANGO_SECRET_KEY` set to a fresh random value, not the development default
- [ ] `DJANGO_DEBUG=false`
- [ ] `DJANGO_ALLOWED_HOSTS` restricted to real hostnames
- [ ] `CORS_ALLOWED_ORIGINS` restricted to the real frontend origin
- [ ] `DATABASE_URL` pointing at PostgreSQL with a least-privilege role
- [ ] TLS terminated in front of the app; HSTS active
- [ ] `REDIS_URL` set so throttling and caching work across instances
- [ ] SMTP configured; console email backend disabled
- [ ] Media on S3-compatible storage with private ACLs
- [ ] Database backups scheduled **and a restore tested**
- [ ] Error monitoring wired up (Sentry or equivalent)

Report a vulnerability privately to the project maintainer rather than opening a
public issue.
