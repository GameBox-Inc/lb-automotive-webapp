/*
  # Create customers table and update appointments

  1. New Tables
    - `customers`
      - `id` (uuid, primary key)
      - `name` (text)
      - `phone` (text)
      - `email` (text)
      - `address` (text)
      - `created_at` (timestamp)
      - `last_visit` (timestamp)

  2. Changes
    - Add customer_id to appointments table
    - Add foreign key constraint

  3. Security
    - Enable RLS on customers table
    - Add policies for authenticated users
*/

-- Create customers table
CREATE TABLE IF NOT EXISTS customers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  phone text NOT NULL,
  email text NOT NULL,
  address text,
  created_at timestamptz DEFAULT now(),
  last_visit timestamptz DEFAULT now()
);

-- Add customer_id to appointments
ALTER TABLE appointments
ADD COLUMN IF NOT EXISTS customer_id uuid REFERENCES customers(id);

-- Enable RLS
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;

-- Create policies
DROP POLICY IF EXISTS "Allow authenticated users to read customers" ON customers;
CREATE POLICY "Allow authenticated users to read customers"
  ON customers
  FOR SELECT
  TO authenticated
  USING (true);

DROP POLICY IF EXISTS "Allow authenticated users to insert customers" ON customers;
CREATE POLICY "Allow authenticated users to insert customers"
  ON customers
  FOR INSERT
  TO authenticated
  WITH CHECK (true);

DROP POLICY IF EXISTS "Allow authenticated users to update customers" ON customers;
CREATE POLICY "Allow authenticated users to update customers"
  ON customers
  FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);