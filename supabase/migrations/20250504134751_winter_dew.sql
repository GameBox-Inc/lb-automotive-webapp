/*
  # Fix services table RLS policies

  1. Changes
    - Drop existing restrictive policies
    - Create new policy allowing authenticated users to manage services
    - Ensure RLS remains enabled for security

  2. Security
    - Maintain RLS protection
    - Grant full access to authenticated users
*/

DO $$ 
BEGIN
  -- Safely drop existing policies if they exist
  IF EXISTS (
    SELECT 1 
    FROM pg_policies 
    WHERE schemaname = 'public' 
    AND tablename = 'services' 
    AND policyname = 'Allow authenticated users to read services'
  ) THEN
    DROP POLICY "Allow authenticated users to read services" ON services;
  END IF;

  IF EXISTS (
    SELECT 1 
    FROM pg_policies 
    WHERE schemaname = 'public' 
    AND tablename = 'services' 
    AND policyname = 'Allow admin users to manage services'
  ) THEN
    DROP POLICY "Allow admin users to manage services" ON services;
  END IF;

  IF EXISTS (
    SELECT 1 
    FROM pg_policies 
    WHERE schemaname = 'public' 
    AND tablename = 'services' 
    AND policyname = 'Allow authenticated users to manage services'
  ) THEN
    DROP POLICY "Allow authenticated users to manage services" ON services;
  END IF;
END $$;

-- Create new unified policy for authenticated users
CREATE POLICY "Allow authenticated users to manage services"
  ON services
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Ensure RLS is enabled
ALTER TABLE services ENABLE ROW LEVEL SECURITY;