# Deployment

## Environment variables

Copy `.env.example` to `.env` and fill it in. Nothing sensitive is committed.

### Required in production

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Signs sessions and JWTs. Generate fresh; never reuse the development default |
| `DJANGO_DEBUG` | `false` in production. Leaving it true exposes stack traces |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames |
| `DATABASE_URL` | `postgres://user:password@host:5432/public_health_lms` |
| `CORS_ALLOWED_ORIGINS` | The frontend origin, e.g. `https://lms.example.edu` |
| `CSRF_TRUSTED_ORIGINS` | Same |
| `FRONTEND_BASE_URL` | Used in password-reset and certificate-verification links |
| `NEXT_PUBLIC_API_URL` | Backend origin the browser calls |

### Recommended

| Variable | Default | Purpose |
| --- | --- | --- |
| `REDIS_URL` | — | Cache, Celery broker, and cross-instance throttling |
| `CELERY_BROKER_URL` | `REDIS_URL` | Background jobs |
| `EMAIL_BACKEND` | console | Set to SMTP for real delivery |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | — | SMTP credentials |
| `DEFAULT_FROM_EMAIL` | `no-reply@sph.srmist.local` | Sender address |
| `MEDIA_ROOT` | `backend/media` | Upload location |
| `TIME_ZONE` | `Asia/Kolkata` | Institutional timezone |
| `MAX_UPLOAD_SIZE_MB` | `25` | Global upload cap |
| `ALLOWED_UPLOAD_EXTENSIONS` | see `.env.example` | Global allow-list |
| `ACCESS_TOKEN_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_DAYS` | `7` | Refresh token lifetime |
| `LOGIN_MAX_FAILED_ATTEMPTS` | `5` | Lockout threshold |
| `LOGIN_LOCKOUT_MINUTES` | `15` | Lockout window |
| `SECURE_SSL_REDIRECT` | `true` when `DEBUG=false` | Force HTTPS |
| `LOG_LEVEL` | `INFO` | Backend log verbosity |

---

## Hosting the frontend on Vercel

Vercel is serverless and cannot run the Celery worker, keep uploaded files, or
hold database connections. Put the Next.js app there and the Django API on a
platform with persistent processes. Step-by-step instructions, including the
cross-site cookie configuration that setup requires, are in
[VERCEL.md](VERCEL.md).

## Hosting on AWS

AWS can run the whole stack, Celery included. The single-VM Lightsail path uses
the compose files directly and is the recommended starting point — see
[AWS.md](AWS.md).

## Docker Compose

The fastest path to a running stack:

```bash
cp .env.example .env
# edit .env — at minimum set DJANGO_SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build
```

Services started:

| Service | Port | Role |
| --- | --- | --- |
| `db` | 5432 | PostgreSQL 16 with a named volume |
| `redis` | 6379 | Cache and Celery broker |
| `backend` | 8000 | Gunicorn serving Django |
| `worker` | — | Celery worker |
| `beat` | — | Celery beat scheduler |
| `frontend` | 3000 | Next.js production server |

Migrations run automatically on backend start. Seed the demo dataset once:

```bash
docker compose exec backend python manage.py seed_demo --reset
```

For a public host, add the production overlay. It puts nginx with TLS in front
and stops the app containers publishing ports of their own, so only 80 and 443
are reachable:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Create a real administrator instead, for a genuine deployment:

```bash
docker compose exec backend python manage.py createsuperuser
```

---

## Manual deployment

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export DJANGO_DEBUG=false
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
export DATABASE_URL="postgres://user:password@localhost:5432/public_health_lms"

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy

gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 --workers 4 --timeout 60 --access-logfile -
```

Run the background services alongside it:

```bash
celery -A config worker --loglevel=info
celery -A config beat   --loglevel=info
```

`config/celery.py` schedules the weekly digest (Monday 07:00), deadline
reminders (daily 18:00), the attendance alert sweep (daily 20:00), content
expiry (daily 01:00) and risk snapshot refresh (Sunday 02:00).

### Frontend

```bash
cd frontend
npm ci
NEXT_PUBLIC_API_URL="https://api.lms.example.edu" npm run build
npm run start          # or serve .next behind a Node process manager
```

`NEXT_PUBLIC_API_URL` is inlined at build time, so it must be set for the build,
not just at runtime.

### Reverse proxy

```nginx
server {
    listen 443 ssl http2;
    server_name lms.example.edu;

    ssl_certificate     /etc/letsencrypt/live/lms.example.edu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/lms.example.edu/privkey.pem;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    client_max_body_size 30M;   # must exceed MAX_UPLOAD_SIZE_MB

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /media/ { alias /srv/public-health-lms/backend/media/; }
    location /static/ { alias /srv/public-health-lms/backend/staticfiles/; }

    location / { proxy_pass http://127.0.0.1:3000; }
}
```

`X-Forwarded-Proto` matters: `SECURE_PROXY_SSL_HEADER` relies on it, and without
it Django will redirect in a loop.

---

## Backups

```bash
# Database — compressed custom format, restorable selectively
pg_dump -Fc -h "$DB_HOST" -U "$DB_USER" public_health_lms \
  > /backups/db_$(date +%F).dump

# Uploaded files
tar czf /backups/media_$(date +%F).tar.gz -C /srv/public-health-lms/backend media/
```

Restore:

```bash
pg_restore -h "$DB_HOST" -U "$DB_USER" -d public_health_lms --clean /backups/db_2026-09-02.dump
tar xzf /backups/media_2026-09-02.tar.gz -C /srv/public-health-lms/backend/
```

Retention: daily for 7 days, weekly for 4 weeks, monthly for 12 months.

**Test the restore on a scratch database.** An untested backup is a hypothesis.

### Disaster recovery

| Scenario | Action |
| --- | --- |
| Application host lost | Redeploy from the image, point at the existing database |
| Database corrupted | Restore the most recent dump; replay is bounded by backup frequency |
| Media lost | Restore the media archive, or rely on S3 versioning |
| Accidental data deletion | Most tables soft-delete: clear `is_deleted` rather than restoring a dump |

Soft delete is the first line of recovery — a mistakenly removed course or note
is a flag flip, not a restore.

---

## Health and monitoring

`GET /api/v1/health` returns `{"status": "ok", "database": "ok", "api_version": "v1"}`
without authentication — suitable for a load balancer probe.

The logging configuration writes structured records to stdout, ready for a
container log collector. Passwords, tokens and student identifiers are never
logged. The architecture leaves room for Sentry, Prometheus and Grafana; none is
wired up.

## Upgrades

```bash
git pull
pip install -r backend/requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
cd frontend && npm ci && npm run build
# restart backend, worker, beat, frontend
```

Run `python manage.py makemigrations --check --dry-run` in CI. It fails when a
model changes without a migration, which is the failure mode that bites during a
deploy rather than during review.
