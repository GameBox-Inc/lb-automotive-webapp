/*
  # Fix customers table RLS policies

  1. Changes
    - Drop existing RLS policies
    - Create new comprehensive policy for authenticated users
    - Enable proper access for all CRUD operations

  2. Security
    - Maintain authentication requirement
    - Allow authenticated users full access to customers table
*/

-- Drop existing policies
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