/*
  # Update services table RLS policies

  1. Changes
    - Drop existing restrictive policies
    - Create new policy for authenticated users to manage services
    - Ensure RLS remains enabled

  2. Security
    - Maintain RLS on services table
    - Allow authenticated users full access to services
*/

DO $$ 
BEGIN
  -- Drop existing policies if they exist
  IF EXISTS (
    SELECT 1 
    FROM pg_policies 
    WHERE tablename = 'services' 
    AND policyname = 'Allow authenticated users to read services'
  ) THEN
    DROP POLICY "Allow authenticated users to read services" ON services;
  END IF;

  IF EXISTS (
    SELECT 1 
    FROM pg_policies 
    WHERE tablename = 'services' 
    AND policyname = 'Allow admin users to manage services'
  ) THEN
    DROP POLICY "Allow admin users to manage services" ON services;
  END IF;

  -- Create new policy if it doesn't exist
  IF NOT EXISTS (
    SELECT 1 
    FROM pg_policies 
    WHERE tablename = 'services' 
    AND policyname = 'Allow authenticated users to manage services'
  ) THEN
    CREATE POLICY "Allow authenticated users to manage services"
      ON services
      FOR ALL
      TO authenticated
      USING (true)
      WITH CHECK (true);
  END IF;
END $$;

-- Ensure RLS is enabled
ALTER TABLE services ENABLE ROW LEVEL SECURITY;