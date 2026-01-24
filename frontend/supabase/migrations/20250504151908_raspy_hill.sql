-- Add metadata column to call_states table
ALTER TABLE call_states 
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Create index on metadata column
CREATE INDEX IF NOT EXISTS idx_call_states_metadata ON call_states USING GIN (metadata);

-- Add comment explaining the metadata structure
COMMENT ON COLUMN call_states.metadata IS 'Stores IVR flow data including:
- categories: Array of available service categories
- selectedCategory: Currently selected category
- services: Array of available services for selected category
- selectedService: Currently selected service
- slots: Array of available time slots
- selectedSlot: Currently selected time slot';