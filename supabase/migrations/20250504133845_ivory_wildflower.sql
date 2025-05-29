/*
  # Update services table RLS policies

  1. Changes
    - Drop existing restrictive policies
    - Add new policies allowing authenticated users to manage services
    
  2. Security
    - Enable RLS on services table
    - Allow authenticated users to perform all operations
*/

-- Drop existing policies
DROP POLICY IF EXISTS "Allow authenticated users to read services" ON services;
DROP POLICY IF EXISTS "Allow admin users to manage services" ON services;

-- Create new policies
CREATE POLICY "Allow authenticated users to manage services"
  ON services
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Ensure RLS is enabled
ALTER TABLE services ENABLE ROW LEVEL SECURITY;