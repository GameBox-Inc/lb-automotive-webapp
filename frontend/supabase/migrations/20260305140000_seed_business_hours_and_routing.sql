/*
  # Seed business_hours and align table usage for IVR/Kiosk/scheduling

  1. Seeds business_hours so the scheduling engine has open days (otherwise
     the engine falls back to in-memory Mon–Fri only → weekend shows "fully booked").
  2. Backfills services.duration_minutes from duration where null (so availability works).
  3. Idempotent: safe to run on every deploy.
*/

-- Seed default business hours (Mon–Sun 08:00–18:00) so IVR and Kiosk show slots.
-- Only insert if no row exists for that day; do not overwrite existing config.
INSERT INTO business_hours (day_of_week, opening_time, closing_time, is_closed, updated_at)
VALUES
  (0, '08:00', '18:00', 0, now()),
  (1, '08:00', '18:00', 0, now()),
  (2, '08:00', '18:00', 0, now()),
  (3, '08:00', '18:00', 0, now()),
  (4, '08:00', '18:00', 0, now()),
  (5, '08:00', '18:00', 0, now()),
  (6, '08:00', '18:00', 0, now())
ON CONFLICT (day_of_week) DO NOTHING;

-- Ensure services.duration_minutes is set for the scheduling engine (uses it for slot length).
UPDATE services
SET duration_minutes = COALESCE(duration_minutes, duration)
WHERE duration_minutes IS NULL AND duration IS NOT NULL;
