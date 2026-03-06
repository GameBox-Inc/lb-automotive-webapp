/*
  # Create services table

  1. New Tables
    - `services`
      - `id` (uuid, primary key)
      - `name` (text)
      - `description` (text)
      - `duration` (integer, minutes)
      - `price` (integer, cents)
      - `is_emergency` (boolean)
      - `created_at` (timestamp with time zone)

  2. Security
    - Enable RLS on `services` table
    - Add policies for:
      - Authenticated users can read services
      - Only admin users can create/update/delete services
*/

CREATE TABLE IF NOT EXISTS services (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  description text NOT NULL,
  duration integer NOT NULL,
  price integer NOT NULL,
  is_emergency boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE services ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Allow authenticated users to read services"
  ON services
  FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Allow admin users to manage services"
  ON services
  FOR ALL
  TO authenticated
  USING (auth.jwt() ->> 'role' = 'admin')
  WITH CHECK (auth.jwt() ->> 'role' = 'admin');