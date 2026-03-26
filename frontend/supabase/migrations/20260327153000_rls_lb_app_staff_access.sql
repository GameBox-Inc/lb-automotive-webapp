/*
  # RLS: allow lb_app on staff (System Admin audit fallback)

  Observed failure:
  - POST /api/cases -> InsufficientPrivilege: new row violates row-level security policy for table "staff"
  - Triggered by backend route `routes/cases.py::_get_staff_id_for_audit()`, which inserts a
    "System Admin" row into `staff` when an admin user has no `staff_id`.

  Fix:
  - Ensure RLS is enabled and add an idempotent policy granting lb_app full access.

  Idempotent and safe to re-run.
*/

ALTER TABLE public.staff ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "rls_lb_app_staff_all" ON public.staff;

CREATE POLICY "rls_lb_app_staff_all"
  ON public.staff
  FOR ALL
  TO lb_app
  USING (true)
  WITH CHECK (true);

