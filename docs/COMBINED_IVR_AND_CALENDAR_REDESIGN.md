# Combined Premium IVR + In-App Calendar Redesign

This document merges the **Premium IVR call entry redesign** with the **in-app calendar redesign** and the **dynamic booking / calendar availability** plan. The backend and Supabase DB are the single source of truth for availability; both IVR and web app use the same logic.

---

## 1. Architecture: Single source of truth

- **Availability** is computed from: `business_hours` + `staff_schedules` + `appointments` + `services` (duration). No separate "IVR calendar" or duplicate slot tables.
- **Backend** exposes:
  - `GET /appointments/available-slots?date=&service_id=` — used by both the **in-app calendar/booking flow** and (internally) by IVR.
  - Optional (for IVR + calendar): `GET /appointments/available-dates?service_id=&days=7` — returns next N days that have at least one slot (for multi-day IVR and for calendar “which days are bookable”).
- **Supabase** holds the same tables the backend uses: `appointments`, `business_hours`, `staff_schedules`, `settings`, `services`, `staff`, etc. New **settings** rows support IVR (transfer number, language prompt, disclaimer, repair retries). No separate `available_slots` table; slots are computed on demand.

---

## 2. Premium IVR call entry (summary)

- **First 5 seconds:** Recording disclaimer (once) → greeting from `ivr_greeting` → menu: “How can I help today? Press 1 or say appointment…”
- **Immediate speech routing:** Map “appointment”, “schedule”, “status”, “representative”, etc. to steps without LLM delay when possible.
- **Repair:** “I didn’t quite catch that. No problem — here are your options again.” Max 2 retries then transfer.
- **Real transfer:** Say “Connecting you. Please hold.” → Dial `ivr_transfer_number` (timeout 30s). No-answer → “Our team is currently assisting other customers. Please try again later.” → smooth hangup.
- **Smooth hangup:** Helper `smooth_hangup(response, voice, language)`: Pause 2s → Say “Thank you for calling LB Automotive. Goodbye.” → hangup.
- **Optional language step:** “For English press 1. Para español presione 2.” when `ivr_language_prompt_enabled` is true.
- **DB settings used:** `ivr_greeting`, `ivr_transfer_number`, `ivr_language_prompt_enabled`, `ivr_repair_max_retries` (default 2), `ivr_recording_disclaimer_en`, `ivr_recording_disclaimer_es`.

---

## 3. In-app calendar redesign (summary)

- **AppointmentCalendar** (existing): Continues to show appointment density per day (count + duration). Data: appointments from API; no schema change.
- **Booking flow:** When creating an appointment, the app already uses `getAvailableSlots(date, serviceId)` (backend). Redesign:
  - **Date picker:** Show only days that have availability (optional: call new `GET /appointments/available-dates` or derive from available-slots for next 7 days).
  - **Time picker:** After date is chosen, call existing `GET /appointments/available-slots?date=&service_id=` and show concrete times (e.g. 9:00, 10:00, 14:00). User selects one slot; submit creates the appointment at that exact time.
- **Backend:** Ensure `GET /appointments/available-slots` respects `business_hours`, `staff_schedules`, and existing `appointments` (already does). Add optional `GET /appointments/available-dates` that returns list of dates with at least one slot for a given service.

---

## 4. Dynamic booking (IVR + calendar)

- **IVR:** Add `select_date` step: “We have openings tomorrow, Wednesday, Thursday. Press 1 for tomorrow, 2 for Wednesday…” Store `target_date` and `available_slots` from `get_available_slots_logic(target_date, service_id)`. Then `select_time`: “We have 9, 10, 11, 2, and 3. Say or press the time.” Store `chosen_slot_time`; at booking re-check slot still available, then INSERT.
- **Calendar (web):** Same idea: pick date (from available-dates or next 7 days), then pick time from available-slots; create appointment at that datetime. Single source of truth: backend slot logic.

---

## 5. Supabase DB table updates

