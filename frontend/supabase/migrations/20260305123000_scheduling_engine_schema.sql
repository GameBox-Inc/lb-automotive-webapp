/*
  # Scheduling engine + vehicle fields for IVR, Kiosk, and web bookings

  This migration ensures the Supabase Postgres schema has the core tables
  and columns expected by the central scheduling engine and the new
  appointment/vehicle fields:

  - Availability: business_hours + staff_schedules + appointments + services
  - Vehicle metadata: vehicle_make/model/color/year on appointments

  It is idempotent and safe to run on existing databases.
*/

-- Core staff table (if it does not already exist)
CREATE TABLE IF NOT EXISTS staff (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  role text DEFAULT 'mechanic',
  active boolean DEFAULT true,
  created_at timestamptz DEFAULT now()
);

-- Business hours per weekday (0 = Monday, 6 = Sunday)
CREATE TABLE IF NOT EXISTS business_hours (
  day_of_week integer PRIMARY KEY,
  opening_time text,
  closing_time text,
  is_closed integer DEFAULT 0,
  updated_at timestamptz DEFAULT now(),
  updated_by text
);

-- Per‑staff weekly schedules used by the availability engine
CREATE TABLE IF NOT EXISTS staff_schedules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  staff_id uuid NOT NULL,
  day_of_week integer NOT NULL,
  start_time text NOT NULL,
  end_time text NOT NULL,
  is_off integer DEFAULT 0,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  CONSTRAINT fk_staff_schedules_staff FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE,
  CONSTRAINT uq_staff_day UNIQUE (staff_id, day_of_week)
);

-- Blackout windows (shop‑wide or technician‑specific) that block slots
CREATE TABLE IF NOT EXISTS blackouts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  reason text,
  start_time text NOT NULL,
  end_time text NOT NULL,
  scope text DEFAULT 'shop', -- 'shop' | 'technician'
  technician_id uuid,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Service duration in minutes used by the scheduling engine
ALTER TABLE services
  ADD COLUMN IF NOT EXISTS duration_minutes integer;

-- Scheduling and vehicle fields on appointments used by IVR/Kiosk/web
ALTER TABLE appointments
  ADD COLUMN IF NOT EXISTS service_id uuid,
  ADD COLUMN IF NOT EXISTS technician_id uuid,
  ADD COLUMN IF NOT EXISTS start_time timestamptz,
  ADD COLUMN IF NOT EXISTS end_time timestamptz,
  ADD COLUMN IF NOT EXISTS source text,
  ADD COLUMN IF NOT EXISTS vehicle_make text,
  ADD COLUMN IF NOT EXISTS vehicle_model text,
  ADD COLUMN IF NOT EXISTS vehicle_color text,
  ADD COLUMN IF NOT EXISTS vehicle_year integer;

