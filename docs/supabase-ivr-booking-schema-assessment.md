# Supabase schema assessment: IVR and booking

**Date:** 2026-03-05  
**Method:** Supabase MCP `execute_sql` + codebase review of `python-backend` (webhook, scheduling engine, call_state store, database).

---

## Summary

| Area | Status | Notes |
|------|--------|--------|
| **Tables exist** | ✅ | All IVR/booking tables present: `call_states`, `ivr_logs`, `ivr_analytics`, `settings`, `business_hours`, `staff_schedules`, `staff`, `services`, `appointments`, `blackouts`. |
| **Columns match backend** | ✅ | Required columns for IVR and scheduling engine exist and types are compatible. |
| **Settings keys** | ✅ | `staff_count`, `ivr_transfer_number`, `ivr_repair_max_retries`, `ivr_recording_disclaimer_en` present. |
| **IVR → DB routing** | ✅ Fixed | IVR booking INSERT now sets `start_time`, `end_time`, `service_id`, and `source='ivr'` so the scheduling engine’s primary conflict path includes IVR-created appointments. |
| **RLS / connection** | ⚠️ Verify | Backend must use a role that can read/write these tables (e.g. service_role or postgres in `DATABASE_URL`). |

---

## Table-by-table (IVR and booking)

### call_states
- **Backend:** `database.get_call_state` / `upsert_call_state`; `store.update_decision_path` (reads/writes `decision_path`).
- **Expected columns:** id, call_sid, current_step, language, metadata (text/JSON), appointment_id, last_response_time, created_at, updated_at, decision_path.
- **Supabase:** All present, types OK (metadata as text is fine for `json.loads`).

### ivr_logs
- **Backend:** `store.log_ivr_interaction` — INSERT (id, call_sid, step, input).
- **Supabase:** id, call_sid, step, input, created_at ✅

### ivr_analytics
- **Backend:** `store.track_decision` — INSERT (id, call_sid, node_name, decision_taken, duration_seconds).
- **Supabase:** id, call_sid, node_name, decision_taken, timestamp, duration_seconds ✅

### settings
- **Backend:** `get_setting(key)`; webhook uses `staff_count` for bandwidth check; IVR uses recording disclaimer, repair retries, transfer number.
- **Supabase:** key, value, description, updated_at, updated_by. Required keys present ✅

### business_hours
- **Backend:** `scheduling.engine.compute_availability` — SELECT day_of_week, opening_time, closing_time, is_closed.
- **Supabase:** All present. Ensure 7 rows (0–6) with desired open/closed; weekend closed → no weekend slots.

### staff_schedules
- **Backend:** Engine SELECT staff_id, day_of_week, start_time, end_time, is_off.
- **Supabase:** id, staff_id, day_of_week, start_time, end_time, is_off, created_at, updated_at ✅

### staff
- **Backend:** Referenced by staff_schedules.staff_id; staff routes for CRUD.
- **Supabase:** id, name, role, active, created_at ✅

### services
- **Backend:** Engine uses id, duration_minutes (fallback duration); webhook SELECT by category, is_emergency.
- **Supabase:** id, name, description, duration, price, is_emergency, category, duration_minutes, ... ✅  
- **Data:** Backfill `duration_minutes` from `duration` where null so engine uses correct slot length.

### appointments
- **Backend:**  
  - Engine: primary path SELECT id, technician_id, start_time, end_time WHERE start_time IS NOT NULL; legacy path SELECT assigned_staff_id AS technician_id, appointment_time WHERE appointment_time IS NOT NULL.  
  - Webhook: INSERT (id, customer_name, phone_number, appointment_time, service_type, status, notes); bandwidth check by appointment_time, status.
- **Supabase:** All columns present, including start_time, end_time, service_id, technician_id, source, vehicle_*.
- **Update:** IVR INSERT in `handle_booking` now sets start_time, end_time (from chosen slot + service duration), service_id, and source='ivr' so the engine’s primary conflict path includes IVR-created appointments.

### blackouts
- **Backend:** Engine SELECT start_time, end_time, scope, technician_id.
- **Supabase:** id, reason, start_time, end_time, scope, technician_id, created_at, updated_at ✅

---

## Recommendations

1. **IVR booking INSERT**  
   Done: `handle_booking` now sets `start_time`, `end_time`, `service_id`, and `source='ivr'` when inserting into `appointments`.

2. **Connection / RLS**  
   Ensure `DATABASE_URL` uses a Supabase role that can read/write all of the above tables (e.g. service_role or postgres). If using a restricted role, add or adjust RLS policies so the backend can access these tables.

3. **Data**  
   - `business_hours`: 7 rows (0=Mon … 6=Sun); set opening_time/closing_time/is_closed per day.  
   - `services`: Run `UPDATE services SET duration_minutes = COALESCE(duration_minutes, duration) WHERE duration_minutes IS NULL AND duration IS NOT NULL;` if needed.

4. **Re-validate**  
   After code or schema changes, re-run this assessment (e.g. MCP `list_tables` + `execute_sql` on `information_schema.columns` and key settings/rows).
