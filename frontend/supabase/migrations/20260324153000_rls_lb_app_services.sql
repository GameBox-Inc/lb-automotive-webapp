/*
  # RLS: allow lb_app to read/write services (catalog)

  Problem: Earlier migrations added RLS on `services` with policies TO authenticated only
  (Supabase JWT role). The FastAPI backend connects as **lb_app** when APP_DATABASE_URL is set,
  so no policy matched and SELECT returned no rows — kiosk/IVR and GET /api/services looked empty.

  Fix: Add lb_app policies so the backend role can use the services catalog. Application routes
  still enforce admin for create/update/delete.

  Idempotent: safe to re-run.
*/

ALTER TABLE services ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "rls_lb_app_services_select" ON services;
DROP POLICY IF EXISTS "rls_lb_app_services_insert" ON services;
DROP POLICY IF EXISTS "rls_lb_app_services_update" ON services;
DROP POLICY IF EXISTS "rls_lb_app_services_delete" ON services;
DROP POLICY IF EXISTS "rls_lb_app_services_all" ON services;

-- Split policies so we can mirror appointment-style rules later if needed; for now catalog is trusted to app layer.
CREATE POLICY "rls_lb_app_services_select"
  ON services FOR SELECT TO lb_app
  USING (true);

CREATE POLICY "rls_lb_app_services_insert"
  ON services FOR INSERT TO lb_app
  WITH CHECK (true);

CREATE POLICY "rls_lb_app_services_update"
  ON services FOR UPDATE TO lb_app
  USING (true)
  WITH CHECK (true);

CREATE POLICY "rls_lb_app_services_delete"
  ON services FOR DELETE TO lb_app
  USING (true);
