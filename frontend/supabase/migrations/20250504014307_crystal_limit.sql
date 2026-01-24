/*
  # Add service categories and sample services

  1. New Data
    - Add service categories for better organization
    - Insert sample services for testing
  
  2. Changes
    - Add category field to services table
    - Add sample automotive services
*/

ALTER TABLE services ADD COLUMN IF NOT EXISTS category text DEFAULT 'general';

-- Insert sample services
INSERT INTO services (name, description, duration, price, category, is_emergency) VALUES
  ('Oil Change', 'Full synthetic oil change service', 30, 75, 'maintenance', false),
  ('Brake Service', 'Brake pad replacement and inspection', 60, 150, 'repair', false),
  ('Tire Rotation', 'Tire rotation and balance', 45, 60, 'maintenance', false),
  ('Engine Diagnostic', 'Complete engine diagnostic scan', 60, 120, 'diagnostic', false),
  ('Emergency Repair', 'Emergency automotive repair service', 120, 250, 'emergency', true),
  ('AC Service', 'Air conditioning system service', 90, 180, 'repair', false),
  ('Battery Service', 'Battery testing and replacement', 30, 85, 'maintenance', false),
  ('Transmission Service', 'Transmission fluid change', 90, 200, 'maintenance', false)
ON CONFLICT (id) DO NOTHING;