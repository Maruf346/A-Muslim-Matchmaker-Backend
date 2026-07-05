# AMM — Docker & CI/CD Setup Guide

This guide walks through every change needed to get AMM running locally via Docker on port 8001, and to have CI/CD working end-to-end (with deployment secrets left empty until AWS is ready).

---

## 1. Fix required in `settings.py` (before anything else)

Your shared `settings.py` has **two `CACHES` dictionaries** — the second one silently overrides the first:

```python
# First definition (correct — uses 'amm' prefix)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/1',
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
        'KEY_PREFIX': 'amm',
        'TIMEOUT': 300,
    }
}

# ... later in the file ...

# Second definition (leftover from FixGo — overrides the one above!)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{_REDIS_HOST}:{_REDIS_PORT}/1',
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
        'KEY_PREFIX': 'autointel',   # ← wrong prefix, silently active
        'TIMEOUT': 300,
    }
}
```

**Fix:** delete the first `CACHES` block entirely (the one right after `REDIS_HOST`/`REDIS_PORT` near the top), and change `'KEY_PREFIX': 'autointel'` to `'KEY_PREFIX': 'amm'` in the second (lower) block, which is the one that's actually active. Keep only one `CACHES` definition in the file.

Also update `SPECTACULAR_SETTINGS['CONTACT']['email']` if you'd like a different contact than `support@amuslimmatrimony.com` — currently already correct for AMM, no change needed there.

No other settings.py changes are required — `INSTALLED_APPS` already lists all the apps we built (`api`, `notifications`, `users`, `questions`, `matches`, `wishlists`, `chat`), and `ASGI_APPLICATION` is already pointed correctly.

One note: `supports` appears in your `INSTALLED_APPS` list but we haven't built that app yet — if it doesn't exist on disk yet, remove it from `INSTALLED_APPS` for now or Django will fail to boot. Add it back once that app exists.

---

## 2. Files I've modified for AMM (renamed from FixGo branding)

| File | What changed |
|---|---|
| `docker-compose.yml` | Container names `fixgo_*` → `amm_*`; Nginx host port `80:80` → `8001:80`; removed the unrelated `libretranslate` service (FixGo leftover, not used by AMM) |
| `Dockerfile` | No functional change — multi-stage build is identical and correct |
| `entrypoint.sh` | Banner text `FixGo API` → `AMM API`; logic unchanged |
| `nginx.conf` | Comments updated to reference AMM's actual WebSocket routes (`notifications`, `chat` — removed mention of a `tracking` consumer that doesn't exist in this project); added a note that host access is via port 8001 |
| `.github/workflows/ci.yml` | Removed FixGo-specific env vars not used by AMM (`PLATFORM_FEE_PERCENTAGE`, `SERVICE_POPULAR_THRESHOLD`, `TRACKING_*`); added AMM's actual settings vars (`LAST_ACTIVE_UPDATE_INTERVAL`); Docker image tag `fixgo-api:ci` → `amm-api:ci`; `BASE_URL` updated to port 8001 |
| `.github/workflows/deploy.yml` | Deploy path `~/fixgo-backend` → `~/amm-backend`; banner text updated; logic otherwise identical |
| `.gitattributes` | No change needed — already project-agnostic |
| `.dockerignore` | No change needed — already project-agnostic |
| `.env.example` | New file — template for local `.env`, matches AMM's actual settings vars and port 8001 |

---

## 3. Local setup steps

```bash
# 1. Copy the env template and fill in real values
cp .env.example .env

# Edit .env and at minimum set a real SECRET_KEY:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# paste the output into SECRET_KEY= in .env

# 2. Build and start everything
docker compose up --build

# 3. In a separate terminal, create a superadmin (maps to SUPERADMIN role)
docker compose exec django python manage.py createsuperuser

# 4. Access points
# API + Swagger → http://localhost:8001/api/docs/
# Django Admin  → http://localhost:8001/admin/
# WebSocket     → ws://localhost:8001/ws/notifications/?token=<jwt>
#               → ws://localhost:8001/ws/chat/<room_id>/?token=<jwt>
```

If port 8001 is ever busy too, change only the **left side** of the ports mapping in `docker-compose.yml`:
```yaml
ports:
  - "8001:80"   # change "8001" to any free port; right side (80) stays the same
```

---

## 4. GitHub Secrets — what to add now vs later

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**.

### Add now (required for CI to pass):

| Secret name | Value |
|---|---|
| `SECRET_KEY` | Any random string — generate with the Python command above. This is used only inside the CI test run, separate from your local `.env` or production secret. |

That's the only secret CI actually needs, since CI uses SQLite + console email backend + empty OAuth placeholders (all hardcoded into `ci.yml` directly, not pulled from secrets except `SECRET_KEY`).

### Add later (once AWS is provisioned — deploy.yml needs these):

| Secret name | Value | Notes |
|---|---|---|
| `EC2_HOST` | Public IP or domain of your EC2 instance | e.g. `54.123.45.67` or `api.amuslimmatrimony.com` |
| `EC2_USER` | SSH username for the EC2 instance | Typically `ubuntu` for Ubuntu AMIs |
| `EC2_SSH_KEY` | The **private** key (full contents of your `.pem` file) used to SSH into EC2 | Paste the entire file including `-----BEGIN ... PRIVATE KEY-----` lines |

**Until these three secrets exist, `deploy.yml` will still run** (since it triggers on every successful CI run on `main`), but the SSH step will fail immediately since `secrets.EC2_HOST` etc. will be empty strings. This is harmless — it'll just show a red ❌ on the Actions tab for the deploy job specifically, while CI itself stays green. If you'd rather not see that red X yet, you can temporarily comment out the entire `deploy.yml` workflow file content (or rename it to `deploy.yml.disabled`) until AWS is ready — your call, both approaches are safe.

### Also needed on the EC2 server itself (NOT GitHub Secrets — these live on the server):

Once you do have AWS, you'll need on the EC2 instance:
1. A cloned copy of the repo at `~/amm-backend`
2. A `.env.production` file (same shape as `.env.example`, but with real production values — `DEBUG=False`, real `SECRET_KEY`, real Postgres credentials if you switch from SQLite, real `ALLOWED_HOSTS` with your actual domain, etc.) 
3. A `docker-compose.prod.yml` file — **this doesn't exist yet**. It's referenced by `deploy.yml` but needs to be created separately (it's typically `docker-compose.yml` minus the bind-mount `- .:/app` line, since production should run the baked image, not live-reload from source). I can build this file with you once you're ready to set up the AWS side — just let me know.

---

## 5. What's NOT yet wired up — flagging for awareness

- `docker-compose.prod.yml` doesn't exist yet (mentioned above) — `deploy.yml` references it but it needs to be created when you're ready for the AWS phase.
- The `supports` app referenced in `INSTALLED_APPS` doesn't exist on disk in anything we've built so far — remove it from the list for now if Django complains on boot, or let me know if that's a different app you're planning to add (e.g. a customer-support ticketing app) and we can build it.
- CI's `python manage.py test` step will currently report "0 tests ran" since no test files exist yet in any app — this is expected and won't fail the build, but it's worth knowing it's not actually testing any of our logic yet. We can add real tests for the auth flow, match lifecycle, etc. whenever you'd like to prioritize that.

---

## 6. Summary of host ports in use

| Service | Host port | Container port |
|---|---|---|
| Nginx (all HTTP + WebSocket traffic) | **8001** | 80 |
| Django/Daphne (direct, optional debug only) | — (commented out) | 8000 |
| Redis | — (not exposed to host) | 6379 |

Everything routes through Nginx on **8001** — that's the only port you need to remember for local development.

