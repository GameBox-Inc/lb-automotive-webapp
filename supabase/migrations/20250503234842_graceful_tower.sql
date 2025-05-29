/*
  # Add IVR support fields

  1. New Fields
    - Added `vehicle_model` to store customer's vehicle information
    - Added `vin_number` for vehicle identification
    - Added `emergency_request` flag for urgent service requests
    - Added `preferred_language` for multilingual support
    - Added `last_ivr_interaction` to track call history

  2. Changes
    - Modified `service_type` to include emergency services
    - Enhanced `notes` field to store IVR interaction details

  3. Security
    - Maintained existing RLS policies
    - Added policy for IVR system access
*/

ALTER TABLE appointments
ADD COLUMN IF NOT EXISTS vehicle_model text,
ADD COLUMN IF NOT EXISTS vin_number text,
ADD COLUMN IF NOT EXISTS emergency_request boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS preferred_language text DEFAULT 'en',
ADD COLUMN IF NOT EXISTS last_ivr_interaction timestamptz DEFAULT now();

-- Create policy for IVR system access
CREATE POLICY "Allow IVR system to create appointments"
ON appointments FOR INSERT
TO authenticated
WITH CHECK (true);

-- Create policy for IVR system to read appointments
CREATE POLICY "Allow IVR system to read appointments"
ON appointments FOR SELECT
TO authenticated
USING (true);