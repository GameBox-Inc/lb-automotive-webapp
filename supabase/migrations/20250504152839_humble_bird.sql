/*
  # Fix services data and ensure proper querying

  1. Changes
    - Clear and repopulate services table with correct data
    - Add indexes for better query performance
    - Ensure RLS policies are correct
*/

-- First, clear existing services to avoid duplicates
TRUNCATE services;

-- Insert services with proper categories and ensure is_emergency is set correctly
INSERT INTO services (name, description, duration, price, category, is_emergency) VALUES
  -- Maintenance Services
  ('Oil Change', 'Full synthetic oil change with filter replacement', 45, 89, 'maintenance', false),
  ('Tire Service', 'Complete tire rotation and balancing', 30, 49, 'maintenance', false),
  ('Brake Maintenance', 'Comprehensive brake system inspection', 45, 69, 'maintenance', false),
  ('Vehicle Inspection', 'Complete multi-point inspection', 60, 79, 'maintenance', false),
  
  -- Repair Services
  ('Brake Repair', 'Complete brake system repair', 120, 299, 'repair', false),
  ('Engine Repair', 'Engine diagnostic and repair', 180, 399, 'repair', false),
  ('Transmission Service', 'Transmission repair and fluid change', 240, 499, 'repair', false),
  ('AC Repair', 'Air conditioning system repair', 120, 299, 'repair', false),
  
  -- Diagnostic Services
  ('Engine Diagnostic', 'Complete engine diagnostic scan', 60, 129, 'diagnostic', false),
  ('Electrical System Check', 'Full electrical system diagnostic', 60, 119, 'diagnostic', false),
  ('AC System Check', 'Air conditioning system testing', 45, 99, 'diagnostic', false),
  
  -- Emergency Services
  ('Emergency Towing', '24/7 emergency towing service', 60, 150, 'emergency', true),
  ('Roadside Assistance', 'Emergency roadside service', 45, 95, 'emergency', true),
  ('Emergency Repair', 'Urgent repair service', 120, 350, 'emergency', true);

-- Ensure RLS is enabled
ALTER TABLE services ENABLE ROW LEVEL SECURITY;

-- Drop existing policies
DROP POLICY IF EXISTS "Enable all operations for authenticated users" ON services;

-- Create new policy for all operations
CREATE POLICY "Enable all operations for authenticated users"
  ON services
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_services_category ON services(category);
CREATE INDEX IF NOT EXISTS idx_services_is_emergency ON services(is_emergency);
CREATE INDEX IF NOT EXISTS idx_services_name ON services(name);

-- Analyze the table to update statistics
ANALYZE services;