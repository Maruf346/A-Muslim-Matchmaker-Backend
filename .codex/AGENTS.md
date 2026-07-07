# AGENTS.md — AI Coding Instructions & Standards for AMM Backend

## Project Identity
- **Name:** A Muslim Matchmaker (AMM) Backend API
- **Type:** Django REST Framework API — matrimonial platform for conservative Sunni Muslims
- **Language:** Python 3.12
- **Framework:** Django 4.x + Django REST Framework + Django Channels (WebSocket)

---

## Architecture at a Glance

```
core/           → Django project config (settings, urls, asgi, celery, pagination)
api/            → URL aggregator only — no models, no views, just includes
apps/
  users/            → Auth, roles, subscriptions, profile, codenames
  questions/        → Onboarding basic info (Male/Female/Wali), photos
  matches/          → Connection requests, matches, photo/wali request lifecycle
  wishlists/        → Saved profiles, profile views, block/hide/report
  notifications/    → DB notifications + WebSocket push for admins
  chat/             → Real-time chat (WebSocket + REST), file attachments
  matchmaking/      → Private matchmaking consultation requests
  private_matches/  → Matchmaker-curated suggestions for private clients
```

---

## Coding Standards — Always Follow These

### Django / DRF
- **Thin views, fat services.** All business logic goes in `services.py`. Views only validate input, call service methods, and return responses.
- **Never put DB queries in serializers** except for `SerializerMethodField` lookups. Heavy logic belongs in services.
- **`get_or_create` pattern** for onboarding endpoints — never require a separate POST to initialize a record.
- All models inherit a `created_at` / `updated_at` pattern (`auto_now_add` / `auto_now`).
- Use `UUID` primary keys on all models.
- All model fields that are optional must have `blank=True, null=True` — especially in `questions/` models.
- `JSONField(default=list)` for multiselect fields — never `ManyToManyField` for choice lists.

### Swagger / OpenAPI
- Every view and viewset action must have `@extend_schema` with `summary`, `description`, `request`, and `responses`.
- Use `@extend_schema_view` on ViewSets to document each action.
- Tag format: `"AppName - Audience"` — e.g. `"Matches - Admin"`, `"Chat - User"`, `"Basic Info - Male"`.
- Use `inline_serializer` for simple response shapes that don't need a full model serializer.
- **Never leave an endpoint undocumented.**

### Permissions
- Always set `permission_classes` explicitly on every view — never rely on global defaults silently.
- Use custom permission classes from `users/permissions.py`: `IsMaleUser`, `IsFemaleUser`, `IsWaliUser`, `IsNormalUser`, `IsAdminUser`, `IsSuperAdmin`, `IsSubscribed`.
- Admin endpoints use `IsAdminUser` (Matchmaker OR Superadmin). Superadmin-only actions use `IsSuperAdmin`.

### Error handling
- Views catch `ValueError` from services and return `HTTP 400` with `{"error": str(e)}`.
- Never let unhandled exceptions reach the client — wrap side effects (notifications, WS push) in `try/except` with `logger.exception(...)`.
- Always use `logger = logging.getLogger(__name__)` at the top of every file that has side effects.

### Naming conventions
- URL names: `kebab-case` — e.g. `"male-register-initiate"`, `"admin-pm-requests"`.
- Model fields: `snake_case`.
- Serializer method fields: `get_<field_name>`.
- Service static methods: `verb_noun` — e.g. `send_connection_request`, `approve_photo_request`.

### File structure per app
```
app_name/
  models.py
  serializers.py
  services.py      ← business logic only
  views.py
  urls.py
  permissions.py   ← only if app has custom permissions
  apps.py
  tasks.py         ← Celery tasks only
  consumers.py     ← WebSocket only (chat, notifications)
  routing.py       ← WebSocket URL patterns only
```

---

## Role System

| Role | `user.role` value | Notes |
|---|---|---|
| Male | `"male"` | Normal user, gender auto-set at registration |
| Female | `"female"` | Normal user, gender auto-set at registration |
| Wali | `"wali"` | Guardian, creates profile for female ward |
| Matchmaker | `"matchmaker"` | Admin, limited permissions (no financial data) |
| Superadmin | `"superadmin"` | Admin, full permissions |

