/*
  # Add service categories and sample services

  This migration adds predefined service categories and sample services to the database.

  1. Changes
    - Adds sample services with categories
    - Sets up initial service offerings
    
  2. Categories
    - Maintenance
    - Repair
    - Diagnostic
    - Emergency
*/

-- Insert sample services if they don't exist
INSERT INTO services (name, description, duration, price, category, is_emergency) VALUES
  ('Oil Change', 'Full synthetic oil change service including filter replacement and fluid top-off', 45, 75, 'maintenance', false),
  ('Tire Rotation', 'Complete tire rotation and balancing service', 30, 60, 'maintenance', false),
  ('Brake Service', 'Comprehensive brake inspection and pad replacement', 90, 180, 'repair', false),
  ('Engine Diagnostic', 'Complete engine diagnostic scan with detailed report', 60, 120, 'diagnostic', false),
  ('Battery Service', 'Battery testing, cleaning, and replacement if needed', 30, 85, 'maintenance', false),
  ('AC Service', 'Air conditioning system diagnosis and recharge', 90, 160, 'repair', false),
  ('Transmission Service', 'Automatic transmission fluid change and system inspection', 120, 220, 'maintenance', false),
  ('Check Engine Light', 'Diagnostic scan and basic troubleshooting', 45, 90, 'diagnostic', false),
  ('Emergency Towing', '24/7 emergency towing service within city limits', 60, 150, 'emergency', true),
  ('Roadside Assistance', 'Emergency roadside service including jump starts and tire changes', 45, 95, 'emergency', true),
  ('Suspension Repair', 'Suspension system inspection and repair', 120, 250, 'repair', false),
  ('Electrical System', 'Electrical system diagnosis and repair', 90, 180, 'repair', false)
ON CONFLICT (id) DO NOTHING;