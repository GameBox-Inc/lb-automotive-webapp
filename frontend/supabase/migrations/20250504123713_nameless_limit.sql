/*
  # Add basic automotive services

  1. Changes
    - Add comprehensive list of automotive services
    - Organized by category (maintenance, repair, diagnostic)
    - Clear descriptions for each service
*/

-- Clear existing services to avoid duplicates
TRUNCATE services;

-- Insert basic services
INSERT INTO services (name, description, duration, price, category) VALUES
  -- Maintenance Services
  ('Oil Change Service', 'Complete oil change with synthetic oil and filter', 45, 89, 'maintenance'),
  ('Tire Service', 'Rotation, balancing, and pressure check', 30, 49, 'maintenance'),
  ('Filter Replacement', 'Air and cabin filter replacement', 30, 59, 'maintenance'),
  ('Fluid Service', 'Check and top off all fluids', 30, 45, 'maintenance'),
  ('Brake Maintenance', 'Brake inspection and adjustment', 45, 79, 'maintenance'),
  
  -- Repair Services
  ('Brake Repair', 'Brake system repair and pad replacement', 120, 299, 'repair'),
  ('Engine Repair', 'Engine diagnostic and repair service', 180, 399, 'repair'),
  ('Transmission Service', 'Transmission repair and fluid change', 240, 499, 'repair'),
  ('Suspension Repair', 'Suspension system repair and alignment', 120, 349, 'repair'),
  ('Electrical Repair', 'Electrical system troubleshooting and repair', 90, 249, 'repair'),
  
  -- Diagnostic Services
  ('Engine Diagnostic', 'Complete engine diagnostic scan', 60, 129, 'diagnostic'),
  ('Electrical Diagnostic', 'Electrical system testing', 60, 119, 'diagnostic'),
  ('AC System Check', 'Air conditioning system diagnosis', 45, 99, 'diagnostic'),
  ('Transmission Diagnostic', 'Transmission system evaluation', 60, 139, 'diagnostic'),
  ('Brake System Analysis', 'Comprehensive brake system testing', 45, 89, 'diagnostic');

-- Ensure available time slots exist
INSERT INTO available_slots (start_time, duration, is_available)
SELECT
  generate_series(
    date_trunc('hour', now()) + interval '1 day',
    date_trunc('hour', now()) + interval '5 days',
    interval '1 hour'
  ),
  60,
  true
WHERE
  -- Only during business hours (9 AM to 5 PM)
  extract(hour from generate_series) between 9 and 16
  -- Only weekdays
  AND extract(dow from generate_series) between 1 and 5
ON CONFLICT DO NOTHING;