- **Tables:** No new tables required. Existing `settings`, `business_hours`, `staff_schedules`, `appointments`, `services`, `staff` support both IVR and calendar.
- **New settings rows (Supabase migration):**
  - `ivr_transfer_number` — E.164 number for representative transfer (Dial).
  - `ivr_language_prompt_enabled` — "true" | "false"; play language selection at start.
  - `ivr_repair_max_retries` — default "2"; max timeouts before transfer.
  - `ivr_recording_disclaimer_en` — “This call may be recorded for quality purposes.”
  - `ivr_recording_disclaimer_es` — Spanish equivalent.
- **Backend seed:** Add the same keys to `database.py` default_settings so backend init or seed keeps them in sync when running against the same DB.

---

## 6. Implementation checklist

| Area | Action |
|------|--------|
| Supabase | Run migration that inserts new IVR settings (ON CONFLICT DO NOTHING). |
| Backend | Add new settings to default_settings in database.py seed_data(). |
| Backend | Implement Premium IVR: disclaimer, ivr_greeting, phrase map, repair copy, smooth_hangup, transfer Dial, dial_complete, optional language_select. |
| Backend | Implement dynamic IVR booking: select_date, get_next_available_dates, select_time with specific slots, handle_booking re-check. |
| Backend | Optional: GET /appointments/available-dates for frontend. |
| Frontend | Calendar/booking: use available-slots for chosen date; show specific times; create appointment at chosen slot. |
| Frontend | Optional: available-dates to disable dates with no slots in date picker. |

---

## 7. Overlooked items: Jenkinsfile and frontend UI

### 7.1 Jenkinsfile

- **No pipeline code changes required** for IVR or calendar. Existing stages cover:
  - **Ensure App Secrets** — `SECRET_KEY`, `ALLOWED_ORIGINS`, `DATABASE_URL` (Supabase/PostgreSQL); no new env vars for IVR/calendar.
  - **Ensure Twilio Secrets** — `TWILIO_AUTH_TOKEN` already synced for webhook signature validation.
  - **Deploy Manifests / Deploy to Production** — backend and frontend images; no new K8s resources for IVR/calendar.
- **Operational note:** New IVR settings (`ivr_transfer_number`, `ivr_language_prompt_enabled`, etc.) live in the **database** (`settings` table). Admins configure them via **Admin IVR** in the app, not via Jenkins credentials. If using Supabase-managed schema, run the new migration once (`frontend/supabase/migrations/20260305120000_ivr_and_calendar_support.sql`) via `supabase db push` or the Supabase SQL editor; Jenkins does not run Supabase migrations.

### 7.2 Frontend UI

- **Admin IVR (`AdminIVR.tsx`):**
  - **New settings visibility:** All new keys (`ivr_transfer_number`, `ivr_language_prompt_enabled`, `ivr_repair_max_retries`, `ivr_recording_disclaimer_en`, `ivr_recording_disclaimer_es`) appear under **IVR Messages** (filter is `ivr_*` excluding only `ivr_voice` and `ivr_language`). They are editable with the existing Edit/Save pattern.
  - **Optional UX improvements:** (1) Add a **Transfer & behaviour** subsection: show `ivr_transfer_number` with an E.164 placeholder/hint; show `ivr_language_prompt_enabled` as a toggle (true/false); show `ivr_repair_max_retries` as a number input. (2) Keep disclaimer texts in IVR Messages.
  - **Pre-existing bug:** The **Business Hours** section uses `businessHours`, `editingDay`, and `editHours` but these state variables are **not declared** in the component (no `useState` for them), and `fetchBusinessHours()` is never called in `useEffect`. The Business Hours table will crash when the Config tab is opened. **Fix:** Add `useState` for `businessHours`, `editingDay`, `editHours` and call `fetchBusinessHours()` on mount (e.g. in `useEffect` when `activeTab === 'config'`).

- **Appointments page (`Appointments.tsx`):**
  - **Current behaviour:** Add-appointment flow already uses **Date** (free date input) and **Available Times** from `getAvailableSlots(selectedDate, serviceId)` (backend). User picks date and a slot; submit sends the chosen time. Aligned with the plan.
  - **Optional enhancement:** If the backend adds `GET /appointments/available-dates?service_id=&days=7`, add `getAvailableDates(serviceId, days?)` in `frontend/src/lib/supabase.ts` and use it to restrict or highlight the date picker (e.g. only allow dates that have at least one slot). Not required for the combined plan.

