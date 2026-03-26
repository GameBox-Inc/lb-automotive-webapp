/*
  # Repair cases: schema (if missing) + RLS for lb_app

  Problem:
  - Case/repair flows use `cases`, `case_notes`, `case_parts`, `case_status_history`.
  - Backend connects as `lb_app` when APP_DATABASE_URL is set.
  - RLS enabled with policies only for Supabase `authenticated` (or no lb_app policy)
    causes: new row violates row-level security policy for table "cases" (and related).

  Fix:
  - CREATE TABLE IF NOT EXISTS for case tables (idempotent; matches python-backend/database.py).
  - ENABLE ROW LEVEL SECURITY + FOR ALL TO lb_app policies (same pattern as customers/call_states).
*/

-- ---------------------------------------------------------------------------
-- Schema (safe if init_db already created the tables)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.cases (
  id TEXT PRIMARY KEY,
  case_number INTEGER,
  appointment_id TEXT NOT NULL UNIQUE,
  status TEXT DEFAULT 'open',
  customer_signature TEXT,
  metadata TEXT DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now(),
  started_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cases_appointment_id ON public.cases(appointment_id);

CREATE TABLE IF NOT EXISTS public.case_notes (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  staff_id TEXT NOT NULL,
  note TEXT NOT NULL,
  is_internal INTEGER DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_case_notes_case_id ON public.case_notes(case_id);

CREATE TABLE IF NOT EXISTS public.case_parts (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  part_name TEXT NOT NULL,
  quantity INTEGER DEFAULT 1,
  price double precision DEFAULT 0,
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_case_parts_case_id ON public.case_parts(case_id);

-- case_status_history may already exist from 20260314120000_case_status_history.sql
CREATE TABLE IF NOT EXISTS public.case_status_history (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  old_status TEXT,
  new_status TEXT NOT NULL,
  changed_at TIMESTAMPTZ DEFAULT now(),
  changed_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_case_status_history_case_id ON public.case_status_history(case_id);

-- ---------------------------------------------------------------------------
-- RLS: lb_app (FastAPI backend)
-- ---------------------------------------------------------------------------
ALTER TABLE public.cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_parts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_status_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "rls_lb_app_cases_all" ON public.cases;
CREATE POLICY "rls_lb_app_cases_all"
  ON public.cases
  FOR ALL
  TO lb_app
  USING (true)
  WITH CHECK (true);

DROP POLICY IF EXISTS "rls_lb_app_case_notes_all" ON public.case_notes;
CREATE POLICY "rls_lb_app_case_notes_all"
  ON public.case_notes
  FOR ALL
  TO lb_app
  USING (true)
  WITH CHECK (true);

DROP POLICY IF EXISTS "rls_lb_app_case_parts_all" ON public.case_parts;
CREATE POLICY "rls_lb_app_case_parts_all"
  ON public.case_parts
  FOR ALL
  TO lb_app
  USING (true)
  WITH CHECK (true);

DROP POLICY IF EXISTS "rls_lb_app_case_status_history_all" ON public.case_status_history;
CREATE POLICY "rls_lb_app_case_status_history_all"
  ON public.case_status_history
  FOR ALL
  TO lb_app
  USING (true)
  WITH CHECK (true);
