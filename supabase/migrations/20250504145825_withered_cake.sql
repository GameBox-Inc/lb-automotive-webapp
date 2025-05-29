-- First, clear existing services to avoid duplicates
TRUNCATE services;

-- Insert services with proper categories
INSERT INTO services (name, description, duration, price, category, is_emergency) VALUES
  -- Maintenance Services
  ('Oil Change', 'Full synthetic oil change with filter replacement', 45, 89, 'maintenance', false),
  ('Tire Rotation', 'Complete tire rotation and balancing', 30, 49, 'maintenance', false),
  ('Brake Inspection', 'Comprehensive brake system inspection', 45, 69, 'maintenance', false),
  ('Multi-Point Inspection', 'Complete vehicle inspection', 60, 79, 'maintenance', false),
  
  -- Repair Services
  ('Brake Repair', 'Complete brake system repair', 120, 299, 'repair', false),
  ('Engine Repair', 'Engine diagnostic and repair', 180, 399, 'repair', false),
  ('Transmission Service', 'Transmission repair and fluid change', 240, 499, 'repair', false),
  ('AC Repair', 'Air conditioning system repair', 120, 299, 'repair', false),
  
  -- Diagnostic Services
  ('Engine Diagnostic', 'Complete engine diagnostic scan', 60, 129, 'diagnostic', false),
  ('Electrical System Check', 'Full electrical system diagnostic', 60, 119, 'diagnostic', false),
  ('AC System Diagnostic', 'Air conditioning system testing', 45, 99, 'diagnostic', false),
  
  -- Emergency Services
  ('Emergency Towing', '24/7 emergency towing service', 60, 150, 'emergency', true),
  ('Roadside Assistance', 'Emergency roadside service', 45, 95, 'emergency', true),
  ('Emergency Repair', 'Urgent repair service', 120, 350, 'emergency', true);

-- Ensure RLS is enabled
ALTER TABLE services ENABLE ROW LEVEL SECURITY;

-- Create unified policy for authenticated users
DROP POLICY IF EXISTS "Enable all operations for authenticated users" ON services;
CREATE POLICY "Enable all operations for authenticated users"
  ON services
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);