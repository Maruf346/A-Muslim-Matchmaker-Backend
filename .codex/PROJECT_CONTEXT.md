# PROJECT_CONTEXT.md — AMM Backend Architecture Overview

## Project Summary
**A Muslim Matchmaker (AMM)** — matrimonial platform for conservative Sunni Muslims.
Three user types (Male, Female, Wali) + two admin types (Matchmaker, Superadmin).
Two separate matching tracks: standard (user-driven) and private (matchmaker-curated).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Web framework | Django 4.x |
| API framework | Django REST Framework (DRF) |
| API docs | drf-spectacular (OpenAPI 3 / Swagger) |
| Auth | JWT via `djangorestframework-simplejwt` |
| WebSocket | Django Channels + Redis channel layer |
| ASGI server | Daphne |
| Task queue | Celery + Redis broker |
| Periodic tasks | `django-celery-beat` (DB scheduler) |
| Caching | `django-redis` |
| Database (dev) | SQLite (in `db_volume/db.sqlite3`) |
| Database (prod) | PostgreSQL on AWS RDS (env-var switchable) |
| File storage | Django `FileField` → local `media/` (S3-ready via env swap) |
| Admin panel | Jazzmin-themed Django admin |
| Filtering | `django-filter` + DRF `SearchFilter` / `OrderingFilter` |
| Phone fields | `django-phonenumber-field` |
| Rich text | `django-ckeditor-5` |
| OAuth | Google + Apple (JWT-based, mobile-first) |

---

## Infrastructure & Deployment

| Component | Detail |
|---|---|
| Server | AWS EC2 (Ubuntu) |
| Repo deploy path | `~/amm-backend` |
| Container runtime | Docker + Docker Compose |
| Reverse proxy | Nginx (Alpine) |
| Host port (local dev) | **8001** (mapped to Nginx container port 80) |
| Host port (production) | 80 / 443 (behind Nginx + SSL) |
| CI | GitHub Actions (`.github/workflows/ci.yml`) |
| CD | GitHub Actions (`.github/workflows/deploy.yml`) — SSH deploy to EC2 on `main` merge |
| CI database | SQLite (in-memory for speed) |
| Prod database | PostgreSQL on AWS RDS |
| Secrets management | GitHub Actions Secrets + `.env.production` on EC2 |

### Docker services
```
amm_nginx         → Nginx reverse proxy, host:8001 → container:80
amm_django        → Daphne ASGI, internal port 8000
amm_celery_worker → Celery worker
amm_celery_beat   → Celery Beat scheduler
amm_redis         → Redis 7 Alpine, AOF persistence
```

### CI/CD flow
```
Push to any branch → CI (lint, migrate, test, docker build check)
Merge to main      → CI passes → deploy.yml SSHes into EC2
                     → git pull → docker compose build → migrate → collectstatic
```

### GitHub Secrets required
| Secret | Purpose |
|---|---|
| `SECRET_KEY` | Django secret key (CI only) |
| `EC2_HOST` | EC2 public IP or domain |
| `EC2_USER` | SSH username (e.g. `ubuntu`) |
| `EC2_SSH_KEY` | Full contents of EC2 `.pem` private key |

---

## App Map & Responsibilities

### `core/`
Django project root. Contains `settings.py`, `urls.py`, `asgi.py`, `celery.py`, `pagination.py`, `wsgi.py`.

`settings.py` key sections:
- `AUTH_USER_MODEL = 'users.User'`
- `ASGI_APPLICATION = 'core.asgi.application'`
- Redis DBs: `/0` = Celery, `/1` = cache
- Cache key prefix: `amm`
- OTP expiry: 300s (5 min) registration, 600s (10 min) password reset
- Last active DB write throttle: 120s

### `api/`
URL aggregator. No models. No views. Just `urls.py` that `include()`s every app.

```
/api/user/            → users.urls
/api/notification/    → notifications.urls
/api/questions/       → questions.urls
/api/matches/         → matches.urls
/api/wishlists/       → wishlists.urls
/api/chat/            → chat.urls
/api/matchmaking/     → matchmaking.urls
/api/private-matches/ → private_matches.urls
/api/docs/            → Swagger UI
/api/schema/          → OpenAPI schema
/api/health/          → health check lambda
```

### `users/`
- Custom `AbstractUser` — email-based auth, `username=None`
- Role stored in `user.role` (TextChoices): `male`, `female`, `wali`, `matchmaker`, `superadmin`
- `is_private_matchmaking_client` (BooleanField) — flipped on matchmaking approval
- `is_active=False` → blocked (admin) or deactivated (user). `deactivated_by_user` distinguishes.
- `last_active` updated by `LastActiveMiddleware` (throttled via Redis, max 1 DB write per 120s)
- Separate registration endpoints per role: `/user/male/register/`, `/user/female/register/`, `/user/wali/register/`
- Single admin login endpoint returns `admin_type` field
- `UserSettings` auto-created via `post_save` signal
- `SubscriptionPlan`: FREE (default), MONTHLY, ANNUAL

### `questions/`
- `MaleBasicInfo`, `FemaleBasicInfo`, `WaliBasicInfo` (sister's data), `WaliProfile` (wali's own Step 1 data)
- All fields `blank=True, null=True`
- Multiselect fields: `JSONField(default=list)`
- `completion_percentage` is a `@property` — computed on the fly, not stored
- `age` is a `@property` — computed from `date_of_birth`
- `UserPhoto` — multiple photos per user, `is_primary` flag, shared across all roles
- Height stored as full display string: `"170cm - 5' 7\""`
- Weight stored as full display string: `"70kg - 154lbs"`
- GET + PATCH only (no POST needed — `get_or_create` pattern)
- Choices module: `questions/choices.py` — single source of truth for all dropdown options

