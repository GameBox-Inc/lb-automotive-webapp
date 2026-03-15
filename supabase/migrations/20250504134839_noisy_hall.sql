/*
  # Fix services table RLS policies

  1. Changes
    - Drop existing RLS policies
    - Create new policies allowing all authenticated users to manage services
    - Re-enable RLS with proper permissions

  2. Security
    - Allow authenticated users to perform all operations on services table
    - Maintain RLS protection while ensuring proper access
*/

-- Temporarily disable RLS
ALTER TABLE services DISABLE ROW LEVEL SECURITY;

-- Drop existing policies
DROP POLICY IF EXISTS "Allow authenticated users to read services" ON services;
DROP POLICY IF EXISTS "Allow admin users to manage services" ON services;
DROP POLICY IF EXISTS "Allow authenticated users to manage services" ON services;
DROP POLICY IF EXISTS "Enable all operations for authenticated users" ON services;
DROP POLICY IF EXISTS "Enable read for authenticated users" ON services;
DROP POLICY IF EXISTS "Enable insert for authenticated users" ON services;
DROP POLICY IF EXISTS "Enable update for authenticated users" ON services;
DROP POLICY IF EXISTS "Enable delete for authenticated users" ON services;

-- Create new comprehensive policy
CREATE POLICY "Enable all operations for authenticated users"
  ON services
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Re-enable RLS
ALTER TABLE services ENABLE ROW LEVEL SECURITY;