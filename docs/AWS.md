# Deploying to AWS

Unlike Vercel, AWS can host the whole system — API, frontend, database, Redis
and the Celery workers. There are several ways to do it, and they differ a lot
in effort and cost.

## Pick a path

| Path | Effort | Cost/month | When it fits |
| --- | --- | --- | --- |
| **Lightsail — one VM, Docker Compose** | Low | ~$10–12 | **Start here.** An academic project, a portfolio link, a demo |
| EC2 + RDS + S3 | Medium | ~$0 on free tier, then ~$25 | You want managed backups and a real database |
| ECS Fargate + RDS + S3 + CloudFront | High | ~$50+ | Real users, autoscaling, zero-downtime deploys |

The project already ships a working `docker-compose.yml` that runs all six
services. On a single VM that is one command — which is why Lightsail is the
recommendation, not a compromise.

> **Free Tier:** a new AWS account gets 750 hours/month of a `t3.micro` EC2
> instance and 750 hours of `db.t3.micro` RDS for 12 months. As a student you
> may also have AWS Educate credits. That makes path 2 effectively free for a
> year.

---

## Fastest route: the bootstrap script

Once you have an Ubuntu instance running and can open its terminal, this does
every step below in one paste — Docker, swap, clone, secrets, public IP
detection, start, seed:

```bash
curl -fsSL https://raw.githubusercontent.com/Rikdebmandal/SRMIST-Public-Health-LMS/main/scripts/aws-bootstrap.sh | bash
```

It brings the stack up on **port 80 over plain HTTP**, reachable at the
instance's public IP, so you need no domain to see it working. Add a domain and
TLS afterwards using the certificate steps further down.

The manual walkthrough below explains what the script is doing, and is what you
want if a step fails.

---

## Path 1 — Lightsail (recommended)

### 1. Create the instance

AWS console → **Lightsail** → Create instance.

- Region: **Mumbai (ap-south-1)** — lowest latency from India
- Platform: **Linux/Unix**
- Blueprint: **OS Only → Ubuntu 24.04 LTS**
- Plan: **$10/month** (2 GB RAM). The $5/512 MB plan will OOM during the
  Next.js build — 2 GB is the realistic floor.
- Name it `srmist-lms`, then Create.

### 2. Open the firewall

Instance → **Networking** → IPv4 Firewall. You need exactly two rules beyond
SSH:

| Application | Port |
| --- | --- |
| HTTP | 80 |
| HTTPS | 443 |

Do **not** open 5432, 6379, 8000 or 3000. The compose file binds Postgres and
Redis to loopback and the production overlay stops the app containers
publishing ports at all, so nginx is the only way in.

Then attach a **static IP** (Networking → Create static IP). Without it the
address changes on every reboot.

### 3. Install Docker

Connect using the browser SSH button, then:

```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
newgrp docker
```

### 4. Get the code

```bash
git clone https://github.com/Rikdebmandal/SRMIST-Public-Health-LMS.git
cd SRMIST-Public-Health-LMS
```

### 5. Configure

```bash
cp .env.example .env
nano .env
```

Set these. Replace the host with your domain, or the Lightsail static IP if you
do not have one yet:

```bash
DJANGO_SECRET_KEY=<paste the generated value>
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=lms.example.com,<static-ip>

POSTGRES_PASSWORD=<a long random password>

# Same origin for both, because nginx serves the API and the app together
NEXT_PUBLIC_API_URL=https://lms.example.com
FRONTEND_BASE_URL=https://lms.example.com
CORS_ALLOWED_ORIGINS=https://lms.example.com
CSRF_TRUSTED_ORIGINS=https://lms.example.com

TIME_ZONE=Asia/Kolkata
```

Generate the secret key:

```bash
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(64))"
```

**One origin for both means you keep `SameSite=Lax`** — the cross-site cookie
problem from the Vercel setup simply does not arise here. That is the main
architectural advantage of hosting both halves together.

### 6. Point your domain

Add an **A record** for `lms.example.com` pointing at the Lightsail static IP.
Wait for it to resolve:

```bash
dig +short lms.example.com
```

Skip this if you are using the raw IP — but then TLS is not possible, and
`DJANGO_DEBUG=false` forces HTTPS. For an IP-only deploy, set
`SECURE_SSL_REDIRECT=false` in `.env` and use the base compose file only.

### 7. Set the domain in nginx

```bash
sed -i 's/lms.example.com/YOUR-DOMAIN.com/g' docker/nginx.conf
```

### 8. Issue the certificate

nginx will not start without a certificate, so get one first using a throwaway
webroot:

```bash
docker run --rm -p 80:80 \
  -v "$PWD/certbot_conf:/etc/letsencrypt" \
  certbot/certbot certonly --standalone \
  -d YOUR-DOMAIN.com --agree-tos --register-unsafely-without-email
```

Copy it into the volume the stack uses:

```bash
docker volume create srmist-public-health-lms_certbot_conf
docker run --rm \
  -v "$PWD/certbot_conf:/from" \
  -v srmist-public-health-lms_certbot_conf:/to \
  alpine sh -c "cp -r /from/. /to/"
```

### 9. Start everything

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

The first build takes 5–10 minutes. Watch it with:

```bash
docker compose logs -f
```

### 10. Seed and create an administrator

