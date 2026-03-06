/*
  # Optimize call_states table and indexes

  1. Changes
    - Add indexes for better query performance
    - Update table statistics
    - Add timeout handling
    
  2. Security
    - Maintain existing RLS policies
*/

-- Create additional indexes for better performance
CREATE INDEX IF NOT EXISTS idx_call_states_updated_at ON call_states(updated_at);
CREATE INDEX IF NOT EXISTS idx_call_states_current_step ON call_states(current_step);
CREATE INDEX IF NOT EXISTS idx_call_states_language ON call_states(language);

-- Update table statistics
ANALYZE call_states;

-- Add timeout column
ALTER TABLE call_states
ADD COLUMN IF NOT EXISTS last_response_time interval;

