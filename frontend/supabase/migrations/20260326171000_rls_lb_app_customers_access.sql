/*
  # RLS: allow lb_app access to customers (kiosk/customer creation)

  Problem:
  - Backend runs as `lb_app` when `APP_DATABASE_URL` is set.
  - Creating a customer fails with:
    `new row violates row-level security policy for table "customers"`

  Fix:
  - Add an idempotent policy granting `lb_app` SELECT/INSERT/UPDATE/DELETE on `public.customers`.
  - Application-layer authorization still applies; this is to prevent RLS from breaking core flows.
*/

ALTER TABLE public.customers ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "rls_lb_app_customers_all" ON public.customers;

CREATE POLICY "rls_lb_app_customers_all"
  ON public.customers
  FOR ALL
  TO lb_app
  USING (true)
  WITH CHECK (true);

