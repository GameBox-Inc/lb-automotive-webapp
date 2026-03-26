/*
  Seed `services` catalog if empty.

  Problem:
  - The production Supabase DB currently has `public.services = 0` rows.
  - This makes the Admin Services tab and all service-dependent flows render empty.

  Approach:
  - Only seed when the table is empty, so we don't clobber admin changes.
  - Use the same baseline services list previously used by seed migrations.
*/

-- Ensure RLS is enabled (policies are handled by other migrations).
ALTER TABLE services ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF (SELECT COUNT(1) FROM public.services) = 0 THEN
    INSERT INTO public.services (id, name, description, duration, price, category, is_emergency)
    VALUES
      -- Maintenance Services
      (gen_random_uuid(), 'Oil Change', 'Full synthetic oil change with filter replacement', 45, 89, 'maintenance', 0),
      (gen_random_uuid(), 'Tire Service', 'Complete tire rotation and balancing', 30, 49, 'maintenance', 0),
      (gen_random_uuid(), 'Brake Maintenance', 'Comprehensive brake system inspection', 45, 69, 'maintenance', 0),
      (gen_random_uuid(), 'Vehicle Inspection', 'Complete multi-point inspection', 60, 79, 'maintenance', 0),

      -- Repair Services
      (gen_random_uuid(), 'Brake Repair', 'Complete brake system repair', 120, 299, 'repair', 0),
      (gen_random_uuid(), 'Engine Repair', 'Engine diagnostic and repair', 180, 399, 'repair', 0),
      (gen_random_uuid(), 'Transmission Service', 'Transmission repair and fluid change', 240, 499, 'repair', 0),
      (gen_random_uuid(), 'AC Repair', 'Air conditioning system repair', 120, 299, 'repair', 0),

      -- Diagnostic Services
      (gen_random_uuid(), 'Engine Diagnostic', 'Complete engine diagnostic scan', 60, 129, 'diagnostic', 0),
      (gen_random_uuid(), 'Electrical System Check', 'Full electrical system diagnostic', 60, 119, 'diagnostic', 0),
      (gen_random_uuid(), 'AC System Check', 'Air conditioning system testing', 45, 99, 'diagnostic', 0),

      -- Emergency Services
      (gen_random_uuid(), 'Emergency Towing', '24/7 emergency towing service', 60, 150, 'emergency', 1),
      (gen_random_uuid(), 'Roadside Assistance', 'Emergency roadside service', 45, 95, 'emergency', 1),
      (gen_random_uuid(), 'Emergency Repair', 'Urgent repair service', 120, 350, 'emergency', 1);

    -- Basic indexes (safe if they already exist).
    CREATE INDEX IF NOT EXISTS idx_services_category ON public.services(category);
    CREATE INDEX IF NOT EXISTS idx_services_is_emergency ON public.services(is_emergency);
    CREATE INDEX IF NOT EXISTS idx_services_name ON public.services(name);
  END IF;
END
$$;

ANALYZE public.services;

