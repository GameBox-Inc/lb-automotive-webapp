import uuid
import json
import logging

# Initialize logger
logger = logging.getLogger(__name__)
from datetime import datetime, time, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Form, Response, Depends
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
import os
from database import get_db_connection, upsert_call_state, update_appointment_status
from models import CallState, IVRLog
from twilio.request_validator import RequestValidator
from fastapi import HTTPException, Header


# Security Configuration
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
MAX_PENDING_APPOINTMENTS = 2

router = APIRouter(prefix="/api/twilio", tags=["twilio"])

async def validate_twilio_request(request: Request):
    """
    Validate that the request is coming from Twilio.
    """
    if os.getenv("ENVIRONMENT") == "development":
        return

    try:
        validator = RequestValidator(TWILIO_AUTH_TOKEN)
        
        # Get the full URL (including query params)
        url = str(request.url)
        
        # Handle proxy headers for correct URL reconstruction
        # Twilio sends requests to the public HTTPS URL, but internal proxy might forward as HTTP
        if "x-forwarded-proto" in request.headers:
            scheme = request.headers["x-forwarded-proto"]
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(url)
            # Only replace scheme if it's different to avoid side effects
            if parsed.scheme != scheme:
                url = urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        
        # Get the POST data
        form = await request.form()
        params = dict(form)
        
        # Get the signature header
        signature = request.headers.get("X-Twilio-Signature", "")
        
        # DEBUG LOGGING (Temporary)
        # masking token for safety in logs if ever included, but here we log what we have
        logger.info(f"Validating Twilio Request: URL={url}, Signature={signature}")
        
        if not validator.validate(url, params, signature):
            logger.warning(f"Invalid Twilio Signature. URL: {url}")
            raise HTTPException(status_code=403, detail="Invalid Twilio Signature")
            
    except Exception as e:
        logger.error(f"Error validating Twilio request: {e}")
        # Fail safe? Or fail secure? Fail secure for now.
        raise HTTPException(status_code=403, detail="Validation Error")

def check_rate_limit(phone_number: str) -> bool:
    """
    Check if the phone number has too many pending appointments.
    Returns True if allowed, False if blocked.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM appointments WHERE phone_number = ? AND status = 'pending'", (phone_number,))
        row = cursor.fetchone()
        conn.close()
        
        if row and row['count'] >= MAX_PENDING_APPOINTMENTS:
            return False
        return True
    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        return True # Fail open on DB error to avoid service denial



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

# Business hours check removed - 24/7 booking enabled
# Appointments can be scheduled at any time for future dates

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


def track_decision(call_sid: str, node_name: str, decision_taken: str = None, duration_seconds: int = None):
    """Track IVR decision in analytics table."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        analytics_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO ivr_analytics (id, call_sid, node_name, decision_taken, duration_seconds)
            VALUES (?, ?, ?, ?, ?)
        """, (analytics_id, call_sid, node_name, decision_taken, duration_seconds))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error tracking decision: {e}")


def update_decision_path(call_sid: str, node_name: str):
    """Update the decision path in call_states."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current decision path
        cursor.execute("SELECT decision_path FROM call_states WHERE call_sid = ?", (call_sid,))
        row = cursor.fetchone()
        
        if row:
            current_path = json.loads(row["decision_path"]) if row["decision_path"] else []
            current_path.append(node_name)
            
            cursor.execute("""
                UPDATE call_states 
                SET decision_path = ?
                WHERE call_sid = ?
            """, (json.dumps(current_path), call_sid))
            
            conn.commit()
        
        conn.close()
    except Exception as e:
        logger.error(f"Error updating decision path: {e}")


