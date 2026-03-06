/*
  # Add error logs table

  1. New Tables
    - `error_logs`
      - `id` (uuid, primary key)
      - `error_message` (text)
      - `error_stack` (text)
      - `context` (text)
      - `metadata` (jsonb)
      - `created_at` (timestamp)

  2. Security
    - Enable RLS on `error_logs` table
    - Add policy for authenticated users to insert logs
    - Add policy for admin users to read logs
*/

CREATE TABLE IF NOT EXISTS error_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  error_message text NOT NULL,
  error_stack text,
  context text,
  metadata jsonb,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE error_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users to insert error logs"
  ON error_logs
  FOR INSERT
  TO authenticated
  WITH CHECK (true);

CREATE POLICY "Allow admin users to read error logs"
  ON error_logs
  FOR SELECT
  TO authenticated
  USING (auth.jwt() ->> 'role' = 'admin');