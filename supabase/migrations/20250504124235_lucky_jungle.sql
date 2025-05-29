/*
  # Fix customers table RLS policies

  1. Changes
    - Drop all existing policies
    - Create new comprehensive policy for authenticated users
    
  2. Security
    - Maintain RLS enabled
    - Allow authenticated users full access
*/

-- Drop all existing policies
DROP POLICY IF EXISTS "Allow authenticated users to read customers" ON customers;
DROP POLICY IF EXISTS "Allow authenticated users to insert customers" ON customers;
DROP POLICY IF EXISTS "Allow authenticated users to update customers" ON customers;
DROP POLICY IF EXISTS "Allow authenticated users to manage customers" ON customers;

-- Create new comprehensive policy
CREATE POLICY "Allow authenticated users to manage customers"
  ON customers
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);