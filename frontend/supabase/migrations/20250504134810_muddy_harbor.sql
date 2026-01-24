-- First, disable RLS temporarily to ensure we can modify policies
ALTER TABLE services DISABLE ROW LEVEL SECURITY;

-- Drop all existing policies
DROP POLICY IF EXISTS "Allow authenticated users to read services" ON services;
DROP POLICY IF EXISTS "Allow authenticated users to insert services" ON services;
DROP POLICY IF EXISTS "Allow authenticated users to update services" ON services;
DROP POLICY IF EXISTS "Allow authenticated users to delete services" ON services;
DROP POLICY IF EXISTS "Allow admin users to manage services" ON services;
DROP POLICY IF EXISTS "Allow authenticated users to manage services" ON services;

-- Create a single policy for all operations
CREATE POLICY "Enable all operations for authenticated users"
  ON services
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Re-enable RLS
ALTER TABLE services ENABLE ROW LEVEL SECURITY;