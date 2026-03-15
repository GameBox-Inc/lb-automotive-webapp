/*
  # Fix services table RLS policies

  1. Changes
    - Drop existing RLS policies for services table
    - Create new policies allowing all authenticated users to manage services
    - Remove admin role requirement

  2. Security
    - Enable RLS on services table
    - Allow all authenticated users to perform CRUD operations
*/

-- Drop existing policies
DROP POLICY IF EXISTS "Allow authenticated users to read services" ON services;
DROP POLICY IF EXISTS "Allow admin users to manage services" ON services;
DROP POLICY IF EXISTS "Enable all operations for authenticated users" ON services;

-- Create new policies
DROP POLICY IF EXISTS "Enable read for authenticated users" ON services;
CREATE POLICY "Enable read for authenticated users"
  ON services
  FOR SELECT
  TO authenticated
  USING (true);

DROP POLICY IF EXISTS "Enable insert for authenticated users" ON services;
CREATE POLICY "Enable insert for authenticated users"
  ON services
  FOR INSERT
  TO authenticated
  WITH CHECK (true);

DROP POLICY IF EXISTS "Enable update for authenticated users" ON services;
CREATE POLICY "Enable update for authenticated users"
  ON services
  FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);

DROP POLICY IF EXISTS "Enable delete for authenticated users" ON services;
CREATE POLICY "Enable delete for authenticated users"
  ON services
  FOR DELETE
  TO authenticated
  USING (true);