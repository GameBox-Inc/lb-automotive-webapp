/*
  # Add call states tracking

  1. New Tables
    - `call_states` - Tracks IVR conversation state
      - `call_sid` (text, primary key) - Twilio Call SID
      - `current_step` (text) - Current conversation step
      - `language` (text) - Selected language
      - `appointment_id` (uuid) - Related appointment ID
      - `created_at` (timestamptz) - Record creation time
      - `updated_at` (timestamptz) - Last update time

  2. New Tables
    - `ivr_logs` - Logs all IVR interactions
      - `id` (uuid, primary key)
      - `call_sid` (text) - Twilio Call SID
      - `step` (text) - Conversation step
      - `input` (text) - User input (DTMF or speech)
      - `created_at` (timestamptz) - Log entry time

  3. Security
    - Enable RLS on both tables
    - Allow authenticated users to manage call states
    - Allow authenticated users to create log entries
*/

-- Create call_states table
CREATE TABLE IF NOT EXISTS call_states (
  call_sid TEXT PRIMARY KEY,
  current_step TEXT NOT NULL DEFAULT 'welcome',
  language TEXT DEFAULT 'en',
  appointment_id UUID REFERENCES appointments(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Create ivr_logs table
CREATE TABLE IF NOT EXISTS ivr_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  call_sid TEXT NOT NULL,
  step TEXT NOT NULL,
  input TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Enable RLS
ALTER TABLE call_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE ivr_logs ENABLE ROW LEVEL SECURITY;

-- Create policies for call_states
DROP POLICY IF EXISTS "Allow authenticated users to manage call states" ON call_states;
CREATE POLICY "Allow authenticated users to manage call states"
  ON call_states
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Create policies for ivr_logs
DROP POLICY IF EXISTS "Allow authenticated users to insert ivr logs" ON ivr_logs;
CREATE POLICY "Allow authenticated users to insert ivr logs"
  ON ivr_logs
  FOR INSERT
  TO authenticated
  WITH CHECK (true);

DROP POLICY IF EXISTS "Allow authenticated users to read ivr logs" ON ivr_logs;
CREATE POLICY "Allow authenticated users to read ivr logs"
  ON ivr_logs
  FOR SELECT
  TO authenticated
  USING (true);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for call_states
CREATE TRIGGER update_call_states_updated_at
  BEFORE UPDATE ON call_states
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();