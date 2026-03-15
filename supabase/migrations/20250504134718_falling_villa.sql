/*
  # Fix services table RLS policies

  1. Changes
    - Drop existing restrictive policies
    - Create new policy allowing authenticated users to manage services
    - Re-enable RLS to ensure security

  2. Security
    - Allow authenticated users to perform all operations on services
    - Maintain RLS protection for unauthenticated access
*/

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Allow authenticated users to read services" ON services;
DROP POLICY IF EXISTS "Allow admin users to manage services" ON services;
DROP POLICY IF EXISTS "Allow authenticated users to manage services" ON services;

-- Create new unified policy for authenticated users
CREATE POLICY "Allow authenticated users to manage services"
  ON services
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Ensure RLS is enabled
ALTER TABLE services ENABLE ROW LEVEL SECURITY;