# --- Decision Tree Structure ---
DECISION_TREE = {
    "start": {
        "type": "gather",
        "prompt_en": "Welcome to LB Automotive. For English, press 1 or say English. Para español, presione 2 o diga Español.",
        "prompt_es": "Bienvenido a LB Automotive. Para español, presione 2 o diga Español. For English, press 1 or say English.",
        "gather_config": {
            "num_digits": 1,
            "timeout": 5,
            "bargein": True,
            "speech_timeout": "auto",
            "input": "speech dtmf"
        },
        "transitions": {
            "1": "main_menu_en",
            "english": "main_menu_en",
            "2": "main_menu_es",
            "español": "main_menu_es",
            "spanish": "main_menu_es",
            "appointment": "smart_jump_service",  # Smart Jump
        },
        "default": "start"  # Repeat if no valid input
    },
    
    "main_menu_en": {
        "type": "gather",
        "prompt_en": "To schedule an appointment, press 1 or say appointment. For road-side assistance and emergencies, press 2 or say emergency.",
        "gather_config": {
            "num_digits": 1,
            "timeout": 5,
            "bargein": True,
            "speech_timeout": "auto",
            "input": "speech dtmf"
        },
        "transitions": {
            "1": "select_time",
            "appointment": "select_time",
            "scheduling": "select_time",
            "2": "emergency_services",
            "emergency": "emergency_services",
        },
        "default": "main_menu_en"
    },
    
    "main_menu_es": {
        "type": "gather",
        "prompt_es": "Para programar una cita, presione 1 o diga cita. Para emergencias, presione 2 o diga emergencia.",
        "gather_config": {
            "num_digits": 1,
            "timeout": 5,
            "bargein": True,
            "speech_timeout": "auto",
            "input": "speech dtmf"
        },
        "transitions": {
            "1": "select_time",
            "cita": "select_time",
            "2": "emergency_services",
            "emergencia": "emergency_services",
        },
        "default": "main_menu_es"
    },
    
    "select_service_category": {
        "type": "dynamic",  # Generated from database
        "handler": "handle_service_category"
    },
    
    "smart_jump_service": {
        "type": "function",
        "handler": "handle_smart_jump"
    },
    
    "select_time": {
        "type": "dynamic",
        "handler": "handle_time_selection"
    },
    
    "confirm_details": {
        "type": "gather",
        "prompt_en": "To confirm your appointment, press 1. To start over, press 9.",
        "prompt_es": "Para confirmar su cita, presione 1. Para comenzar de nuevo, presione 9.",
        "gather_config": {
            "num_digits": 1,
            "timeout": 5,
            "bargein": True,
            "input": "dtmf"
        },
        "transitions": {
            "1": "collect_contact",
            "9": "start"
        },
        "default": "confirm_details"
    },
    
    "collect_contact": {
        "type": "function",
        "handler": "handle_contact_collection"
    },
    
    "book_appointment": {
        "type": "function",
        "handler": "handle_booking"
    },
    
    "emergency_services": {
        "type": "dynamic",
        "handler": "handle_emergency"
    }
}


def get_tree_node(node_name: str) -> Optional[Dict[str, Any]]:
    """Get a node from the decision tree."""
    return DECISION_TREE.get(node_name)


def navigate_tree(node_name: str, user_input: str, language: str = "en") -> Optional[str]:
    """
    Navigate the decision tree based on user input.
    Returns the next node name or None if no match.
    """
    node = get_tree_node(node_name)
    if not node:
        return None
    
    transitions = node.get("transitions", {})
    
    # Normalize user input for matching
    input_lower = user_input.lower() if user_input else ""
    
    # Try exact match first
    if user_input in transitions:
        return transitions[user_input]
    
    # Try lowercase match
    if input_lower in transitions:
        return transitions[input_lower]
    
    # Return default if no match
    return node.get("default")


