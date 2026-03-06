/*
  # Create appointments table

  1. New Tables
    - `appointments`
      - `id` (uuid, primary key)
      - `customer_name` (text)
      - `phone_number` (text)
      - `appointment_time` (timestamptz)
      - `service_type` (text)
      - `notes` (text)
      - `created_at` (timestamptz)
      - `status` (text)

  2. Security
    - Enable RLS on `appointments` table
    - Add policy for authenticated users to read all appointments
    - Add policy for authenticated users to update appointments
*/

CREATE TABLE IF NOT EXISTS appointments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_name text NOT NULL,
  phone_number text NOT NULL,
  appointment_time timestamptz NOT NULL,
  service_type text NOT NULL,
  notes text,
  created_at timestamptz DEFAULT now(),
  status text DEFAULT 'scheduled'
);

ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users to read appointments"
  ON appointments
  FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Allow authenticated users to update appointments"
  ON appointments
  FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);