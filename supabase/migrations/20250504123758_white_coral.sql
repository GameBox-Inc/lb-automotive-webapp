/*
  # Add basic services and time slots

  1. Services
    - Add maintenance services
    - Add repair services
    - Add diagnostic services

  2. Time Slots
    - Generate available slots for next 5 days
    - Business hours: 9 AM to 5 PM
    - Weekdays only
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

-- Function to generate time slots
DO $$
DECLARE
  slot_time timestamptz;
  v_date date := CURRENT_DATE + interval '1 day';
  v_end_date date := CURRENT_DATE + interval '5 days';
BEGIN
  -- Loop through dates
  WHILE v_date <= v_end_date LOOP
    -- Loop through hours (9 AM to 5 PM)
    FOR hour IN 9..16 LOOP
      -- Skip weekends
      IF EXTRACT(DOW FROM v_date) NOT IN (0, 6) THEN
        slot_time := v_date + (hour || ' hours')::interval;
        
        -- Insert hourly slots
        INSERT INTO available_slots (start_time, duration, is_available)
        VALUES (slot_time, 60, true)
        ON CONFLICT DO NOTHING;
      END IF;
    END LOOP;
    v_date := v_date + interval '1 day';
  END LOOP;
END $$;