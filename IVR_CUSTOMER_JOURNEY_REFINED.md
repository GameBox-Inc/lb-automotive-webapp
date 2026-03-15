# IVR Customer Journey - 24/7 Booking Enabled

**Last Updated:** January 24, 2026
**Status:** ✅ Fully Configured for 24/7 Booking

---

## Changes Made

### 1. Removed Business Hours Restrictions
- ✅ Deleted `is_within_business_hours()` function from `twilio_webhook.py:62-79`
- ✅ Removed all business hours checks from webhook logic
- ✅ No more "we are closed" blocking messages

### 2. Updated Database Settings
- ✅ `ivr_greeting`: "Welcome to LB Automotive. We are available 24/7 to schedule your appointment."
- ✅ `ivr_closed_message`: "Thank you for calling LB Automotive. We accept appointments 24/7 for your convenience."
- ✅ `ivr_24_7_enabled`: Set to `1` (enabled)

### 3. Streamlined Customer Journey
- ✅ Direct flow to booking without time checks
- ✅ Simplified appointment scheduling
- ✅ No service selection required (defaults to "General Service")

---

## Refined IVR Customer Journey

```
┌─────────────────────────────────────────────────────────────────┐
│                    CUSTOMER CALLS ANYTIME                       │
│                         (24/7 Access)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: WELCOME & LANGUAGE SELECTION                           │
│  ─────────────────────────────────────────────────────────────  │
│  • Greeting: "Welcome to LB Automotive" (Personalized if       │
│    returning customer detected)                                 │
│  • Prompt: "For English, press 1 or say English.               │
│            Para español, presione 2 o diga Español."           │
│                                                                  │
│  Smart Features:                                                │
│  ✓ Recognizes returning customers by phone number              │
│  ✓ Speech recognition enabled (can speak or press keys)        │
│  ✓ Smart Jump: If customer says "I need brakes" or mentions   │
│    a service, system skips to time selection directly          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: MAIN MENU                                              │
│  ─────────────────────────────────────────────────────────────  │
│  Options: 1 = Appointment, 2 = Emergency, 3 = Speak to someone  │
│  • Press 1 / Say "Appointment" → Regular Booking              │
│  • Press 2 / Say "Emergency" → Emergency Services             │
│  • Press 3 / Say "Representative" → Transfer (Dial when        │
│    ivr_transfer_number is set; else "unable to transfer")     │
│  • Status: Check status looks up next appointment by phone     │
│    and speaks it, or says no appointment on file.             │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
        ┌───────────────────┐  ┌───────────────────┐
        │ REGULAR BOOKING   │  │ EMERGENCY SERVICE │
        └───────────────────┘  └───────────────────┘
                    │                   │
                    ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3A: TIME SELECTION (Regular Booking)                      │
│  ─────────────────────────────────────────────────────────────  │
│  • System checks tomorrow's availability                        │
│  • Service: Defaults to "General Service" (60 min duration)    │
│  • Prompt: "We have availability tomorrow, [DATE].             │
│            For morning, press 1. For afternoon, press 2."      │
│                                                                  │
│  Smart Features:                                                │
│  ✓ Real-time slot checking using business_hours table          │
│  ✓ Aggregates slots into Morning (<12pm) / Afternoon (≥12pm)  │
│  ✓ LLM-powered natural language availability summary           │
│  ✓ If no slots available, informs customer and ends call       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3B: EMERGENCY SERVICE SELECTION                           │
│  ─────────────────────────────────────────────────────────────  │
│  • Lists all emergency services from database                   │
│  • Customer selects service by number or speech                │
│  • Books ASAP (immediate appointment)                           │
│  • Confirmation: "Emergency team notified. We will call you    │
│    back shortly."                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: COLLECT SYMPTOMS (Regular Booking Only)                │
│  ─────────────────────────────────────────────────────────────  │
│  • Prompt: "Please briefly describe the issue with your        │
│            vehicle after the beep. Press any key when finished."│
│  • Records up to 10 seconds of audio                            │
│  • Twilio transcription enabled                                 │
│  • Symptoms stored in appointment metadata                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: CONFIRM BOOKING                                        │
│  ─────────────────────────────────────────────────────────────  │
│  • Determines specific time slot based on choice:              │
│    - Morning (1) → First available slot before 12pm            │
│    - Afternoon (2) → First available slot after 12pm           │
│  • Creates appointment in database with status: 'pending'      │
│  • Stores:                                                      │
│    - Customer phone number (From)                               │
│    - Appointment time (tomorrow at selected slot)               │
│    - Service type ("General Service" or selected service)      │
│    - Symptoms (if provided)                                     │
│    - Customer name (if recognized)                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 6: CONFIRMATION & GOODBYE                                 │
│  ─────────────────────────────────────────────────────────────  │
│  • Message: "Appointment confirmed for [TIME] [AM/PM]. Goodbye."│
│  • Example: "Appointment confirmed for 9:00 AM. Goodbye."       │
│  • Call ends                                                    │
│                                                                  │
│  Background Actions:                                            │
│  ✓ Appointment logged in 'appointments' table                   │
│  ✓ IVR interaction logged in 'ivr_logs' table                   │
│  ✓ Call state updated to 'completed'                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### 1. 24/7 Availability
- **No time restrictions**: Customers can call anytime to book appointments
- **Business hours used for scheduling only**: The `business_hours` table defines when appointments can be scheduled, not when calls are accepted
- **Tomorrow's availability**: System checks tomorrow's schedule in real-time

### 2. Smart Jump Technology
- **Intent recognition**: LLM classifies customer speech to detect intent
- **Service extraction**: If customer mentions a specific service (e.g., "I need an oil change"), system extracts it
- **Automatic routing**: Skips menu steps and goes straight to relevant section
- **Example**: Customer says "I need brakes" → System jumps directly to time selection with "Brake Service" selected

### 3. Multilingual Support
- **Languages**: English and Spanish
- **Voice adaptation**:
  - English: Polly.Matthew (male voice)
  - Spanish: Polly.Lupe (female voice)
- **Speech recognition**: Understands both languages

### 4. Returning Customer Recognition
- **Phone number lookup**: Checks if caller is in customer database
- **Personalized greeting**: "Welcome back, [First Name]"
- **Pre-filled information**: Customer data automatically associated with appointment

### 5. Dual Input Methods
- **DTMF (keypad)**: Press numbers for quick navigation
- **Speech recognition**: Speak naturally instead of pressing keys
- **Hybrid approach**: System accepts both inputs simultaneously

---

## Database Tables Used

### 1. `call_states`
Tracks active call sessions and metadata:
- `call_sid`: Unique Twilio call identifier
- `current_step`: Current position in IVR flow
- `language`: Selected language (en/es)
- `metadata`: JSON with selected service, time slots, symptoms
- `appointment_id`: Linked appointment ID (if booked)

### 2. `ivr_logs`
Logs all IVR interactions for analytics:
- `call_sid`: Call identifier
- `step`: IVR step name
- `input`: User input (digits or speech)
- `timestamp`: When interaction occurred

### 3. `appointments`
Stores booked appointments:
- `id`: Unique appointment ID
- `customer_name`: Name (or "Voice Customer" if unknown)
- `phone_number`: Caller's phone
- `appointment_time`: Scheduled date/time
- `service_type`: Selected service
- `status`: 'pending', 'confirmed', 'completed', 'cancelled'
- `emergency_request`: 1 if emergency, 0 if regular

### 4. `business_hours`
Defines when appointments can be scheduled:
- `day_of_week`: 0=Monday, 6=Sunday
- `opening_time`: Start time (HH:MM)
- `closing_time`: End time (HH:MM)
- `is_closed`: 1 if closed all day, 0 if open

### 5. `settings`
IVR configuration:
- `ivr_greeting`: Welcome message
- `ivr_closed_message`: 24/7 availability message
- `ivr_24_7_enabled`: Enable/disable 24/7 booking
- `ivr_voice`: TTS voice selection
- `ivr_language`: Default language

---

## Error Handling

### No Available Slots
- **Message**: "Sorry, we have no available appointments tomorrow. Please call during business hours to schedule."
- **Action**: Call ends gracefully

### Invalid Selection
- **Message**: "Invalid selection. Please try again."
- **Action**: Repeats current menu

### Technical Error
- **Message**: "An error occurred. Please try again later."
- **Action**: Logs error, ends call gracefully
- **Logging**: Full traceback logged for debugging

---

## Testing the IVR

### Test Scenarios

1. **Regular Booking Flow**
   - Call the Twilio number
   - Press 1 for English
   - Press 1 for Appointment
   - Select morning (1) or afternoon (2)
   - Describe issue after beep
   - Confirm appointment

2. **Smart Jump Test**
   - Call the Twilio number
   - Say "I need an oil change" at first prompt
   - System should skip directly to time selection

3. **Emergency Service**
   - Call the Twilio number
   - Press 1 for English
   - Press 2 for Emergency
   - Select emergency service
   - Get immediate confirmation

4. **Spanish Flow**
   - Call the Twilio number
   - Press 2 for Spanish
   - Follow prompts in Spanish

5. **After Hours Test** (Now works 24/7!)
   - Call outside business hours
   - Should work exactly the same as during business hours
   - Can book appointments for tomorrow

---

## Configuration

### Twilio Webhook URL
```
POST https://kozytherocket.space/api/twilio/webhook
```

### Environment Variables Required
```bash
TWILIO_ACCOUNT_SID=<your_account_sid>
TWILIO_AUTH_TOKEN=<your_auth_token>
TWILIO_PHONE_NUMBER=<your_twilio_phone>
```

### LLM Configuration (for Smart Jump)
```bash
LLM_PROVIDER=ollama  # or "anthropic"
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=smollm2:135m
```

---

## Files Modified

1. **`python-backend/routes/twilio_webhook.py`**
   - Removed `is_within_business_hours()` function
   - Removed business hours check at start step
   - Cleaned up comments

2. **`python-backend/migrate_24_7_settings.py`**
   - New migration script to update database settings
   - Updates `ivr_greeting` and `ivr_closed_message`
   - Adds `ivr_24_7_enabled` setting

3. **Database (via migration)**
   - Updated `settings` table entries
   - No schema changes required

---

## Future Enhancements

### Potential Improvements
1. **Multi-day scheduling**: Allow booking beyond tomorrow
2. **Specific time slot selection**: Let customer choose exact time instead of morning/afternoon
3. **Service category selection**: Add service menu back for more specific bookings
4. **Appointment confirmation via SMS**: Send text message confirmation
5. **Calendar integration**: Sync with Google Calendar or iCal
6. **Callback scheduling**: If no slots available, schedule a callback
7. **Preferred mechanic selection**: Let customers choose specific staff
8. **Vehicle information collection**: Ask for make/model/year
9. **Loyalty program integration**: Offer rewards for frequent customers
10. **Payment collection**: Pre-authorize payment via phone

---

## Monitoring & Analytics

### Key Metrics to Track
- **Total calls received**: Count in `call_states`
- **Completion rate**: Calls that result in booked appointments
- **Abandonment rate**: Calls that hang up before booking
- **Average call duration**: From `ivr_analytics`
- **Popular time slots**: Most frequently selected times
- **Language preference**: English vs. Spanish usage
- **Smart Jump effectiveness**: How often users skip menus
- **Emergency vs. regular ratio**: Service type distribution

### Analytics Endpoints
```
GET /api/ivr/analytics/summary?timeframe=30d
GET /api/ivr/analytics/nodes?timeframe=30d
```

---

## Troubleshooting

### Common Issues

1. **"No available appointments" every time**
   - Check `business_hours` table: Ensure days are not marked as `is_closed=1`
   - Verify `opening_time` and `closing_time` are set correctly
   - Check tomorrow's date falls within configured hours

2. **Speech recognition not working**
   - Ensure `input="speech dtmf"` is set in Gather elements
   - Verify Twilio account has speech recognition enabled
   - Check LLM service is running (Ollama or Anthropic)

3. **LLM classification failing**
   - Check `llm_service.py` configuration
   - Verify Ollama is running: `docker ps | grep ollama`
   - Check Anthropic API key if using Claude

4. **Database errors**
   - Verify `DATABASE_URL` environment variable
   - Check SQLite file permissions
   - Run migrations: `python migrate_24_7_settings.py`

---

## Summary

✅ **24/7 booking is now fully enabled!**

Customers can call anytime to schedule appointments. The system:
- Accepts calls 24 hours a day, 7 days a week
- Books appointments for tomorrow based on real availability
- Uses business hours table only for scheduling, not call blocking
- Provides a streamlined, user-friendly experience
- Supports both English and Spanish
- Leverages AI for smart intent recognition

**Next Steps:**
1. Test the IVR by calling your Twilio number
2. Monitor `ivr_logs` and `appointments` tables for activity
3. Adjust business hours in Admin panel if needed
4. Consider adding SMS confirmations for better UX

---

**Questions or Issues?**
- Check logs: `docker logs lb-auto-backend --tail 100`
- Review IVR analytics: Admin dashboard → IVR Analytics
- Database queries: Use SQLite browser or Admin panel
