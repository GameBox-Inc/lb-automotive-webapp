/*
  # Fix call_states RLS policies

  1. Changes
    - Drop existing policies on call_states table
    - Create new comprehensive policy for authenticated users
    - Ensure RLS is properly enabled

  2. Security
    - Allow authenticated users to manage call states
    - Enable all CRUD operations for authenticated users
*/

-- First ensure RLS is enabled
ALTER TABLE call_states ENABLE ROW LEVEL SECURITY;

-- Drop any existing policies
DROP POLICY IF EXISTS "Allow authenticated users to manage call states" ON call_states;

-- Create new comprehensive policy
CREATE POLICY "Allow authenticated users to manage call states"
  ON call_states
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Create index for better query performance
CREATE INDEX IF NOT EXISTS idx_call_states_call_sid ON call_states(call_sid);

-- Analyze the table to update statistics
ANALYZE call_states;