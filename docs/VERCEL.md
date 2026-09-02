# Deploying to Vercel

Vercel hosts the **frontend**. The Django backend has to live somewhere that
runs persistent processes.

## Why the split

Vercel is serverless: functions spin up per request and die. The backend needs
three things that model cannot provide.

| Requirement | Why serverless does not work |
| --- | --- |
| Celery worker and beat | Long-running processes; there is nothing to keep alive between requests |
| Uploaded files (notes, submissions, certificates) | No persistent filesystem; anything written disappears |
| Database connections | Connection churn per invocation exhausts a Postgres connection pool |

Django *can* be forced onto Vercel functions, but the weekly digest, deadline
reminders, attendance alerts and file uploads would all break. Put the API on a
platform with real processes instead.

| Piece | Platform | Cost at small scale |
| --- | --- | --- |
| Next.js frontend | Vercel | Free (Hobby) |
| Django API + Celery | Railway, Render or Fly.io | Free–$5/mo |
| PostgreSQL | Neon, Supabase or the platform's addon | Free tier |
| Media storage | Cloudflare R2 or AWS S3 | Free–pennies |

---

## Step 1 — Deploy the backend first

The frontend needs the API URL at build time, so do this first.

### Railway (simplest path)

1. **railway.app** → New Project → Deploy from GitHub → pick
   `SRMIST-Public-Health-LMS`.
2. Settings → **Root Directory**: `backend`.
3. Add a **PostgreSQL** service and a **Redis** service from the same project.
   Railway injects `DATABASE_URL` and `REDIS_URL` automatically.
4. Set the start command:

   ```
   python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
   ```

5. Add the environment variables in the table below.
6. Add two more services from the same repo for the background jobs, each with
   root directory `backend` and the same variables:

   ```
   celery -A config worker --loglevel=info
   celery -A config beat   --loglevel=info
   ```

7. Generate a public domain. Note it — for example
   `srmist-lms-api.up.railway.app`.

### Backend environment variables

```bash
DJANGO_SECRET_KEY=<64 random chars — see below>
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=srmist-lms-api.up.railway.app

# Your Vercel URL, once you have it (step 2)
CORS_ALLOWED_ORIGINS=https://srmist-public-health-lms.vercel.app
CSRF_TRUSTED_ORIGINS=https://srmist-public-health-lms.vercel.app
FRONTEND_BASE_URL=https://srmist-public-health-lms.vercel.app

# CRITICAL — see the cross-site cookie note below
REFRESH_COOKIE_SAMESITE=None
REFRESH_COOKIE_SECURE=true

TIME_ZONE=Asia/Kolkata
```

Generate the secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Then seed the demo data once, from the platform's shell:

```bash
python manage.py seed_demo --reset
```

---

## Step 2 — Deploy the frontend to Vercel

1. **vercel.com** → Add New → Project → import
   `Rikdebmandal/SRMIST-Public-Health-LMS`.
2. **Root Directory**: `frontend` ← this is the setting people miss. Without it
   Vercel looks for a Next.js app at the repo root and the build fails.
3. Framework preset: Next.js (auto-detected).
4. Add one environment variable:

   | Name | Value |
   | --- | --- |
   | `NEXT_PUBLIC_API_URL` | `https://srmist-lms-api.up.railway.app` |

   No trailing slash.

5. Deploy.

`NEXT_PUBLIC_*` variables are **inlined at build time**, not read at runtime. If
you change the API URL later you must redeploy, not just restart.

### Step 3 — Close the loop

Go back to the backend and set `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`
and `FRONTEND_BASE_URL` to the real Vercel URL, then restart it. Until you do,
the browser blocks every API call as a CORS failure.

---

## The cross-site cookie problem

This is the one that will waste your afternoon if you skip it.

The refresh token is an httpOnly cookie. Locally, `localhost:3000` and
`localhost:8000` are the **same site**, so `SameSite=Lax` works fine.

In production, `something.vercel.app` and `something.railway.app` are
**different sites**. A `SameSite=Lax` cookie is not sent on cross-site requests,
so:

- Logging in appears to work.
- Reloading the page logs you straight back out, because `/auth/refresh` never
  receives the cookie.

The fix is the two variables above:

```bash
REFRESH_COOKIE_SAMESITE=None
REFRESH_COOKIE_SECURE=true
```

`SameSite=None` requires `Secure`, which requires HTTPS — both platforms give
you that by default.

### The better alternative: one domain

If you have a domain, put both on it and the problem disappears:

- `lms.yourdomain.com` → Vercel
- `api.yourdomain.com` → Railway

They are then same-site, so you can keep `SameSite=Lax`, which is a stronger
CSRF posture than `None`. Add the domain in both dashboards and point the DNS
records they give you.

---

## Media uploads

The default `FileSystemStorage` writes to local disk, which most hosts wipe on
redeploy. For anything beyond a demo, move to object storage:

```bash
pip install django-storages boto3
```

```python
# config/settings.py
STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")   # R2 or S3
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_ACL = None          # keep objects private
AWS_QUERYSTRING_AUTH = True     # serve via signed URLs
```

Cloudflare R2 has no egress fee, which suits a document repository.

---

## Verify the deployment

```bash
# API is alive
curl https://srmist-lms-api.up.railway.app/api/v1/health

# Branding endpoint is public — the login page needs it before sign-in
curl https://srmist-lms-api.up.railway.app/api/v1/settings/public
```

Then in the browser:

1. Open the Vercel URL — the login page should render with the school branding
   (that proves the public settings call crossed CORS successfully).
2. Sign in as `student1@sph.srmist.demo` / `Demo@12345`.
3. **Reload the page.** If you stay signed in, the cross-site cookie is
   configured correctly. If you get bounced to login, revisit
   `REFRESH_COOKIE_SAMESITE`.
4. Open a certificate verification link — it should work signed out.

---

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Vercel build fails, "no Next.js detected" | Root Directory is not set to `frontend` |
| Login page loads unbranded, console shows CORS errors | `CORS_ALLOWED_ORIGINS` does not exactly match the Vercel origin — scheme included, no trailing slash |
| Login works, reload signs you out | `REFRESH_COOKIE_SAMESITE` is still `Lax` on a cross-site setup |
| `DisallowedHost` from Django | Backend hostname missing from `DJANGO_ALLOWED_HOSTS` |
| Uploads vanish after a redeploy | Still on local filesystem storage; move to S3/R2 |
| Weekly digest never arrives | Celery beat service not running, or `REDIS_URL` unset |
| Frontend still calls localhost | `NEXT_PUBLIC_API_URL` changed without a redeploy — it is baked in at build time |

## A note on free tiers

Railway and Render free tiers sleep after inactivity, so the first request after
a quiet period takes 30–60 seconds. That is fine for a portfolio demo but reads
as "broken" to someone clicking a link cold. If you are showing this in a viva,
open it a minute beforehand.
