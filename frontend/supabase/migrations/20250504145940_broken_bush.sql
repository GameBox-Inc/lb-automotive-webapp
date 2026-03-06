-- First, clear existing services to avoid duplicates
TRUNCATE services;

-- Insert services with proper categories and ensure is_emergency is set correctly
INSERT INTO services (name, description, duration, price, category, is_emergency) VALUES
  -- Maintenance Services
  ('Oil Change', 'Full synthetic oil change with filter replacement and multi-point inspection', 45, 89, 'maintenance', false),
  ('Tire Service', 'Complete tire rotation, balancing, and pressure check', 30, 49, 'maintenance', false),
  ('Brake Maintenance', 'Comprehensive brake system inspection and maintenance', 45, 69, 'maintenance', false),
  ('Vehicle Inspection', 'Complete multi-point vehicle inspection', 60, 79, 'maintenance', false),
  
  -- Repair Services
  ('Brake System Repair', 'Complete brake system repair including pads and rotors', 120, 299, 'repair', false),
  ('Engine Repair', 'Engine diagnostic and repair service', 180, 399, 'repair', false),
  ('Transmission Service', 'Transmission repair and fluid change', 240, 499, 'repair', false),
  ('AC System Repair', 'Air conditioning system repair and recharge', 120, 299, 'repair', false),
  
  -- Diagnostic Services
  ('Engine Diagnostic', 'Complete engine diagnostic scan with detailed report', 60, 129, 'diagnostic', false),
  ('Electrical Diagnostic', 'Full electrical system diagnostic testing', 60, 119, 'diagnostic', false),
  ('AC System Check', 'Air conditioning system performance testing', 45, 99, 'diagnostic', false),
  
  -- Emergency Services
  ('Emergency Towing', '24/7 emergency towing service within city limits', 60, 150, 'emergency', true),
  ('Roadside Assistance', 'Emergency roadside service including jump starts and tire changes', 45, 95, 'emergency', true),
  ('Emergency Repair', 'Priority emergency repair service', 120, 350, 'emergency', true);

-- Ensure RLS is enabled and policy is correct
ALTER TABLE services ENABLE ROW LEVEL SECURITY;

-- Recreate the policy to ensure proper access
DROP POLICY IF EXISTS "Enable all operations for authenticated users" ON services;
CREATE POLICY "Enable all operations for authenticated users"
  ON services
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Create indexes to improve query performance
CREATE INDEX IF NOT EXISTS idx_services_category ON services(category);
CREATE INDEX IF NOT EXISTS idx_services_is_emergency ON services(is_emergency);