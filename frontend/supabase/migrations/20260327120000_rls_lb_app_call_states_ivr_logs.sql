/*
  # RLS: allow lb_app on call_states and ivr_logs (IVR / FastAPI)

  Existing policies target Supabase JWT role `authenticated` only. The Python backend
  connects as `lb_app` when APP_DATABASE_URL is set; with RLS enabled and no policy
  for that role, Postgres denies all rows — get_call_state / upsert_call_state / ivr_logs
  INSERT fail and the IVR plays the generic error message.

  Idempotent: safe to re-run.
*/

ALTER TABLE call_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE ivr_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "rls_lb_app_call_states_all" ON call_states;
CREATE POLICY "rls_lb_app_call_states_all"
  ON call_states
  FOR ALL
  TO lb_app
  USING (true)
  WITH CHECK (true);

DROP POLICY IF EXISTS "rls_lb_app_ivr_logs_all" ON ivr_logs;
CREATE POLICY "rls_lb_app_ivr_logs_all"
  ON ivr_logs
  FOR ALL
  TO lb_app
  USING (true)
  WITH CHECK (true);