- **AppointmentCalendar:** No change needed; it shows appointment density and `onDateClick` opens the Add modal with that date pre-filled.

- **Settings page:** IVR keys are not shown here (they live under Admin IVR). No change.

### 7.3 Backend

- **Settings API:** `GET /api/settings` and `PUT /api/settings/{key}` already return/update any key in `settings`. New IVR keys are stored and updated the same way; no API changes.

### 7.4 Kiosk (CheckIn) and the new calendar system

- **Current behaviour:** The Kiosk (`/checkin`, [frontend/src/pages/CheckIn.tsx](frontend/src/pages/CheckIn.tsx)) is a **walk-in only** flow: phone → confirm customer → select service → create appointment with `appointment_time: new Date().toISOString()` (i.e. “now”). It does **not** call `getAvailableSlots` or any date/time picker; it does not use the shared calendar/slot engine.
- **Gap:** The combined plan did not previously address the Kiosk. The architecture diagram (Web & Kiosk) describes both using the same slot logic, but only the **Appointments** page uses the available-slots API; the Kiosk does not.
- **Ways to reflect the new calendar system:**
  1. **Leave as walk-in only (minimal):** Document that the Kiosk creates “now” appointments in the same `appointments` table, so staff views and availability (e.g. slot consumption) already see kiosk check-ins. No code change; only documentation.
  2. **Add optional “Book a future slot” at Kiosk:** Add a step (e.g. “Check in now” vs “Book a time”) so customers can choose to book a future slot. Reuse the same APIs: `getAvailableSlots(date, serviceId)` and optionally `getAvailableDates(serviceId, days)` once available. Flow: select service → choose date (from available-dates or next N days) → choose time from available-slots → create appointment at that datetime. Same backend and calendar rules as IVR and web.

| Option | Action |
|--------|--------|
| Walk-in only | No Kiosk code change; add note in plan that Kiosk uses same `appointments` table. |
| Kiosk + future booking | Add date/time selection step(s) in CheckIn.tsx using `getAvailableSlots` (and optionally `getAvailableDates`); create appointment at chosen slot. |

### 7.5 Summary checklist (overlooked items)

| Item | Action |
|------|--------|
| Jenkinsfile | No code change; document that IVR config is in DB via Admin IVR and that Supabase migration is run outside Jenkins if applicable. |
| Admin IVR – new settings | Shown in IVR Messages by default; optional: add Transfer & behaviour subsection and toggle for language prompt. |
| Admin IVR – Business Hours | Fix missing state and load: add `businessHours`, `editingDay`, `editHours` and call `fetchBusinessHours()` on load. |
| Appointments – date picker | Optional: add `getAvailableDates` and restrict/highlight dates when backend exposes available-dates. |
| API client | Add `getAvailableDates(serviceId, days?)` only if backend implements `GET /appointments/available-dates`. |
| Kiosk (CheckIn) | Not yet addressed. Either document as walk-in only (same `appointments` table) or add optional “Book a slot” path using `getAvailableSlots` / `getAvailableDates`. |

---

## 8. File references

- IVR webhook: `python-backend/routes/twilio/webhook.py`
- Scheduler/slots: `python-backend/utils_scheduler.py`, `python-backend/routes/appointments.py` (available-slots)
- DB seed: `python-backend/database.py` (seed_data, default_settings)
- Supabase migrations: `frontend/supabase/migrations/`
- Appointments page: `frontend/src/pages/Appointments.tsx`
- AppointmentCalendar: `frontend/src/components/AppointmentCalendar.tsx`
- Admin IVR: `frontend/src/pages/AdminIVR.tsx`
- Kiosk (CheckIn): `frontend/src/pages/CheckIn.tsx`
- API client: `frontend/src/lib/supabase.ts`
- Jenkinsfile: `Jenkinsfile` (root)
