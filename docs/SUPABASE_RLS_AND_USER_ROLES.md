# Supabase RLS and User Roles (Admin vs Staff)

## Is appointment access controlled at the database level (Supabase)?

**Short answer: No.** Access control for appointments is enforced in the **application layer** (FastAPI), not by Supabase RLS in a way that distinguishes admin vs staff.

- **Current Supabase migrations:** The `appointments` table has RLS enabled with policies such as "Allow authenticated users to read/update/insert appointments" (`TO authenticated`). Those policies apply when the **Supabase Auth** role is `authenticated` (e.g. when using the Supabase JS client with a real Supabase JWT).
- **How the backend connects:** The FastAPI backend uses a **single connection** to Postgres via `DATABASE_URL` (typically the Supabase direct connection string as `postgres` or the pooler). That role usually **bypasses RLS** (Postgres superuser / service role), so all backend requests run with full table access. The backend does **not** set a different Postgres user or JWT per request.
- **Implication:** Who can create/see/update appointments is decided in Python (e.g. in `appointment_repository.list_appointments` and route dependencies like `get_current_active_user`), not by Supabase RLS. So "database level" enforcement of admin vs staff does **not** exist today; it is application-level only.

If you later switch to a connection that does **not** bypass RLS (e.g. a dedicated role that is subject to RLS), you would need RLS policies that grant that role the right access (e.g. SELECT/INSERT/UPDATE on `appointments`) or use a per-request role (e.g. `SET LOCAL role = ...` based on JWT), which would require backend changes.

---

## Do we have proper user configuration to separate admin vs staff?

**Yes, at the application level.** The `users` table (created by the backend’s `init_db()` or by your schema process) has:

| Column     | Purpose |
|-----------|--------|
| `is_admin` | `1` = admin, `0` = non-admin. Used by the backend to restrict admin-only endpoints (e.g. services create/update/delete, business hours). |
| `staff_id` | Optional FK to `staff.id`. When set, the user is a staff member (e.g. mechanic, advisor). Used for "staff see their assigned appointments or unassigned" in `list_appointments`. |

So we **do** have a clear separation:

- **Admin:** `is_admin = 1`. Can manage services, business hours, and (in the app) see all appointments.
- **Staff:** `staff_id` set (and typically `is_admin = 0` unless they are also admin). Can create appointments and see their own or unassigned ones, as implemented in `appointment_repository.list_appointments`.
- **Other users:** `is_admin = 0` and no `staff_id`. Treated as "regular" users; the repo can restrict them to their own appointments (e.g. by `user_id` or `phone_number`).

This is **not** "proper RLS" in the Supabase sense (different Postgres roles per user). It is **proper application-level role separation** using `users.is_admin` and `users.staff_id`, with the backend applying the rules in code. RLS in Supabase is currently either bypassed (backend) or used for Supabase Auth (`authenticated`) in the existing policies.

---

## Summary

| Question | Answer |
|----------|--------|
| Is appointment create/access enforced at the **database level** in Supabase? | No. Backend uses a single connection that bypasses RLS; enforcement is in the app. |
| Do we have proper **user** configuration for admin vs staff? | Yes. `users.is_admin` and `users.staff_id` define roles; the backend uses them for access control. |
| Is that "proper RLS"? | It is proper **application-level** access control. It is **not** Supabase RLS that differentiates admin vs staff at the DB. |

To add true DB-level RLS for admin vs staff you would need to either: (1) run each request as a Postgres role that corresponds to the current user and add policies on that role, or (2) keep using a single privileged connection and continue relying on application-level checks (current setup).
