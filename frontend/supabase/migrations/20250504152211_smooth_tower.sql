/*
  # Add metadata column to call_states table

  1. Changes
    - Add JSONB metadata column to store service selection state
    - Create GIN index for efficient querying
    - Add detailed column comment

  2. Purpose
    - Store service selection flow data
    - Track selected category and service
    - Maintain available options for each step
*/

-- Add metadata column to call_states table
ALTER TABLE call_states 
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Create index on metadata column for efficient querying
CREATE INDEX IF NOT EXISTS idx_call_states_metadata ON call_states USING GIN (metadata);

-- Add comment explaining the metadata structure
COMMENT ON COLUMN call_states.metadata IS 'Stores IVR flow data including:
- categories: Array of available service categories
- selectedCategory: Currently selected category
- services: Array of available services for selected category
- selectedService: Currently selected service
- slots: Array of available time slots
- selectedSlot: Currently selected time slot
- price: Selected service price
- duration: Selected service duration
- description: Selected service description';