/*
  # RLS: allow lb_app access to users (auth bootstrap)

  Problem:
  - Backend uses role `lb_app` when `APP_DATABASE_URL` is set.
  - `lb_app` currently sees `0` rows in `public.users`, even though the table has admin rows.
  - This makes the app behave like admin accounts were "removed" because login/user fetches return none.

  Fix:
  - Add an idempotent RLS policy for `lb_app` on `public.users`.
  - Allow the backend (lb_app) to SELECT/INSERT/UPDATE/DELETE users.
  - Route-level authorization remains enforced in FastAPI; RLS is second-layer defense.
*/

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "rls_lb_app_users_all" ON public.users;

CREATE POLICY "rls_lb_app_users_all"
  ON public.users
  FOR ALL
  TO lb_app
  USING (true)
  WITH CHECK (true);