```bash
docker compose exec backend python manage.py seed_demo --reset
docker compose exec backend python manage.py createsuperuser
```

Skip `seed_demo` for a real deployment — it creates fictional demo accounts with
a published password.

### 11. Verify

```bash
curl https://YOUR-DOMAIN.com/api/v1/health
```

Then open `https://YOUR-DOMAIN.com` and sign in. Reload the page — if you stay
signed in, cookies are working.

---

## Path 2 — EC2 + RDS + S3

Same VM setup, but the database and files move to managed services. Worth it
because RDS gives you automated backups and point-in-time recovery, which a
container volume does not.

### RDS

RDS → Create database → PostgreSQL 16 → **Free tier** template →
`db.t3.micro`, 20 GB.

- **Public access: No.** Put it in the same VPC as the instance.
- Security group: allow 5432 **only** from the EC2 instance's security group,
  never from `0.0.0.0/0`.

Then in `.env`:

```bash
DATABASE_URL=postgres://phlms:<password>@<rds-endpoint>.rds.amazonaws.com:5432/public_health_lms
```

Remove the `db` service from the compose command:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale db=0
```

### S3 for uploads

A container volume is lost if you rebuild the instance. Notes, submissions and
certificates belong in S3.

```bash
aws s3 mb s3://srmist-lms-media --region ap-south-1
```

Keep **Block Public Access on** — the app serves files through signed URLs.

Add to `backend/requirements.txt`:

```
django-storages==1.14.4
boto3==1.35.0
```

Then in `config/settings.py`:

```python
if os.getenv("AWS_STORAGE_BUCKET_NAME"):
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "ap-south-1")
    AWS_DEFAULT_ACL = None          # objects stay private
    AWS_QUERYSTRING_AUTH = True     # served via signed URLs
    AWS_S3_FILE_OVERWRITE = False
```

Attach an **IAM role** to the instance with `s3:GetObject`, `s3:PutObject` and
`s3:DeleteObject` scoped to that bucket. Use a role, not access keys in `.env` —
a role rotates its own credentials and cannot leak through a committed file.

---

## Path 3 — ECS Fargate

Only worth the complexity if you need autoscaling and zero-downtime deploys.
Outline:

1. Push both images to **ECR**.
2. Task definitions for `backend`, `frontend`, `worker`, `beat`.
3. **ECS Fargate** service behind an **Application Load Balancer**.
4. **RDS** for Postgres, **ElastiCache** for Redis.
5. **ACM** certificate on the ALB, **CloudFront** in front for static assets.
6. Secrets in **AWS Secrets Manager**, injected as task environment.

Realistically ~$50–80/month and a day of setup. For an academic project it buys
nothing that path 1 does not already give you.

---

## Cost control

Set a billing alarm before you deploy anything:

Billing → Budgets → Create budget → Cost budget → $10 → email alert at 80%.

This is the step people skip and then get a surprise bill.

To stop paying while keeping the setup:

```bash
docker compose down          # stops containers, keeps data volumes
```

Lightsail still bills for a stopped instance. Take a snapshot and delete the
instance to stop charges entirely.

---

## Operations

```bash
# Update to the latest code
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Logs
docker compose logs -f backend
docker compose logs -f worker

# Django shell
docker compose exec backend python manage.py shell

# Database backup
docker compose exec db pg_dump -U phlms -Fc public_health_lms > backup_$(date +%F).dump

# Restore
cat backup.dump | docker compose exec -T db pg_restore -U phlms -d public_health_lms --clean
```

Automate the backup with cron:

```bash
crontab -e
# Daily at 02:00, keeping 7 days
0 2 * * * cd ~/SRMIST-Public-Health-LMS && docker compose exec -T db pg_dump -U phlms -Fc public_health_lms > ~/backups/db_$(date +\%F).dump && find ~/backups -name 'db_*.dump' -mtime +7 -delete
```

---

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `DisallowedHost` | Domain missing from `DJANGO_ALLOWED_HOSTS` |
| Infinite HTTPS redirect | nginx not sending `X-Forwarded-Proto`, or you are on plain HTTP with `SECURE_SSL_REDIRECT=true` |
| 502 from nginx | Backend container not up yet — `docker compose logs backend` |
| Build killed during `npm run build` | Instance under 2 GB RAM. Resize, or add swap |
| 413 on file upload | `client_max_body_size` in nginx is below `MAX_UPLOAD_SIZE_MB` |
| Certificate renewal fails | Port 80 closed. Certbot's webroot challenge needs it open |
| Weekly digest never sends | `beat` container not running, or `REDIS_URL` unset |
| Uploads vanish after rebuild | Still on a container volume — move to S3 (path 2) |

### Add swap if the build is killed

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## Security checklist

- [ ] Only 22, 80 and 443 open; 5432 and 6379 are loopback-bound
- [ ] `DJANGO_DEBUG=false` and a freshly generated `DJANGO_SECRET_KEY`
- [ ] `POSTGRES_PASSWORD` is long and random, not the `.env.example` default
- [ ] SSH by key only, password authentication disabled
- [ ] `seed_demo` **not** run on a real deployment — the demo password is public
- [ ] RDS not publicly accessible; security group scoped to the instance
- [ ] S3 bucket has Block Public Access on; app uses an IAM role, not keys
- [ ] Billing alarm set
- [ ] Automated database backup running, **and a restore tested once**
