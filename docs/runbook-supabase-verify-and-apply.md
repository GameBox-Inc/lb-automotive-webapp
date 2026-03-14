# Supabase: verify tables, migrations, and data

Use this after deploying or when debugging IVR/Kiosk "fully booked" or "no times".

## 1. List tables (Supabase MCP or SQL)

**Via Supabase MCP:** In Cursor, use the Supabase MCP tool **`list_tables`**.

**Via SQL:** In Supabase Dashboard → SQL Editor, or `psql $DATABASE_URL`:

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN (
  'business_hours', 'staff_schedules', 'staff', 'blackouts',
  'services', 'appointments', 'call_states', 'ivr_logs', 'settings',
  'users', 'customers', 'cases'
)
ORDER BY table_name;
```

Expected: all of the above should exist. Backend needs at least `business_hours`, `staff_schedules`, `services`, `appointments`, `call_states`, `settings`.

## 2. List migrations (Supabase MCP or CLI)

**Via Supabase MCP:** Use **`list_migrations`** to see applied migrations.

**Via CLI:** From repo root with Supabase linked:

```bash
npx supabase db remote list
# or
supabase migration list
```

Ensure these are applied (or run the migration script):

- `20260305123000_scheduling_engine_schema.sql` — creates staff, business_hours, staff_schedules, blackouts; adds columns to services/appointments.
- `20260305140000_seed_business_hours_and_routing.sql` — seeds business_hours (Mon–Sun 08:00–18:00), backfills services.duration_minutes.

## 3. Apply migrations (Supabase MCP or pipeline)

**Via Supabase MCP:** Use **`apply_migration`** for the migration file(s) above if they are pending.

**Via pipeline:** Push to your branch and let Jenkins run `Run Supabase Migrations` (uses `deployment/scripts/run_supabase_migrations.sh` and `DATABASE_URL` from credentials).

**Via local psql:**

```bash
export DATABASE_URL="postgresql://..."   # your Supabase connection string
bash deployment/scripts/run_supabase_migrations.sh
```

## 4. Verify business_hours has rows (fix if empty)

**Via Supabase MCP:** Use **`execute_sql`** with:

```sql
SELECT day_of_week, opening_time, closing_time, is_closed FROM business_hours ORDER BY day_of_week;
```

If this returns **0 rows**, the scheduling engine falls back to in-memory Mon–Fri only (weekend = "fully booked"). Apply the seed migration or run manually:

```sql
INSERT INTO business_hours (day_of_week, opening_time, closing_time, is_closed, updated_at)
VALUES
  (0, '08:00', '18:00', 0, now()),
  (1, '08:00', '18:00', 0, now()),
  (2, '08:00', '18:00', 0, now()),
  (3, '08:00', '18:00', 0, now()),
  (4, '08:00', '18:00', 0, now()),
  (5, '08:00', '18:00', 0, now()),
  (6, '08:00', '18:00', 0, now())
ON CONFLICT (day_of_week) DO NOTHING;
```

Then restart (or redeploy) the backend so it picks up the seeded data.

## 5. Confirm which database the backend uses

The backend reads `business_hours`, `staff_schedules`, etc. from the DB pointed to by **`DATABASE_URL`** (K8s `app-secrets` or Vault). Supabase MCP in Cursor is connected to a specific project (e.g. "user-supabase"). If they differ, updates made via MCP or Dashboard only affect the MCP-linked project; the app will keep showing "No slots available" until the **backend's** database is updated.

**To confirm alignment:**

1. **Backend DB:** On the server, read the backend's `DATABASE_URL` (mask the password):
   ```bash
   sudo k3s kubectl get secret app-secrets -n lb-automotive -o jsonpath='{.data.DATABASE_URL}' | base64 -d
   ```
   Note the host (e.g. `db.xxxx.supabase.co`) and project ref.

2. **MCP project:** In Supabase Dashboard or Cursor MCP settings, note which project "user-supabase" (or your MCP connection) points to. Compare the host/project with the backend's `DATABASE_URL`.

3. **Apply updates to the right place:** Run migrations and any manual SQL (e.g. `UPDATE business_hours`) against the **same** project the backend uses. Use the in-app **Admin → IVR → Configuration (Business Hours)** and **Admin → Staff (Schedules)** to change data in the backend's DB; or run SQL in the Supabase project that matches `DATABASE_URL`.
