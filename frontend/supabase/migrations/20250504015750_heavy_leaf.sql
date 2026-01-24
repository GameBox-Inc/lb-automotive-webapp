/*
  # Add available slots management

  1. New Tables
    - `available_slots`
      - `id` (uuid, primary key)
      - `start_time` (timestamptz)
      - `duration` (integer)
      - `is_available` (boolean)
      - `created_at` (timestamptz)
  
  2. Security
    - Enable RLS on `available_slots` table
    - Add policy for authenticated users to read slots
    - Add policy for admin users to manage slots

  3. Functions
    - `generate_available_slots()`: Creates appointment slots for next 7 days
*/

-- Create available slots table
CREATE TABLE IF NOT EXISTS available_slots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  start_time timestamptz NOT NULL,
  duration integer NOT NULL,
  is_available boolean DEFAULT true,
  created_at timestamptz DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE available_slots ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Allow authenticated users to read available slots"
  ON available_slots
  FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Allow admin users to manage available slots"
  ON available_slots
  FOR ALL
  TO authenticated
  USING (auth.jwt() ->> 'role' = 'admin')
  WITH CHECK (auth.jwt() ->> 'role' = 'admin');

-- Function to generate available slots for the next 7 days
CREATE OR REPLACE FUNCTION generate_available_slots()
RETURNS void AS $$
DECLARE
  v_current_date date;
  v_slot_date timestamp;
BEGIN
  v_current_date := CURRENT_DATE;
  
  FOR d IN 0..6 LOOP
    -- Morning slots (9 AM to 12 PM)
    v_slot_date := v_current_date + (d || ' days')::interval + '09:00:00'::interval;
    
    WHILE v_slot_date::time < '12:00:00'::time LOOP
      INSERT INTO available_slots (start_time, duration)
      VALUES (v_slot_date, 60)
      ON CONFLICT DO NOTHING;
      
      v_slot_date := v_slot_date + '30 minutes'::interval;
    END LOOP;
    
    -- Afternoon slots (1 PM to 5 PM)
    v_slot_date := v_current_date + (d || ' days')::interval + '13:00:00'::interval;
    WHILE v_slot_date::time < '17:00:00'::time LOOP
      INSERT INTO available_slots (start_time, duration)
      VALUES (v_slot_date, 60)
      ON CONFLICT DO NOTHING;
      
      v_slot_date := v_slot_date + '30 minutes'::interval;
    END LOOP;
  END LOOP;
END;
$$ LANGUAGE plpgsql;