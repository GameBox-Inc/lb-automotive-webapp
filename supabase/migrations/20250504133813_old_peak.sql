/*
  # Update services table RLS policies

  1. Changes
    - Drop existing restrictive RLS policy
    - Add new policy allowing authenticated users to manage services
    
  2. Security
    - Maintain read access for all authenticated users
    - Allow all authenticated users to manage services
*/

-- Drop the existing admin-only policy
DROP POLICY IF EXISTS "Allow admin users to manage services" ON services;

-- Create new policy allowing all authenticated users to manage services
CREATE POLICY "Allow authenticated users to manage services"
  ON services
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);