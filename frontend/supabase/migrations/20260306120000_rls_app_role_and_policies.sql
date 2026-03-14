/*
  # RLS: lb_app role and session-variable policies for appointments

  Run as postgres (or service role). Creates role lb_app for the backend so that
  Row Level Security is enforced via session variables set by the app per request.

  - Creates role lb_app with placeholder password (change in Supabase and set APP_DATABASE_URL).
  - Grants lb_app access to all tables in public used by the app.
  - Adds RLS policies on appointments for lb_app using app.current_user_id,
    app.is_admin, app.staff_id, app.service_request.

  Idempotent: safe to run multiple times.
*/

-- Ensure appointments has columns used by RLS (backend may have created them)
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS user_id text;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS assigned_staff_id text;

-- Create lb_app role if it does not exist (password must be changed in Supabase and stored in APP_DATABASE_URL)
DO
$do$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lb_app') THEN
    CREATE ROLE lb_app LOGIN PASSWORD 'changeme';
    RAISE NOTICE 'Role lb_app created. Change password in Supabase and set APP_DATABASE_URL for the backend.';
  ELSE
    RAISE NOTICE 'Role lb_app already exists.';
  END IF;
EXCEPTION
  WHEN duplicate_object THEN
    RAISE NOTICE 'Role lb_app already exists (concurrent create).';
END
$do$;

-- Grant connect and usage (required for any connection)
GRANT CONNECT ON DATABASE postgres TO lb_app;
GRANT USAGE ON SCHEMA public TO lb_app;

-- Grant full access to all existing and future tables in public (app needs read/write on all)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO lb_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO lb_app;

-- Ensure RLS is enabled on appointments (already done in earlier migration; harmless if repeated)
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;

-- Drop existing lb_app policies if present (idempotent re-run)
DROP POLICY IF EXISTS "rls_lb_app_appointments_select" ON appointments;
DROP POLICY IF EXISTS "rls_lb_app_appointments_insert" ON appointments;
DROP POLICY IF EXISTS "rls_lb_app_appointments_update" ON appointments;
DROP POLICY IF EXISTS "rls_lb_app_appointments_delete" ON appointments;

-- SELECT: service request (IVR/cron), admin, staff (own + unassigned), or user (own rows)
CREATE POLICY "rls_lb_app_appointments_select"
  ON appointments FOR SELECT TO lb_app
  USING (
    current_setting('app.service_request', true) = 'true'
    OR current_setting('app.is_admin', true) = 'true'
    OR (
      current_setting('app.staff_id', true) IS NOT NULL
      AND current_setting('app.staff_id', true) <> ''
      AND (assigned_staff_id::text = current_setting('app.staff_id', true) OR assigned_staff_id IS NULL)
    )
    OR (
      current_setting('app.current_user_id', true) IS NOT NULL
      AND current_setting('app.current_user_id', true) <> ''
      AND user_id::text = current_setting('app.current_user_id', true)
    )
  );

-- INSERT: service request, admin, or any authenticated user (current_user_id set)
CREATE POLICY "rls_lb_app_appointments_insert"
  ON appointments FOR INSERT TO lb_app
  WITH CHECK (
    current_setting('app.service_request', true) = 'true'
    OR current_setting('app.is_admin', true) = 'true'
    OR (
      current_setting('app.current_user_id', true) IS NOT NULL
      AND current_setting('app.current_user_id', true) <> ''
    )
  );

-- UPDATE: same visibility as SELECT (service, admin, staff for their/unassigned, user for own)
CREATE POLICY "rls_lb_app_appointments_update"
  ON appointments FOR UPDATE TO lb_app
  USING (
    current_setting('app.service_request', true) = 'true'
    OR current_setting('app.is_admin', true) = 'true'
    OR (
      current_setting('app.staff_id', true) IS NOT NULL
      AND current_setting('app.staff_id', true) <> ''
      AND (assigned_staff_id::text = current_setting('app.staff_id', true) OR assigned_staff_id IS NULL)
    )
    OR (
      current_setting('app.current_user_id', true) IS NOT NULL
      AND current_setting('app.current_user_id', true) <> ''
      AND user_id::text = current_setting('app.current_user_id', true)
    )
  )
  WITH CHECK (true);

-- DELETE: service request or admin only
CREATE POLICY "rls_lb_app_appointments_delete"
  ON appointments FOR DELETE TO lb_app
  USING (
    current_setting('app.service_request', true) = 'true'
    OR current_setting('app.is_admin', true) = 'true'
  );
