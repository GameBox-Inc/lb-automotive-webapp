# Supabase RLS and User Roles (Admin vs Staff)

## Database-level RLS (implemented)

When the backend connects with the **lb_app** role (via `APP_DATABASE_URL`), Row Level Security is enforced on the `appointments` table. The app sets Postgres session variables per request; RLS policies use them to allow or deny rows.

### How it works

1. **Connection:** The app uses `APP_DATABASE_URL` when set (else `DATABASE_URL`). `APP_DATABASE_URL` should be the connection string for the **lb_app** role so that RLS applies. Migrations and `init_db()`/`seed_data()` use `DATABASE_URL` (postgres) so DDL and seeding are not restricted by RLS.

2. **Session variables (set in `database.get_db_connection()`):**
   - `app.service_request` — `'true'` for IVR/cron requests; RLS allows full access to appointments.
   - `app.current_user_id` — Authenticated user’s id (from JWT).
   - `app.is_admin` — `'true'` or `'false'`.
   - `app.staff_id` — Staff id when the user is staff (or empty).

3. **Policies on `appointments` (for role lb_app):**
   - **SELECT/UPDATE:** Allowed if `app.service_request = 'true'`, or `app.is_admin = 'true'`, or (staff sees rows where `assigned_staff_id` = their `staff_id` or is NULL), or (user sees rows where `user_id` = their `current_user_id`).
   - **INSERT:** Allowed if service request, admin, or `app.current_user_id` is set (authenticated user).
   - **DELETE:** Allowed only for service request or admin.

4. **Service context:** The Twilio webhook sets `service_request_context` (and thus `app.service_request = 'true'`) via the `ivr_service_context` dependency so IVR can read/write appointments and related data. Cron or other server-to-server paths that need full access should set `service_request_context.set(True)` for the duration of the request.

### Tables with RLS (Phase 1)

- **appointments** — RLS enabled with lb_app policies above (session variables).
- **services** — Supabase migrations added RLS policies for the **`authenticated`** role only. When the backend uses **`lb_app`** (`APP_DATABASE_URL`), those policies do not apply, so **no rows were visible** until migration `20260324153000_rls_lb_app_services.sql` added `lb_app` SELECT/INSERT/UPDATE/DELETE policies. The app still restricts service management to admins in route code.

---

## User configuration (application-level)

The `users` table defines roles used by the app and by RLS session variables:

| Column     | Purpose |
|-----------|--------|
| `is_admin` | `1` = admin, `0` = non-admin. Backend restricts admin-only endpoints; RLS uses `app.is_admin` for appointments. |
| `staff_id` | Optional FK to `staff.id`. When set, user is staff; RLS uses `app.staff_id` for staff-scoped appointment visibility. |

- **Admin:** `is_admin = 1`. Sees all appointments (RLS and app).
- **Staff:** `staff_id` set. Sees appointments assigned to them or unassigned (RLS and app).
- **Other users:** See only their own appointments (`user_id` / `app.current_user_id`).

---

## Summary

| Question | Answer |
|----------|--------|
| Is appointment access enforced at the **database level** when using lb_app? | Yes. When `APP_DATABASE_URL` is set, the app connects as lb_app and RLS on `appointments` enforces visibility and write access via session variables. |
| How does the backend set the “current user” for RLS? | Auth sets `current_user_context`; IVR sets `service_request_context`. `get_db_connection()` runs `SET app.service_request`, `app.current_user_id`, `app.is_admin`, `app.staff_id` on each connection. |
| Do we still need application-level checks? | Yes. Keep route dependencies (e.g. `get_current_admin_user`) and repo filters as defense-in-depth. RLS adds a second enforcement layer at the DB. |
| Password for lb_app? | The migration creates lb_app with placeholder password `changeme`. Change it in Supabase (e.g. `ALTER ROLE lb_app PASSWORD '...'`) and set `APP_DATABASE_URL` in Vault to the lb_app connection string. |

---

## RLS troubleshooting

**Symptom: Services page / kiosk / IVR shows no services, or `GET /api/services` returns `[]`, while DB has rows.**  
If `APP_DATABASE_URL` is set, the API uses role `lb_app`. RLS on `services` must include policies **TO lb_app** (see migration `20260324153000_rls_lb_app_services.sql`). Apply pending Supabase migrations on the deploy pipeline or run `deployment/scripts/run_supabase_migrations.sh` with `DATABASE_URL` set.

If the app or IVR cannot access appointments when using `APP_DATABASE_URL`:

1. **Confirm the app is using lb_app:** Check that `APP_DATABASE_URL` is set (e.g. in Vault / pod env) and points to the lb_app user.
2. **Confirm session variables:** In development, you can log or inspect that `app.service_request` / `app.current_user_id` / `app.is_admin` / `app.staff_id` are set as expected for the request type (IVR vs authenticated user).
3. **IVR/cron:** Ensure the Twilio webhook uses the `ivr_service_context` dependency and that any cron job sets `service_request_context.set(True)` before DB access.
4. **Migrations:** Migrations and `init_db()`/`seed_data()` use `DATABASE_URL` (postgres), not lb_app; they are not subject to RLS.

See also: runbook section “RLS blocking expected access” in `docs/runbooks/k8s-debugging.md`.