def process_smart_jump(intent, llm_result, CallSid, metadata, response, language):
    """
    Encapsulates the logic for 'Smart Jump' - detecting intent/service and skipping menu steps.
    Returns True if a jump occurred (response modified), False otherwise.
    """
    # Normalize keys to lowercase for robustness
    if isinstance(llm_result, dict):
        llm_result = {k.lower(): v for k, v in llm_result.items()}
    else:
        llm_result = {}

    intent = llm_result.get("intent", "").lower()

    if intent == "appointment" or intent == "spanish":
        # Check for Spanish intent via LLM
        if intent == "spanish":
            language = "es"
            upsert_call_state(CallSid, "menu", language)
            response.redirect("/api/twilio/webhook?step=menu")
            return True

        # If entity extraction found a service
        extracted_service = llm_result.get("service")
        
        if extracted_service:
            logger.info(f"Smart Jump: Detected service '{extracted_service}'")
            # Try to match service name to DB
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, category, duration FROM services")
            all_services = cursor.fetchall()
            conn.close()
            
            # Simple fuzzy match (case insensitive substring)
            matched_service = None
            for svc in all_services:
                # Improved Fuzzy Match: Check if meaningful parts of the string match
                # Split by space and check overlap
                user_terms = set(extracted_service.lower().split())
                svc_terms = set(svc["name"].lower().split())
                
                # Filter out common stop words if needed, but for now just check intersection
                common = user_terms.intersection(svc_terms)
                
                # If at least 2 words match (or 1 if it's a unique word like 'diagnostic')
                if len(common) >= 2 or (len(common) >= 1 and len(user_terms) == 1):
                    matched_service = svc
                    break
                
                # Fallback: simple substring
                if extracted_service.lower() in svc["name"].lower():
                        matched_service = svc
                        break
            
            if matched_service:
                logger.info(f"Smart Jump: Matched DB service '{matched_service['name']}'")
                metadata["selected_service"] = {
                    "id": matched_service["id"],
                    "name": matched_service["name"],
                    "duration": matched_service["duration"]
                }
                metadata["selected_category"] = matched_service["category"]
                
                # Go straight to select_time
                # We also default language to 'en' if not explicitly spanish
                upsert_call_state(CallSid, "select_time", "en", metadata)
                response.redirect(f"{WEBHOOK_BASE_URL}?step=select_time")
                return True

    return False

# --- Webhook Handler ---

