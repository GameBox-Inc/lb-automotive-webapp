/*
  # Fix customers table RLS policies

  1. Changes
    - Drop existing RLS policies for customers table
    - Create new policies with proper insert permissions
    - Maintain existing table structure

  2. Security
    - Enable RLS
    - Allow authenticated users to perform all operations
*/

-- Drop existing policies
DROP POLICY IF EXISTS "Allow authenticated users to read customers" ON customers;
DROP POLICY IF EXISTS "Allow authenticated users to insert customers" ON customers;
DROP POLICY IF EXISTS "Allow authenticated users to update customers" ON customers;

-- Create new comprehensive policy
CREATE POLICY "Allow authenticated users to manage customers"
  ON customers
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);