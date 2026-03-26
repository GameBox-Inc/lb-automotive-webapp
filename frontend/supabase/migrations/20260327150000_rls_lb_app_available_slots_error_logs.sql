/*
  # RLS: allow lb_app on available_slots and error_logs

  These tables already have RLS with policies for Supabase `authenticated` only.
  The FastAPI backend uses role `lb_app` when APP_DATABASE_URL is set; without
  explicit `TO lb_app` policies, any future or edge-path access from the backend
  would be denied.

  Idempotent: safe to re-run.
*/

-- available_slots (see 20250504015750_heavy_leaf.sql)
ALTER TABLE public.available_slots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "rls_lb_app_available_slots_all" ON public.available_slots;
CREATE POLICY "rls_lb_app_available_slots_all"
  ON public.available_slots
  FOR ALL
  TO lb_app
  USING (true)
  WITH CHECK (true);

-- error_logs (see 20250504040140_square_beacon.sql)
ALTER TABLE public.error_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "rls_lb_app_error_logs_all" ON public.error_logs;
CREATE POLICY "rls_lb_app_error_logs_all"
  ON public.error_logs
  FOR ALL
  TO lb_app
  USING (true)
  WITH CHECK (true);
