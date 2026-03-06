/*
  # Fix services table RLS policies

  1. Changes
    - Drop all existing policies
    - Create new policies for all CRUD operations
    - Ensure RLS is enabled
    - Allow all authenticated users to perform all operations

  2. Security
    - Maintain RLS protection
    - Allow authenticated users full access
*/

-- First ensure RLS is enabled
ALTER TABLE services ENABLE ROW LEVEL SECURITY;

-- Drop all existing policies to start fresh
DROP POLICY IF EXISTS "Allow authenticated users to read services" ON services;
DROP POLICY IF EXISTS "Allow admin users to manage services" ON services;
DROP POLICY IF EXISTS "Enable all operations for authenticated users" ON services;
DROP POLICY IF EXISTS "Enable read for authenticated users" ON services;
DROP POLICY IF EXISTS "Enable insert for authenticated users" ON services;
DROP POLICY IF EXISTS "Enable update for authenticated users" ON services;
DROP POLICY IF EXISTS "Enable delete for authenticated users" ON services;

-- Create a single comprehensive policy for all operations
CREATE POLICY "Enable all operations for authenticated users"
  ON services
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);