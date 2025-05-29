/*
  # Enhance call_states metadata for service booking

  1. Changes
    - Add metadata column to store service and booking information
    - Create GIN index for efficient JSON querying
    - Add detailed column documentation

  2. Structure
    The metadata column stores:
    - Service selection state
    - Available time slots
    - Customer preferences
    - Booking progress
*/

-- Add metadata column if it doesn't exist
ALTER TABLE call_states 
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Create GIN index for efficient JSON querying
CREATE INDEX IF NOT EXISTS idx_call_states_metadata ON call_states USING GIN (metadata);

-- Add detailed documentation about the metadata structure
COMMENT ON COLUMN call_states.metadata IS 'Stores IVR flow data including:
- categories: Array of available service categories
- selectedCategory: Currently selected category
- services: Array of available services for selected category
- selectedService: Currently selected service details (name, price, duration, description)
- slots: Array of available time slots
- selectedSlot: Currently selected time slot
- customerInfo: Customer details gathered during the call
- bookingProgress: Track completed steps in the booking process';

-- Drop existing trigger if it exists
DROP TRIGGER IF EXISTS update_call_states_metadata_updated_at ON call_states;

-- Create trigger to update updated_at when metadata changes
CREATE TRIGGER update_call_states_metadata_updated_at
  BEFORE UPDATE OF metadata ON call_states
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();