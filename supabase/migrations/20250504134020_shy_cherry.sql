/*
  # Fix services table RLS policies

  1. Changes
    - Drop existing restrictive policies
    - Add new policies to allow authenticated users to manage services
    - Ensure RLS is enabled
    
  2. Security
    - Allow authenticated users to perform all operations on services
*/

-- Drop existing policies
DROP POLICY IF EXISTS "Allow authenticated users to read services" ON services;
DROP POLICY IF EXISTS "Allow authenticated users to insert services" ON services;
DROP POLICY IF EXISTS "Allow authenticated users to update services" ON services;
DROP POLICY IF EXISTS "Allow authenticated users to delete services" ON services;
DROP POLICY IF EXISTS "Allow admin users to manage services" ON services;
DROP POLICY IF EXISTS "Allow authenticated users to manage services" ON services;

-- Create new policies for all operations
DROP POLICY IF EXISTS "Allow authenticated users to read services" ON services;
CREATE POLICY "Allow authenticated users to read services"
  ON services
  FOR SELECT
  TO authenticated
  USING (true);

DROP POLICY IF EXISTS "Allow authenticated users to insert services" ON services;
CREATE POLICY "Allow authenticated users to insert services"
  ON services
  FOR INSERT
  TO authenticated
  WITH CHECK (true);

DROP POLICY IF EXISTS "Allow authenticated users to update services" ON services;
CREATE POLICY "Allow authenticated users to update services"
  ON services
  FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);

DROP POLICY IF EXISTS "Allow authenticated users to delete services" ON services;
CREATE POLICY "Allow authenticated users to delete services"
  ON services
  FOR DELETE
  TO authenticated
  USING (true);

-- Ensure RLS is enabled
ALTER TABLE services ENABLE ROW LEVEL SECURITY;