### `matches/`
- `Match` model — single table covering full lifecycle via `status` field
- Status flow: `PENDING → ACCEPTED → WALI_REQUESTED → IN_DISCUSSION → MARRIED/DROPPED`
- Photo cycle: `photo_request_status` (NONE/REQUESTED/APPROVED) + `photos_currently_visible` bool
- Wali request: male-initiated only, tracked via `wali_request_status`
- `cancelled_by` / `dropped_by` FKs track who ended the connection
- `match_id`: format `MT-<n>` (flexible, no zero-padding)
- Subscription enforcement: Free → can't send; Monthly → 10/cycle; Annual → unlimited
- Billing cycle: anniversary-based on `user.subscription_start`
- Directory: `GET /api/matches/directory/` — excludes blocked/hidden/reported/private clients
- Profile view recorded on `GET /api/matches/directory/<user_id>/` and `GET /api/matches/<pk>/`

### `wishlists/`
- `SavedProfile` — toggle save/unsave (love button)
- `ProfileView` — auto-recorded on profile access, used for "who viewed me"
- "Who viewed me" gated by subscription (`can_see_viewers`)
- `BlockedProfile` — mutual visibility block
- `HiddenProfile` — one-directional hide
- `Report` — filed against user, reviewed by admin
- `VisibilityService.get_excluded_user_ids(user)` — central exclusion set used in directory + connection requests

### `notifications/`
- Single `Notification` model, all roles share it
- Delivery: Male/Female/Wali → DB only (REST poll); Admin → DB + WebSocket push
- WebSocket group: `f"user_{user.id}"`
- Consumer: `ws/notifications/?token=<jwt>` — admin only, rejects non-admin with code 4003
- Always use `NotificationTemplates` — never `NotificationService.send()` directly

### `chat/`
- One `ChatRoom` per normal user (OneToOneField) — shared inbox for all admins
- `Message` — text and/or single file attachment, `sender_is_admin` denormalized
- `is_read` / `read_at` for read receipts
- WebSocket: `ws/chat/<room_id>/?token=<jwt>` — user: own room only; admin: any room
- File upload via REST POST (not WS). Download via `FileResponse(as_attachment=True)`.
- Admin inbox sorted by `room.updated_at` (touched on every new message)
- Admin inbox searchable by codename, first/last name, email

### `matchmaking/`
- `PrivateMatchmakingRequest` — user submits, admin approves/declines
- One active request per user at a time (enforced in service)
- On approval: `user.is_private_matchmaking_client = True` automatically
- `request_id` format: `RQ-<n>` (flexible)
- No booking fields (datetime/investment) — admin handles manually via chat

### `private_matches/`
- `PrivateMatchSuggestion` — matchmaker pushes prospect to private client
- Prospect is NEVER notified until private client says YES
- Status flow: `PENDING_CLIENT_REVIEW → CLIENT_ACCEPTED → SENT_TO_PROSPECT → PROSPECT_ACCEPTED/DECLINED`
                              `→ CLIENT_DECLINED` (prospect never notified)
- `unique_together`: `(private_client, prospect)` — one suggestion per pair
- No standard `Match` row ever created for private matches
- Admin prospect browser: gender-filtered, shows both standard + private clients

---

## Authentication Flow

```
Register (2-step OTP):
  POST /api/user/<role>/register/initiate/  → sends OTP email (Celery task)
  POST /api/user/<role>/register/verify/   → creates user, assigns codename, returns JWT

Login (role-specific):
  POST /api/user/male/login/
  POST /api/user/female/login/
  POST /api/user/wali/login/
  POST /api/user/admin/login/   → returns admin_type field

Password reset (3-step):
  POST /api/user/password-reset/initiate/  → OTP email
  POST /api/user/password-reset/verify/    → returns reset_token
  POST /api/user/password-reset/confirm/   → sets new password

OAuth (Google + Apple):
  POST /api/user/auth/google/   → id_token + role
  POST /api/user/auth/apple/    → id_token + user + role

JWT:
  Access token lifetime:  1 day
  Refresh token lifetime: 7 days
  Rotation + blacklist on refresh
```

---

## Environment Variables

```bash
# Core
SECRET_KEY
DEBUG=True/False
ALLOWED_HOSTS

# Database
DB_ENGINE=django.db.backends.sqlite3  # or postgresql
DB_NAME / DB_USER / DB_PASSWORD / DB_HOST / DB_PORT

# Redis
REDIS_HOST=redis   # inside Docker; localhost outside
REDIS_PORT=6379

# Email
EMAIL_BACKEND
EMAIL_HOST / EMAIL_PORT / EMAIL_USE_TLS
EMAIL_HOST_USER / EMAIL_HOST_PASSWORD
DEFAULT_FROM_EMAIL=noreply@amuslimmatrimony.com

# OAuth
GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_WEB_CLIENT_ID
APPLE_CLIENT_ID

# Timing
OTP_EXPIRY_SECONDS=300
PASSWORD_RESET_OTP_EXPIRY_SECONDS=600
PASSWORD_RESET_TOKEN_EXPIRY_SECONDS=900
LAST_ACTIVE_UPDATE_INTERVAL=120
```

---

## Pending / Not Yet Built

- Admin dashboard summary endpoint (total users, active users, total matches, pending requests, recent activity feed)
- Account deletion with `WhyLeaving` feedback model
- Subscription upgrade/downgrade endpoints (payment not integrated yet)
- Legacy user data migration management command
- Suggested matches AI integration (skeleton endpoint only — AI team handles AI side)
- Push notifications via FCM/APNs (device_token field exists, not wired up)
- `docker-compose.prod.yml` (needed for EC2 deployment — not created yet)
- Payment integration (Apple Pay / Google Pay — deferred)
