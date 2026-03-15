/*
  # Add RLS policies for services table

  1. Security Changes
    - Add RLS policy to allow authenticated users to insert new services
    - Add RLS policy to allow authenticated users to read services
    - Add RLS policy to allow authenticated users to update services
    - Add RLS policy to allow authenticated users to delete services

  Note: These policies grant access to all authenticated users. In a production environment, 
  you might want to restrict these operations to specific user roles (e.g., admin users only).
*/

-- Enable RLS if not already enabled
ALTER TABLE services ENABLE ROW LEVEL SECURITY;

-- Create policies for all CRUD operations
DROP POLICY IF EXISTS "Allow authenticated users to insert services" ON services;
CREATE POLICY "Allow authenticated users to insert services"
ON services
FOR INSERT
TO authenticated
WITH CHECK (true);

DROP POLICY IF EXISTS "Allow authenticated users to read services" ON services;
CREATE POLICY "Allow authenticated users to read services"
ON services
FOR SELECT
TO authenticated
USING (true);

DROP POLICY IF EXISTS "Allow authenticated users to update services" ON services;
CREATE POLICY "Allow authenticated users to update services"
ON services
FOR UPDATE
TO authenticated
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Allow authenticated users to delete services" ON services;
CREATE POLICY "Allow authenticated users to delete services"
ON services
FOR DELETE
TO authenticated
USING (true);