@router.post("/webhook", dependencies=[Depends(validate_twilio_request)])
def twilio_webhook(
    request: Request,
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
        
        # 24/7 booking enabled - no time-based restrictions
        # Customers can call and book appointments at any time

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
        llm_result = {}  # Initialize to empty dict
        if SpeechResult:
            logger.error(f"DEBUG: Processing SpeechResult: '{SpeechResult}'")
            # Hybrid Approach: Use Local LLM for intent classification
            try:
                llm_result = classify_intent(SpeechResult)
                logger.error(f"DEBUG: LLM Result Raw: {llm_result}")
                intent = llm_result.get("intent")
                logger.info(f"LLM Classification: {SpeechResult} -> {intent}")
            except Exception as e:
                logger.error(f"DEBUG: Classification Error: {e}")
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
        else:
            logger.error("DEBUG: No SpeechResult received.")

        # --- State Machine ---

        if step == "start" or step == "welcome":
            # If user already spoke 'spanish' or pushed 2, switch language immediately
            if Digits == "2":
                language = "es"
                upsert_call_state(CallSid, "menu", language)
                response.redirect(f"{WEBHOOK_BASE_URL}?step=menu")
                return Response(content=str(response), media_type="application/xml")
            
            # --- Smart Jump Logic ---
            if process_smart_jump(intent, llm_result, CallSid, metadata, response, language):
                return Response(content=str(response), media_type="application/xml")
            
            # Default fallback if no smart jump
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
            greeting = "Welcome to LB Automotive."
            if customer_name:
                 # Extract first name
                 first_name = customer_name.split()[0]
                 greeting = f"Welcome back, {first_name}."
                 metadata["customer_name"] = customer_name
                 upsert_call_state(CallSid, "welcome", language, metadata)

            gather = Gather(
                num_digits=1,
                timeout=5,
                bargein=True,  # Enable cut-off
                speechTimeout="auto", # Reduce latency
                input="speech dtmf",
                action=f"{WEBHOOK_BASE_URL}?step=language",
                method="POST"
            )
            gather.say(
                f"{greeting} For English, press 1 or say English. Para español, presione 2 o diga Español.",
                voice="Polly.Matthew"
            )
            response.append(gather)
        
        elif step == "language":
            # Check for Smart Jump here too (User said "I need brakes" at the first prompt)
            if process_smart_jump(intent, llm_result, CallSid, metadata, response, language):
                return Response(content=str(response), media_type="application/xml")

            if Digits == "1" or (SpeechResult and "english" in SpeechResult.lower()):
                language = "en"
            elif Digits == "2" or (SpeechResult and "español" in SpeechResult.lower()):
                language = "es"
            
            upsert_call_state(CallSid, "menu", language, metadata)
            response.redirect(f"{WEBHOOK_BASE_URL}?step=menu")
            return Response(content=str(response), media_type="application/xml")

        elif step == "menu":
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
                    "To schedule an appointment, press 1 or say appointment. For road-side assistance and emergencies, press 2 or say emergency."
                )

            gather = Gather(
                num_digits=1,
                timeout=5,
                bargein=True,  # Enable cut-off
                speechTimeout="auto", # Reduce latency
                input="speech dtmf",
                action=f"{WEBHOOK_BASE_URL}?step=route_direct",
                method="POST"
            )
            gather.say(message, voice=voice)
            response.append(gather)
        
        elif step == "route_direct":
            # Simplified routing: appointment (1) -> time selection, emergency (2) -> emergency services
            is_emergency = False
            if Digits == "2" or intent == "emergency":
                is_emergency = True
            elif Digits == "1" or intent == "appointment":
                is_emergency = False
            else:
                # Check for speech numbers if intent wasn't clear
                if SpeechResult:
                    lower = SpeechResult.lower()
                    if "one" in lower or "1" in lower or "appointment" in lower:
                        is_emergency = False
                    elif "two" in lower or "2" in lower or "emergency" in lower:
                        is_emergency = True
                    else:
                        response.redirect(f"{WEBHOOK_BASE_URL}?step=menu")
                        return Response(content=str(response), media_type="application/xml")
                else:
                    response.redirect(f"{WEBHOOK_BASE_URL}?step=menu")
                    return Response(content=str(response), media_type="application/xml")

            if is_emergency:
                # Route to emergency services
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, description, duration, price, category
                    FROM services WHERE is_emergency = 1 ORDER BY name
                """)
                services = [dict(row) for row in cursor.fetchall()]
                conn.close()
                
                metadata["services"] = services
                upsert_call_state(CallSid, "select_emergency", language, metadata)
                
                message = (
                    "Por favor seleccione el servicio de emergencia:"
                    if language == "es" else
                    "Please select from our available emergency services:"
                )
                
                response.say(message, voice=voice)
                
                for idx, item in enumerate(services, 1):
                    response.say(f"For {item['name']}, press {idx} or say {idx}", voice=voice)
                
                gather = Gather(
                    num_digits=1,
                    timeout=5,
                    bargein=True,
                    input="speech dtmf",
                    action=f"{WEBHOOK_BASE_URL}?step=confirm_emergency",
                    method="POST"
                )
                response.append(gather)
            else:
                # Route directly to time selection with default general service
                # Create a default general service entry
                default_service = {
                    "id": "general",
                    "name": "General Service",
                    "duration": 60,  # Default 1 hour
                    "category": "General"
                }
                
                metadata["selected_service"] = default_service
                metadata["selected_category"] = "General"
                metadata["services"] = [default_service]
                
                upsert_call_state(CallSid, "select_time_direct", language, metadata)
                response.redirect(f"{WEBHOOK_BASE_URL}?step=select_time_direct")
                return Response(content=str(response), media_type="application/xml")

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
                        response.redirect(f"{WEBHOOK_BASE_URL}?step=menu")
                        return Response(content=str(response), media_type="application/xml")
                 else:
                    response.redirect(f"{WEBHOOK_BASE_URL}?step=menu")
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
                    "Please select from our available emergency services:"
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
                # Capitalize categories for better speech synthesis
                clean_name = name.capitalize() if isinstance(item, str) else name
                response.say(f"For {clean_name}, press {idx} or say {idx}", voice=voice)
            
            gather = Gather(
                num_digits=1,
                timeout=5,
                bargein=True,  # Enable cut-off
                input="speech dtmf", # Enable speech
                action=f"{WEBHOOK_BASE_URL}?step={'confirm_emergency' if is_emergency else 'select_service'}",
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
                 response.redirect(f"{WEBHOOK_BASE_URL}?step=route") # Retry
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
                    action=f"{WEBHOOK_BASE_URL}?step=select_time",
                    method="POST"
                )
                response.append(gather)
            else:
                 response.say("Invalid selection", voice=voice)
                 response.redirect(f"{WEBHOOK_BASE_URL}?step=route")

        elif step == "select_time_direct":
            # Simplified time selection - no service selection required
            # Use the default general service from metadata
            selected_service = metadata.get("selected_service", {"id": "general", "name": "General Service", "duration": 60})
            
            # Fetch availability for tomorrow
            from utils_scheduler import get_available_slots_logic
            tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            
            # Get available slots using general service duration
            slots = get_available_slots_logic(tomorrow_date, selected_service.get('id'))
            
            # If no slots with ID, try with duration-based logic
            if not slots:
                # Fallback: generate slots based on business hours
                try:
                    opening_str = get_setting('opening_time', "08:00")
                    closing_str = get_setting('closing_time', "18:00")
                    # Simple slot generation for demo
                    slots = ["09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00"]
                except Exception as e:
                    logger.error(f"Error generating slots: {e}")
                    slots = []
            
            # Check for morning and afternoon availability
            has_morning = any(int(s.split(':')[0]) < 12 for s in slots)
            has_afternoon = any(int(s.split(':')[0]) >= 12 for s in slots)
            
            if not slots:
                message = (
                    "Lo sentimos, no hay espacios disponibles mañana. Por favor llame durante horas de oficina para programar."
                    if language == "es" else
                    "Sorry, we have no available appointments tomorrow. Please call during business hours to schedule."
                )
                response.say(message, voice=voice)
                response.hangup()
                return Response(content=str(response), media_type="application/xml")
            
            # Present time options
            message = (
                f"Tenemos disponibilidad mañana, {tomorrow_date}. "
                if language == "es" else
                f"We have availability tomorrow, {tomorrow_date}. "
            )
            
            if has_morning and has_afternoon:
                message += (
                    "Para la mañana, presione 1. Para la tarde, presione 2."
                    if language == "es" else
                    "For morning, press 1. For afternoon, press 2."
                )
            elif has_morning:
                message += (
                    "Tenemos espacios en la mañana. Presione 1 para continuar."
                    if language == "es" else
                    "We have morning slots available. Press 1 to continue."
                )
            else:
                message += (
                    "Tenemos espacios en la tarde. Presione 2 para continuar."
                    if language == "es" else
                    "We have afternoon slots available. Press 2 to continue."
                )
            
            response.say(message, voice=voice)
            
            metadata["available_slots"] = slots
            metadata["target_date"] = tomorrow_date
            upsert_call_state(CallSid, "collect_symptoms", language, metadata)
            
            gather = Gather(
                num_digits=1,
                input="speech dtmf",
                timeout=5,
                action=f"{WEBHOOK_BASE_URL}?step=collect_symptoms",
                method="POST"
            )
            response.append(gather)

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
                
                # Use LLM to generate natural language summary of availability
                from llm_service import analyze_schedule
                
                # Format slots for the LLM
                slot_summary = analyze_schedule(slots, tomorrow_date, selected_service.get('name', 'Service'))
                
                # Check if the LLM output suggests options (it usually will for valid slots)
                # We need to construct the speech.
                # If no slots, the LLM will provide the "Fully booked" message which we can use directly.
                
                response.say(slot_summary, voice=voice)
                
                if not slots:
                     response.hangup()
                     return Response(content=str(response), media_type="application/xml")

                metadata["available_slots"] = slots # Store for confirmation logic
                metadata["target_date"] = tomorrow_date
                upsert_call_state(CallSid, "select_time_slot_confirm", language, metadata)
                
                # We still need a Gather for the user's choice
                # The LLM prompt asks the user to "say their preferred time".
                gather = Gather(num_digits=1, input="speech dtmf", action=f"{WEBHOOK_BASE_URL}?step=collect_symptoms")
                response.append(gather)
            else:
                response.say("Invalid selection", voice=voice)
                response.redirect(f"{WEBHOOK_BASE_URL}?step=select_service")

        elif step == "collect_symptoms":
             # Save selection first if coming from select_time
            if Digits:
                choice = Digits
                # Store the choice for later use in confirm_booking
                metadata["time_slot_choice"] = choice
                upsert_call_state(CallSid, "collect_symptoms", language, metadata)
            elif SpeechResult:
                 # Minimal logic if we just came from select_time confirmation loop
                 lower = SpeechResult.lower()
                 if "morning" in lower or "one" in lower or "1" in lower:
                    choice = "1"
                 elif "afternoon" in lower or "two" in lower or "2" in lower:
                    choice = "2"
                 else:
                    choice = None
                 
                 if choice:
                    metadata["time_slot_choice"] = choice
                    upsert_call_state(CallSid, "collect_symptoms", language, metadata)
                 else:
                    response.say("Invalid time selection. Please try again.", voice=voice)
                    response.redirect(f"{WEBHOOK_BASE_URL}?step=select_time")
                    return Response(content=str(response), media_type="application/xml")
            else:
                # If no Digits or SpeechResult, redirect back to select_time
                response.say("No selection received for time. Please try again.", voice=voice)
                response.redirect(f"{WEBHOOK_BASE_URL}?step=select_time")
                return Response(content=str(response), media_type="application/xml")
            
            message = (
                "Please briefly describe the issue with your vehicle after the beep. For example, say 'I need an oil change' or 'my brakes are squeaking'."
                if language == "en" else
                "Por favor describa brevemente el problema. Por ejemplo, diga 'necesito un cambio de aceite' o 'mis frenos hacen ruido'."
            )
            
            response.say(message, voice=voice)
            
            # Use Gather instead of Record to get immediate transcription
            gather = Gather(
                input="speech",
                timeout=5,
                speechTimeout="auto",
                action=f"{WEBHOOK_BASE_URL}?step=process_symptoms",
                method="POST"
            )
            response.append(gather)

        elif step == "process_symptoms":
            # Store symptoms
            symptoms = "User provided audio description" 
            if SpeechResult: 
                 symptoms = SpeechResult
            elif Digits:
                 symptoms = "User pressed digits during description"
            
            metadata["symptoms"] = symptoms
            upsert_call_state(CallSid, "confirm_booking", language, metadata)

            # Now proceed to confirm booking with the collected symptoms
            response.redirect(f"{WEBHOOK_BASE_URL}?step=confirm_booking")
            return Response(content=str(response), media_type="application/xml")

        elif step == "confirm_booking":
            chosen_slot = None
            # Retrieve choice from metadata, set in collect_symptoms
            choice = metadata.get("time_slot_choice")

            if choice:
                # Default to General Service if selected_service is missing or empty
                svc = metadata.get("selected_service") or {}
                service_name = svc.get('name', 'General Service')
                
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
                    # RATE LIMIT CHECK
                    if not check_rate_limit(From):
                        logger.warning(f"Rate limit exceeded for {From}")
                        response.say("You have too many pending appointments. Please call us directly.", voice=voice)
                        response.hangup()
                        return Response(content=str(response), media_type="application/xml")

                    # Book it
                    appt_time = f"{target_date_str}T{chosen_slot}:00"
                    
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    aid = str(uuid.uuid4())
                    
                    customer_name = metadata.get("customer_name", "Voice Customer")
                    symptoms_desc = metadata.get("symptoms", "No symptoms provided.")
                    
                    # Ensure we don't have "Unknown Service"
                    if not service_name or service_name == "Service":
                        service_name = "General Service"

                    # Insert with notes!
                    cursor.execute("""
                        INSERT INTO appointments (id, customer_name, phone_number, appointment_time, service_type, status, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (aid, "Voice Customer", From, appt_time, service_name, 'pending', symptoms_desc)) 
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
                    response.redirect(f"{WEBHOOK_BASE_URL}?step=select_time") # Retry
            else:
                response.redirect(f"{WEBHOOK_BASE_URL}?step=select_time") # Retry

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
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Webhook error: {e}")
        logger.error(f"Full traceback:\n{error_details}")
        print(f"WEBHOOK ERROR: {e}")
        print(f"TRACEBACK:\n{error_details}")
        response.say("An error occurred. Please try again later.", voice="Polly.Matthew")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")
