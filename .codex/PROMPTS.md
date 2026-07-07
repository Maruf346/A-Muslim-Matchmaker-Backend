# PROMPTS.md — Reusable Prompt Templates for AMM Backend

Use these prompts when asking an AI agent to perform common tasks.
Always read `PROJECT_CONTEXT.md` and `AGENTS.md` first for full context.

---

## 1. Add a new API endpoint

```
Context: AMM Django backend. Read AGENTS.md and PROJECT_CONTEXT.md.

Add a new endpoint to the `<app_name>` app:
- Purpose: <describe what it does>
- HTTP method: GET / POST / PATCH / DELETE
- URL: /api/<prefix>/<path>/
- Who can access: <Male / Female / Wali / Admin / All authenticated>
- Request fields: <list fields>
- Response fields: <list fields>

Follow the thin-views / fat-services pattern.
Add @extend_schema with summary, description, request, and responses.
Use permission class from users/permissions.py.
Tag format: "<AppName> - <Audience>"
```

---

## 2. Add a new model

```
Context: AMM Django backend. Read AGENTS.md and PROJECT_CONTEXT.md.

Add a new model to `<app_name>/models.py`:
- Model name: <Name>
- Purpose: <describe>
- Fields: <list with types>
- Optional fields should be blank=True, null=True
- Use UUID primary key
- Add created_at (auto_now_add) and updated_at (auto_now)
- Add __str__, Meta.ordering, and relevant indexes

Then create a migration stub reminder (don't run it, just note it).
```

---

## 3. Add a new notification type

```
Context: AMM Django backend. Read AGENTS.md and PROJECT_CONTEXT.md.

Add a new notification type for: <describe the event>

Steps:
1. Add a new entry to `NotificationType` TextChoices in notifications/models.py
2. Add a static method to `NotificationTemplates` in notifications/services.py
   - Recipient: <who receives it>
   - Delivery: DB only (normal user) or DB + WS push (admin)
   - Priority: LOW / NORMAL / HIGH / URGENT
   - Title and body copy

Never call NotificationService.send() directly from outside notifications/services.py.
```

---

## 4. Add a new Celery task

```
Context: AMM Django backend. Read AGENTS.md and PROJECT_CONTEXT.md.

Add a new Celery task to `<app_name>/tasks.py`:
- Task name: <app_name>.<task_name>
- Purpose: <describe>
- Input args: <list>
- Retry policy: max_retries=3, countdown=60*(2**retries)
- Use @shared_task(bind=True, max_retries=3)
- Use logger.error() on failure before raising self.retry()
```

---

## 5. Debug an existing endpoint

```
Context: AMM Django backend. Read AGENTS.md and PROJECT_CONTEXT.md.

I'm getting this error on endpoint `<METHOD> /api/<path>/`:
<paste error / traceback>

The endpoint is in `<app_name>/views.py`.
The relevant service is in `<app_name>/services.py`.

Please diagnose and fix the issue following AMM coding standards.
Do not move business logic into the view. Do not skip @extend_schema.
```

---

## 6. Add filtering/search to an existing viewset

```
Context: AMM Django backend. Read AGENTS.md and PROJECT_CONTEXT.md.

Add filtering and search to `<ViewSetName>` in `<app_name>/views.py`:
- Search fields: <list>
- Filter fields: <list with types>
- Ordering fields: <list>
- Default ordering: <field>

Use DRF's SearchFilter and OrderingFilter.
Add OpenApiParameter entries to @extend_schema.
```

---

## 7. Add a new app

```
Context: AMM Django backend. Read AGENTS.md and PROJECT_CONTEXT.md.

Create a new Django app named `<app_name>`:
- Purpose: <describe>
- Models: <list>
- Endpoints: <list with methods and paths>
- Swagger tag prefix: "<AppName> - "

File structure required:
  models.py / serializers.py / services.py / views.py / urls.py / apps.py

After creating files, provide:
1. The line to add to settings.py INSTALLED_APPS
2. The line to add to api/urls.py
3. Migration command to run
```

---

## 8. Write a test for an endpoint

```
Context: AMM Django backend. Read AGENTS.md and PROJECT_CONTEXT.md.

Write a Django test for the endpoint `<METHOD> /api/<path>/` in `<app_name>/tests.py`.

Test cases to cover:
- Happy path: <describe>
- Auth failure (no token)
- Wrong role access (403)
- Validation error (400): <describe invalid input>

Use `APITestCase` from `rest_framework.test`.
Create test users with role=<role> using `User.objects.create(...)`.
```

---

## 9. Fix a migration conflict

```
Context: AMM Django backend. Read AGENTS.md and PROJECT_CONTEXT.md.

I have a migration conflict in the `<app_name>` app.
Running `python manage.py migrate` gives: <paste error>

Diagnose and provide the correct resolution steps.
Do not suggest squashing migrations unless absolutely necessary.
```

---

## 10. Add a management command (data migration)

```
Context: AMM Django backend. Read AGENTS.md and PROJECT_CONTEXT.md.

Create a management command at `<app_name>/management/commands/<command_name>.py`:
- Purpose: <describe — e.g. import legacy user data>
- Source data format: <CSV / JSON / existing DB>
- Target models: <list>
- Handle errors gracefully — log failures, don't abort the whole import
- Use transaction.atomic() per row or per batch
- Print progress with self.stdout.write()
```

---

## Quick reference — key file locations

| What | Where |
|---|---|
| User model | `users/models.py` → `User` class |
| Role choices | `users/models.py` → `UserRole` TextChoices |
| Permission classes | `users/permissions.py` |
| Notification templates | `notifications/services.py` → `NotificationTemplates` |
| Visibility exclusion | `wishlists/services.py` → `VisibilityService.get_excluded_user_ids()` |
| Subscription limits | `matches/services.py` → `SubscriptionLimitService` |
| Match lifecycle | `matches/services.py` → `MatchService` |
| Codename generation | `users/models.py` → `generate_codename(role)` |
| All dropdown choices | `questions/choices.py` |
| WebSocket routing | `core/asgi.py` |
| Chat consumer | `chat/consumers.py` |
| Notification consumer | `notifications/consumers.py` |
| URL aggregator | `api/urls.py` |
| Docker compose (dev) | `docker-compose.yml` |
| CI workflow | `.github/workflows/ci.yml` |
| Deploy workflow | `.github/workflows/deploy.yml` |
| Env template | `.env.example` |