- `user.is_normal_user` → True for Male/Female/Wali
- `user.is_admin_user` → True for Matchmaker/Superadmin
- `user.is_private_matchmaking_client` → Bool, flipped by matchmaking approval

---

## Codename Format

| Role | Format | Example |
|---|---|---|
| Male | `B-<n>` | B-1, B-238 |
| Female | `S-<n>` | S-1, S-460 |
| Wali | `W-<n>` | W-1, W-99 |

Generated at registration-complete time. No zero-padding. Numbers grow naturally.
Admins do not get codenames.

---

## Key Business Rules — Never Violate These

1. **Photos are blurred until mutual interest** — enforced in `MatchedProfileSerializer` via `photos_currently_visible` flag. Directory view always returns `photo_blurred=True`.
2. **Full name, phone, and contact details hidden until mutual interest** — `display_name` returns `codename` before mutual interest, `full_name` after.
3. **Only Male can send connection requests** — Female/Wali can only receive and respond.
4. **Free plan users cannot send connection requests** — blocked at `CanSendConnectionRequest` permission.
5. **Monthly plan limit: 10 requests per billing cycle** — cycle resets on `subscription_start` anniversary day, enforced in `SubscriptionLimitService`.
6. **Private matchmaking clients are hidden from the standard directory** — `DirectoryListView` always filters `is_private_matchmaking_client=False`.
7. **Private match prospect is NEVER notified unless the private client says YES first** — enforced in `PrivateMatchService.client_respond()`.
8. **No standard Match row is ever created for private matchmaking** — private matches live only in `PrivateMatchSuggestion`.
9. **Wali handles everything on behalf of the female ward** — no separate "ward" user account; Wali IS the account for the female.
10. **Wali request is male-initiated only** — enforced in `MatchService.send_wali_request()`.

---

## WebSocket Channels

| Endpoint | Consumer | Who connects |
|---|---|---|
| `ws/notifications/` | `NotificationConsumer` | Admin only (Matchmaker/Superadmin) |
| `ws/chat/<room_id>/` | `ChatConsumer` | Normal user (own room only) + Admin (any room) |

- No `AllowedHostsOriginValidator` — mobile apps don't send Origin headers.
- Auth via `?token=<jwt>` query param in both consumers.
- Sending chat messages happens via REST (file uploads can't go over WS).
- WS only receives pushed events (`chat_message`, `read_receipt`, `notification_message`).

---

## Redis Usage

| Redis DB | Purpose |
|---|---|
| `/0` | Celery broker + result backend |
| `/1` | Django cache (OTPs, last_active throttle) |

Cache key prefix: `amm`

Key patterns:
- `registration_otp:<role>:<email>` — registration OTP payload
- `password_reset_otp:<email>` — password reset OTP
- `password_reset_token:<token>` — reset token → email mapping
- `last_active_updated:<user_id>` — throttle flag for LastActiveMiddleware (TTL: 120s)

---

## Celery Tasks

All tasks live in `<app>/tasks.py` with `@shared_task`.
Email tasks use exponential backoff retry: `countdown=60 * (2 ** self.request.retries)`, max 3 retries.

Current tasks:
- `users.send_registration_otp_email`
- `users.send_password_reset_otp_email`
- `users.send_welcome_email`

---

## Notification Delivery Strategy

| Recipient | Delivery |
|---|---|
| Male / Female / Wali | DB record only — mobile app polls REST |
| Matchmaker / Superadmin | DB record + WebSocket push |

Use `NotificationTemplates` (in `notifications/services.py`) — never call `NotificationService.send()` directly from views or other apps.

---

## What NOT to Do

- ❌ Never put business logic in views
- ❌ Never call `NotificationService.send()` directly — always use `NotificationTemplates`
- ❌ Never create a standard `Match` row for private matchmaking flows
- ❌ Never use `AllowedHostsOriginValidator` in `asgi.py`
- ❌ Never use `localStorage` or browser storage in any artifact
- ❌ Never use `is_staff` / `is_superuser` to check roles — always use `user.role`
- ❌ Never skip `@extend_schema` on any endpoint
- ❌ Never use `ManyToManyField` for choice lists — use `JSONField(default=list)`
- ❌ Never expose private matchmaking client profiles in standard directory
