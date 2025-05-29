/*
  # Add basic services and available time slots

  1. Services
    - Add basic automotive services in different categories
    - Set realistic durations and prices
    
  2. Available Slots
    - Add available time slots for the next 5 business days
    - Set standard duration of 60 minutes
*/

-- Insert basic services
INSERT INTO services (name, description, duration, price, category) VALUES
  -- Maintenance Services
  ('Oil Change', 'Full synthetic oil change with filter replacement', 45, 89, 'maintenance'),
  ('Tire Rotation', 'Complete tire rotation and balancing', 30, 49, 'maintenance'),
  ('Brake Inspection', 'Comprehensive brake system inspection', 45, 69, 'maintenance'),
  
  -- Repair Services
  ('Brake Pad Replacement', 'Front or rear brake pad replacement', 120, 249, 'repair'),
  ('Alternator Replacement', 'Alternator diagnosis and replacement', 180, 399, 'repair'),
  ('Starter Replacement', 'Starter motor replacement', 120, 349, 'repair'),
  
  -- Diagnostic Services
  ('Check Engine Light', 'Complete diagnostic scan and inspection', 60, 129, 'diagnostic'),
  ('AC System Check', 'Air conditioning system diagnosis', 45, 99, 'diagnostic'),
  ('Electrical System', 'Electrical system diagnostic', 60, 119, 'diagnostic')
ON CONFLICT (id) DO NOTHING;

-- Insert available time slots for the next 5 business days
WITH RECURSIVE dates AS (
  SELECT current_date AS date
  UNION ALL
  SELECT date + 1
  FROM dates
  WHERE date < current_date + 5
),
times AS (
  SELECT '09:00'::time AS start_time
  UNION ALL
  SELECT (start_time + interval '1 hour')::time
  FROM times
  WHERE start_time < '17:00'::time
)
INSERT INTO available_slots (start_time, duration, is_available)
SELECT
  (d.date + t.start_time)::timestamptz,
  60,
  true
FROM dates d
CROSS JOIN times t
WHERE EXTRACT(DOW FROM d.date) BETWEEN 1 AND 5  -- Monday to Friday
ON CONFLICT DO NOTHING;