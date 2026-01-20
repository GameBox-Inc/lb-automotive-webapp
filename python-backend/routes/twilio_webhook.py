import uuid
import json
import logging
from datetime import datetime, time, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Form, Response, Depends
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
import os
from database import get_db_connection, upsert_call_state, update_appointment_status
from models import CallState, IVRLog
from llm_service import classify_intent, generate_response

router = APIRouter(prefix="/api/twilio", tags=["twilio"])
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def get_call_state(call_sid: str) -> Optional[dict]:
    """Get call state from database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, call_sid, current_step, language, metadata, appointment_id, 
                   last_response_time, created_at, updated_at
            FROM call_states WHERE call_sid = ?
        """, (call_sid,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row["id"],
                "call_sid": row["call_sid"],
                "current_step": row["current_step"],
                "language": row["language"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                "appointment_id": row["appointment_id"],
                "last_response_time": row["last_response_time"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
        return None
    except Exception as e:
        logger.error(f"Error fetching call state: {e}")
        return None

def get_setting(key: str, default: str) -> str:
    """Get a specific setting value from the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row['value'] if row else default
    except Exception as e:
        logger.error(f"Error fetching setting {key}: {e}")
        return default

def is_business_open():
    """Check if currently within business hours based on DB settings."""
    try:
        opening_time_str = get_setting('opening_time', "08:00")
        closing_time_str = get_setting('closing_time', "18:00")
        
        now = datetime.now().time()
        open_time = datetime.strptime(opening_time_str, "%H:%M").time()
        close_time = datetime.strptime(closing_time_str, "%H:%M").time()
        
        return open_time <= now <= close_time
    except Exception as e:
        logger.error(f"Error checking business hours: {e}")
        return True # Default to open on error

def log_ivr_interaction(call_sid: str, step: str, input_data: str = None):
    """Log IVR interaction."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        log_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO ivr_logs (id, call_sid, step, input)
            VALUES (?, ?, ?, ?)
        """, (log_id, call_sid, step, input_data))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error logging IVR interaction: {e}")

# --- Webhook Handler ---

@router.post("/webhook")
def twilio_webhook(
    CallSid: str = Form(...),
    From: str = Form(...),
    Digits: Optional[str] = Form(None),
    SpeechResult: Optional[str] = Form(None),
    step: str = "start"
):
    """
    Handle incoming Twilio calls with speech and DTMF support.
    """
    response = VoiceResponse()
    
    try:
        # Get configuration from DB
        voice = get_setting('ivr_voice', 'alice')
        language = get_setting('ivr_language', 'en-US')
        
        # Check business hours on initial call
        if step == "start":
            if not is_business_open():
                closed_message = get_setting(
                    'ivr_closed_message', 
                    "We are currently closed. Our hours are 8 AM to 6 PM. Please call back during business hours."
                )
                response.say(closed_message, voice=voice, language=language)
                response.hangup()
                return Response(content=str(response), media_type="application/xml")

        # Fetch/Create state
        call_state = get_call_state(CallSid)
        if not call_state:
            call_state = {
                "call_sid": CallSid,
                "current_step": "welcome",
                "language": "en",
                "metadata": {}
            }
        
        # Update context from state
        language = call_state.get("language", "en")
        # Adjust voice based on language
        voice = "Polly.Lupe" if language == "es" else "Polly.Matthew"
        metadata = call_state.get("metadata", {})
        
        # Log interaction (Digits or Speech)
        input_data = Digits if Digits else SpeechResult
        log_ivr_interaction(CallSid, step, input_data)
        
        # Determine intent if speech was used
        intent = None
        if SpeechResult:
            # Hybrid Approach: Use Local LLM for intent classification
            try:
                llm_result = classify_intent(SpeechResult)
                intent = llm_result.get("intent")
                logger.info(f"LLM Classification: {SpeechResult} -> {intent}")
            except Exception as e:
                logger.error(f"LLM classification failed: {e}")
                # Fallback to keyword matching if LLM fails
                speech_lower = SpeechResult.lower()
                if "appointment" in speech_lower or "schedule" in speech_lower or "cita" in speech_lower:
                    intent = "appointment"
                elif "emergency" in speech_lower or "help" in speech_lower or "emergencia" in speech_lower:
                    intent = "emergency"
                elif "spanish" in speech_lower or "español" in speech_lower:
                    intent = "spanish"
                elif "english" in speech_lower or "inglés" in speech_lower:
                    intent = "english"

        # --- State Machine ---

        if step == "start" or step == "welcome":
            # If user already spoke 'spanish' or pushed 2, switch language immediately
            if intent == "spanish" or Digits == "2":
                language = "es"
                upsert_call_state(CallSid, "menu", language)
                response.redirect("/api/twilio/webhook?step=menu")
                return Response(content=str(response), media_type="application/xml")
            
            # Check for returning customer
            conn = get_db_connection()
            cursor = conn.cursor()
            # Normalize 'From' number (e.g., +1845...)
            clean_from = From.replace("+", "").replace("-", "").strip()
            # Try exact match or match specific substring if needed
            cursor.execute("SELECT name FROM customers WHERE replace(replace(phone, '-', ''), '+', '') LIKE ?", (f"%{clean_from}%",))
            row = cursor.fetchone()
            conn.close()
            
            customer_name = row["name"] if row else None
            greeting = "Welcome to L B Automotive."
            if customer_name:
                 # Extract first name
                 first_name = customer_name.split()[0]
                 greeting = f"Welcome back, {first_name}."
                 metadata["customer_name"] = customer_name
                 upsert_call_state(CallSid, "welcome", language, metadata)

            gather = Gather(
                num_digits=1,
                timeout=5,
                speechTimeout="auto", # Reduce latency
                input="speech dtmf",
                action="/api/twilio/webhook?step=language",
                method="POST"
            )
            gather.say(
                f"{greeting} For English, press 1 or say English. Para español, presione 2 o diga Español.",
                voice="Polly.Matthew"
            )
            response.append(gather)
        
        elif step == "language":
            # ... (unchanged) ...
            pass
            # (Note: Step language logic is fine, jumping to menu)

        elif step == "menu":
            # (Code omitted for brevity but I will replace the whole block in actual call)
            # ...
            # Dynamic Response Generation
            if SpeechResult:
                 # If user said something but we didn't catch a direct intent or it was chatty
                 context = "User is at the main menu. They can schedule an appointment or report an emergency."
                 dynamic_reply = generate_response(SpeechResult, context)
                 # Ensure we guide them back to the options if the LLM gets too chatty
                 message = f"{dynamic_reply} To schedule an appointment, press 1. For emergencies, press 2."
            else:
                message = (
                    "Para programar una cita, presione 1 o diga cita. Para emergencias, presione 2 o diga emergencia."
                    if language == "es" else
                    "To schedule an appointment, press 1 or say appointment. For emergencies, press 2 or say emergency."
                )

            gather = Gather(
                num_digits=1,
                timeout=5,
                speechTimeout="auto", # Reduce latency
                input="speech dtmf",
                action="/api/twilio/webhook?step=route",
                method="POST"
            )
            gather.say(message, voice=voice)
            response.append(gather)
        
        elif step == "route":
            # Determine path based on input
            is_emergency = False
            if Digits == "2" or intent == "emergency":
                is_emergency = True
            elif Digits == "1" or intent == "appointment":
                is_emergency = False
            else:
                 # Check for speech numbers if intent wasn't clear
                 if SpeechResult:
                     lower = SpeechResult.lower()
                     if "one" in lower or "1" in lower:
                         is_emergency = False
                     elif "two" in lower or "2" in lower:
                         is_emergency = True
                     else:
                        response.redirect("/api/twilio/webhook?step=menu")
                        return Response(content=str(response), media_type="application/xml")
                 else:
                    response.redirect("/api/twilio/webhook?step=menu")
                    return Response(content=str(response), media_type="application/xml")

            conn = get_db_connection()
            cursor = conn.cursor()
            
            if is_emergency:
                # Emergency services
                cursor.execute("""
                    SELECT id, name, description, duration, price, category
                    FROM services WHERE is_emergency = 1 ORDER BY name
                """)
                services = [dict(row) for row in cursor.fetchall()]
                metadata["services"] = services
                next_step = "select_emergency"
                
                message = (
                    "Por favor seleccione el servicio de emergencia:"
                    if language == "es" else
                    "Please select the emergency service:"
                )
            else:
                # Regular categories
                cursor.execute("SELECT DISTINCT category FROM services ORDER BY category")
                categories = [row["category"] for row in cursor.fetchall()]
                metadata["categories"] = categories
                next_step = "select_category"
                
                message = (
                    "Por favor seleccione una categoría:"
                    if language == "es" else
                    "Please select a category:"
                )
            conn.close()
            
            upsert_call_state(CallSid, next_step, language, metadata)
            
            response.say(message, voice=voice)
            
            items = metadata.get("services" if is_emergency else "categories", [])
            for idx, item in enumerate(items, 1):
                name = item["name"] if isinstance(item, dict) else item
                response.say(f"{name}, press {idx} or say {idx}", voice=voice)
            
            gather = Gather(
                num_digits=1,
                timeout=5,
                input="speech dtmf", # Enable speech
                action=f"/api/twilio/webhook?step={'confirm_emergency' if is_emergency else 'select_service'}",
                method="POST"
            )
            response.append(gather)

        elif step == "select_service":
            # Selection logic for category -> service
            idx = -1
            if Digits:
                idx = int(Digits) - 1
            elif SpeechResult:
                # Try to parse number from speech
                lower = SpeechResult.lower()
                words_to_num = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
                for word, num in words_to_num.items():
                    if word in lower or str(num) in lower:
                        idx = num - 1
                        break
            
            if idx == -1:
                 response.redirect("/api/twilio/webhook?step=route") # Retry
                 return Response(content=str(response), media_type="application/xml")
            
            categories = metadata.get("categories", [])
            if 0 <= idx < len(categories):
                selected_cat = categories[idx]
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM services WHERE category = ?", (selected_cat,))
                services = [dict(row) for row in cursor.fetchall()]
                conn.close()
                
                metadata["services"] = services
                metadata["selected_category"] = selected_cat
                upsert_call_state(CallSid, "select_service_detail", language, metadata)
                
                response.say(f"Services for {selected_cat}:", voice=voice)
                for i, svc in enumerate(services, 1):
                    response.say(f"{svc['name']}, press {i} or say {i}", voice=voice)
                
                gather = Gather(
                    num_digits=1,
                    input="speech dtmf", # Enable Speech
                    action="/api/twilio/webhook?step=select_time",
                    method="POST"
                )
                response.append(gather)
            else:
                 response.say("Invalid selection", voice=voice)
                 response.redirect("/api/twilio/webhook?step=route")

        elif step == "select_time":
            # Service selected, pick time
            idx = -1
            if Digits:
                idx = int(Digits) - 1
            elif SpeechResult:
                 lower = SpeechResult.lower()
                 words_to_num = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
                 for word, num in words_to_num.items():
                    if word in lower or str(num) in lower:
                        idx = num - 1
                        break

            services = metadata.get("services", [])
            if 0 <= idx < len(services):
                selected_service = services[idx]
                metadata["selected_service"] = selected_service
                
                # Fetch REAL availability for tomorrow
                from utils_scheduler import get_available_slots_logic
                tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                
                # We need the service ID to check duration/slots
                # Ensure the service dict has 'id', otherwise we might fail if metadata is incomplete
                service_id = selected_service.get('id') 
                
                slots = []
                if service_id:
                     slots = get_available_slots_logic(tomorrow_date, service_id)
                
                # Aggregate logic: Check for Morning (before 12) and Afternoon (after 12) availability
                has_morning = any(int(s.split(':')[0]) < 12 for s in slots)
                has_afternoon = any(int(s.split(':')[0]) >= 12 for s in slots)
                
                if not slots:
                    response.say("Sorry, we are fully booked for tomorrow. Please call the front desk.", voice=voice)
                    response.hangup()
                    return Response(content=str(response), media_type="application/xml")

                metadata["available_slots"] = slots # Store for confirmation logic
                metadata["target_date"] = tomorrow_date
                upsert_call_state(CallSid, "select_time_slot_confirm", language, metadata)
                
                # Dynamic Menu based on availability
                options = []
                if has_morning:
                    options.append("Press 1 or say morning.")
                if has_afternoon:
                    options.append("Press 2 or say afternoon.")
                
                response.say(
                    f"For tomorrow, {tomorrow_date}, we have openings. {' '.join(options)}",
                    voice=voice
                )
                gather = Gather(num_digits=1, input="speech dtmf", action="/api/twilio/webhook?step=confirm_booking")
                response.append(gather)
            else:
                response.say("Invalid selection", voice=voice)
                response.redirect("/api/twilio/webhook?step=select_service")

        elif step == "confirm_booking":
            chosen_slot = None
            if Digits:
                choice = Digits
            elif SpeechResult:
                lower = SpeechResult.lower()
                if "morning" in lower or "one" in lower or "1" in lower:
                    choice = "1"
                elif "afternoon" in lower or "two" in lower or "2" in lower:
                    choice = "2"
                else:
                    choice = None
            else:
                choice = None

            if choice:
                svc = metadata.get("selected_service", {})
                target_date_str = metadata.get("target_date")
                slots = metadata.get("available_slots", [])
                
                # Resolve approximate choice to specific slot
                
                if choice == "1": # Morning
                    for s in slots:
                        if int(s.split(':')[0]) < 12:
                            chosen_slot = s
                            break
                elif choice == "2": # Afternoon
                    for s in slots:
                        if int(s.split(':')[0]) >= 12:
                            chosen_slot = s
                            break
                
                if chosen_slot:
                    # Book it
                    appt_time = f"{target_date_str}T{chosen_slot}:00"
                    
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    aid = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO appointments (id, customer_name, phone_number, appointment_time, service_type, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (aid, "Voice Customer", From, appt_time, svc.get('name', 'Service'), 'pending')) 
                    conn.commit()
                    conn.close()
                    
                    upsert_call_state(CallSid, "completed", language, metadata, aid)
                    
                    # Human friendly time readout
                    h, m = map(int, chosen_slot.split(':'))
                    ampm = "AM" if h < 12 else "PM"
                    h_display = h if h <= 12 else h - 12
                    
                    response.say(f"Appointment confirmed for {h_display}:{m:02d} {ampm}. Goodbye.", voice=voice)
                    response.hangup()
                else:
                    response.say("Sorry, that time block is no longer available.", voice=voice)
                    response.redirect("/api/twilio/webhook?step=select_time") # Retry
            else:
                response.redirect("/api/twilio/webhook?step=select_time") # Retry

        elif step == "confirm_emergency":
           # Similar logic for emergency but faster
           if Digits:
               idx = int(Digits) - 1
               services = metadata.get("services", [])
               if 0 <= idx < len(services):
                   svc = services[idx]
                   # Book ASAP
                   conn = get_db_connection()
                   cursor = conn.cursor()
                   aid = str(uuid.uuid4())
                   cursor.execute("""
                       INSERT INTO appointments (id, customer_name, phone_number, appointment_time, service_type, status, emergency_request)
                       VALUES (?, ?, ?, ?, ?, ?, 1)
                   """, (aid, "Emergency Caller", From, datetime.now().isoformat(), svc.get('name'), 'pending'))
                   conn.commit()
                   conn.close()
                   
                   response.say("Emergency team notified. We will call you back shortly.", voice=voice)
                   response.hangup()

        else:
            response.say("Goodbye.", voice=voice)
            response.hangup()

        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        response.say("An error occurred. Please try again later.", voice="Polly.Matthew")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")
