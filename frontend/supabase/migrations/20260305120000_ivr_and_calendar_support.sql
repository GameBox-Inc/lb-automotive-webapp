/*
  # IVR and in-app calendar support (Premium IVR + dynamic booking)

  1. Ensures `settings` exists (for backends that use Supabase as DB).
  2. Inserts IVR and calendar-related settings used by:
     - Premium IVR: transfer number, language prompt, repair retries, recording disclaimer.
     - Single source of truth for availability: business_hours + staff_schedules + appointments
       (no new tables; calendar/IVR both use backend-computed slots).
*/

-- Ensure settings table exists (matches backend schema)
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  description TEXT,
  updated_at TIMESTAMPTZ DEFAULT now(),
  updated_by TEXT
);

-- Insert IVR and calendar-support settings (idempotent)
INSERT INTO settings (key, value, description)
VALUES
  ('ivr_transfer_number', '', 'E.164 number for representative transfer (Dial)'),
  ('ivr_language_prompt_enabled', 'false', 'Play language selection at start (true/false)'),
  ('ivr_repair_max_retries', '2', 'Max timeouts before offering transfer'),
  ('ivr_recording_disclaimer_en', 'This call may be recorded for quality purposes.', 'Recording disclaimer (English)'),
  ('ivr_recording_disclaimer_es', 'Esta llamada puede ser grabada para fines de calidad.', 'Recording disclaimer (Spanish)')
ON CONFLICT (key) DO NOTHING;
