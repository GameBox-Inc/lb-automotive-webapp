import uuid
import json
import logging
import os
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse, Gather

# Initialize logger
logger = logging.getLogger(__name__)
from datetime import datetime, time, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Header, BackgroundTasks, APIRouter, Request, Response, Depends, Form
from database import get_db_connection, upsert_call_state, update_appointment_status, fmt_query, get_setting, DatabaseContextManager
from llm_service import classify_intent, generate_response
from utils.ivr_helper import get_random_filler, get_redis_result_key, clear_ivr_state
from utils.background_tasks import process_ivr_intent_async
from security import redis_client
from routes.smart_jump_helper import process_smart_jump


# Security Configuration
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
MAX_PENDING_APPOINTMENTS = 2
# MED-3: Moved from hardcoded string to environment variable.
# Set TWILIO_WEBHOOK_BASE_URL in your .env or K8s secret.
WEBHOOK_BASE_URL = os.getenv(
    "TWILIO_WEBHOOK_BASE_URL",
    "https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook"
) or "https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook"

router = APIRouter(prefix="/api/twilio", tags=["twilio"])

async def validate_twilio_request(request: Request):
    """
    Validate that the request is coming from Twilio.
    MED-4: Set TWILIO_SKIP_VALIDATION=true ONLY in dev environments without real Twilio traffic.
    """
    # MED-4: Replaced broad ENVIRONMENT==development bypass with an explicit opt-in flag.
    # This prevents accidental bypass if ENVIRONMENT is misconfigured in production.
    if os.getenv("TWILIO_SKIP_VALIDATION", "false").lower() == "true":
        logger.warning(
            "SECURITY WARNING: Twilio request validation is DISABLED (TWILIO_SKIP_VALIDATION=true). "
            "This must not be set in production environments."
        )
        return

    try:
        validator = RequestValidator(TWILIO_AUTH_TOKEN)
        
        # Get the full URL (including query params)
        url = str(request.url)
        
        # Handle proxy headers for correct URL reconstruction
        # Twilio sends requests to the public HTTPS URL, but internal proxy might forward as HTTP
        # and strip prefixes (e.g. /lb-automotive)
        
        # 1. Handle Scheme (HTTP vs HTTPS)
        scheme_override = request.headers.get("x-forwarded-proto")
        
        # 2. Handle Prefix (e.g. /lb-automotive)
        # Check standard and Traefik specific headers
        prefix_override = request.headers.get("x-forwarded-prefix")
        original_uri = request.headers.get("x-original-uri") or request.headers.get("x-forwarded-uri")
        
        if scheme_override or prefix_override or original_uri:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(url)
            
            new_scheme = scheme_override if scheme_override else parsed.scheme
            new_netloc = parsed.netloc
            new_path = parsed.path
            new_query = parsed.query
            
            # If we have the full original URI, use its path and query
            if original_uri:
                # original_uri might be full URL or just path
                if original_uri.startswith("http"):
                    parsed_orig = urlparse(original_uri)
                    new_path = parsed_orig.path
                    new_query = parsed_orig.query
                else:
                    # It's just the path + query
                    if "?" in original_uri:
                        new_path, new_query = original_uri.split("?", 1)
                    else:
                        new_path = original_uri
                        
            elif prefix_override:
                # Fallback to appending prefix if no original URI
                clean_prefix = prefix_override.rstrip('/')
                new_path = f"{clean_prefix}{parsed.path}"
            
            url = urlunparse((new_scheme, new_netloc, new_path, parsed.params, new_query, parsed.fragment))
        
        # 3. Hard fallback for missing headers in known production environment
        # If headers failed to provide the prefix, and we are on the specific domain, force it.
        if "twilio.kozytherocket.space" in url and "/lb-automotive" not in url:
            url = url.replace("/api/twilio", "/lb-automotive/api/twilio")

        # Get the POST data
        form = await request.form()
        params = dict(form)
        
        # Get the signature header
        signature = request.headers.get("X-Twilio-Signature", "")
        
        # DEBUG LOGGING
        # Log headers to debug proxy strippings
        safe_headers = {k: v for k, v in request.headers.items() if k.lower() not in ["authorization", "x-twilio-signature"]}
        logger.info(f"Twilio Validation Debug: Headers={safe_headers}")
        logger.info(f"Validating URL={url}")
        
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
        with DatabaseContextManager(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute(fmt_query("SELECT COUNT(*) as count FROM appointments WHERE phone_number = ? AND status = 'pending'"), (phone_number,))
            row = cursor.fetchone()
        
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
        with DatabaseContextManager(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute(fmt_query("""
                SELECT id, call_sid, current_step, language, metadata, appointment_id, 
                       last_response_time, created_at, updated_at
                FROM call_states WHERE call_sid = ?
            """), (call_sid,))
            row = cursor.fetchone()
        
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
        with DatabaseContextManager(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute(fmt_query("SELECT value FROM settings WHERE key = ?"), (key,))
            row = cursor.fetchone()
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
        cursor.execute(fmt_query("""
            INSERT INTO ivr_logs (id, call_sid, step, input)
            VALUES (?, ?, ?, ?)
        """), (log_id, call_sid, step, input_data))
        
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
        cursor.execute(fmt_query("""
            INSERT INTO ivr_analytics (id, call_sid, node_name, decision_taken, duration_seconds)
            VALUES (?, ?, ?, ?, ?)
        """), (analytics_id, call_sid, node_name, decision_taken, duration_seconds))
        
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
        cursor.execute(fmt_query("SELECT decision_path FROM call_states WHERE call_sid = ?"), (call_sid,))
        row = cursor.fetchone()
        
        if row:
            current_path = json.loads(row["decision_path"]) if row["decision_path"] else []
            current_path.append(node_name)
            
            cursor.execute(fmt_query("""
                UPDATE call_states 
                SET decision_path = ?
                WHERE call_sid = ?
            """), (json.dumps(current_path), call_sid))
            
            conn.commit()
        
        conn.close()
    except Exception as e:
        logger.error(f"Error updating decision path: {e}")


# --- Decision Tree Structure ---
DECISION_TREE = {
    "start": {
        "type": "gather",
        "prompt_en": "Welcome to L-B Automotive Repair. For English, press 1 or say English. Para español, presione 2 o diga Español.",
        "prompt_es": "Bienvenido a L-B Automotive Repair. Para español, presione 2 o diga Español. For English, press 1 or say English.",
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
            "input": "speech dtmf"
        },
        "transitions": {
            "1": "collect_vehicle",
            "appointment": "collect_vehicle",
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
            "input": "speech dtmf"
        },
        "transitions": {
            "1": "collect_vehicle",
            "cita": "collect_vehicle",
            "2": "emergency_services",
            "emergencia": "emergency_services",
        },
        "default": "main_menu_es"
    },
    
    "collect_vehicle": {
        "type": "gather",
        "prompt_en": "Please describe your vehicle, including the year, make, and model. Or press star to skip.",
        "prompt_es": "Por favor describa su vehículo, incluyendo el año, marca y modelo. O presione asterisco para saltar.",
        "gather_config": {
            "timeout": 5,
            "input": "speech dtmf"
        },
        "transitions": {
            "*": "collect_plate",
            "skip": "collect_plate",
            "default": "collect_plate"
        },
        "handler": "handle_vehicle_collection"
    },
    
    "collect_plate": {
        "type": "gather",
        "prompt_en": "Please say your license plate number, or press star to skip.",
        "prompt_es": "Por favor diga su número de placa, o presione asterisco para saltar.",
        "gather_config": {
            "timeout": 5,
            "input": "speech dtmf"
        },
        "transitions": {
            "*": "select_time",
            "skip": "select_time",
            "default": "select_time"
        },
        "handler": "handle_plate_collection"
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
    },
    
    "collect_symptoms": {
        "type": "gather",
        "prompt_en": "Please briefly describe the issue with your vehicle after the beep. For example, say 'I need an oil change' or 'my brakes are squeaking'.",
        "prompt_es": "Por favor describa brevemente el problema. Por ejemplo, diga 'necesito un cambio de aceite' o 'mis frenos hacen ruido'.",
        "gather_config": {
            "input": "speech",
            "timeout": 5,
            "speech_timeout": "auto"
        },
        "transitions": {
            "default": "process_symptoms"
        }
    },
    
    "process_symptoms": {
        "type": "function",
        "handler": "handle_symptoms_processing"
    },
    
    "confirm_booking": {
        "type": "function",
        "handler": "handle_booking"
    },
    
    "completed": {
        "type": "terminal",
        "prompt_en": "Your appointment is confirmed. Thank you for choosing L-B Automotive. Goodbye.",
        "prompt_es": "Su cita está confirmada. Gracias por elegir L-B Automotive. Adiós."
    }
}


def handle_smart_jump(intent, llm_result, CallSid, metadata, response, language):
    """
    Handles 'Smart Jump' - detecting intent/service and skipping menu steps.
    Used by the tree 'function' node.
    """
    if process_smart_jump(intent, llm_result, CallSid, metadata, response, language):
        return None # Jump occurred, redirect already added
    return "welcome"

def handle_service_category(user_input, language, CallSid, metadata, response):
    """Handler for selecting a service category."""
    with DatabaseContextManager(read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute(fmt_query("SELECT DISTINCT category FROM services ORDER BY category"))
        categories = [row["category"] for row in cursor.fetchall()]
    
    metadata["categories"] = categories
    upsert_call_state(CallSid, "select_service_category", language, metadata)
    
    voice = "Polly.Lupe" if language == "es" else "Polly.Matthew"
    message = "Por favor seleccione una categoría:" if language == "es" else "Please select a category:"
    response.say(message, voice=voice)
    
    for idx, cat in enumerate(categories, 1):
        response.say(f"For {cat.replace('_', ' ')}, press {idx}", voice=voice)
    
    gather = Gather(num_digits=1, input="dtmf", action=f"{WEBHOOK_BASE_URL}?step=select_service_detail")
    response.append(gather)
    return None

def handle_vehicle_collection(user_input, language, CallSid, metadata, response):
    """Saves vehicle details and moves to next step."""
    if user_input and user_input not in ["*", "skip"]:
        metadata["vehicle_info"] = user_input
    upsert_call_state(CallSid, "collect_plate", language, metadata)
    return "collect_plate"

def handle_plate_collection(user_input, language, CallSid, metadata, response):
    """Saves plate number and moves to time selection."""
    if user_input and user_input not in ["*", "skip"]:
        metadata["license_plate"] = user_input
    upsert_call_state(CallSid, "select_time", language, metadata)
    return "select_time"

def check_shop_bandwidth(date_str, slot_time):
    """Checks if the shop has capacity for another appointment at this time."""
    try:
        # DB Optimization: Use read-only connection
        with DatabaseContextManager(read_only=True) as conn:
            cursor = conn.cursor()
            # Staff count from settings
            cursor.execute(fmt_query("SELECT value FROM settings WHERE key = 'staff_count'"))
            staff_row = cursor.fetchone()
            staff_limit = int(staff_row['value']) if staff_row else 5
            
            # Count existing appointments for this slot
            appt_datetime = f"{date_str}T{slot_time}:00"
            cursor.execute(fmt_query("SELECT COUNT(*) as count FROM appointments WHERE appointment_time = ? AND status != 'cancelled'"), (appt_datetime,))
            count_row = cursor.fetchone()
            current_count = count_row['count'] if count_row else 0
            
            return current_count < staff_limit
    except Exception as e:
        logger.error(f"Bandwidth check error: {e}")
        return True # Fallback to allowing

def handle_time_selection(user_input, language, CallSid, metadata, response):
    """Handler for selecting an appointment time with bandwidth check."""
    from utils_scheduler import get_available_slots_logic
    from llm_service import analyze_schedule
    
    selected_service = metadata.get("selected_service", {"id": "general", "name": "General Service"})
    tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    raw_slots = get_available_slots_logic(tomorrow_date, selected_service.get('id'))
    
    # Filter slots based on bandwidth
    available_slots = [s for s in raw_slots if check_shop_bandwidth(tomorrow_date, s)]
    
    if not available_slots:
        voice = "Polly.Lupe" if language == "es" else "Polly.Matthew"
        response.say("I'm sorry, we are fully booked for tomorrow. Please try another day online. Goodbye.", voice=voice)
        response.hangup()
        return None

    slot_summary = analyze_schedule(available_slots, tomorrow_date, selected_service.get('name'))
    
    voice = "Polly.Lupe" if language == "es" else "Polly.Matthew"
    response.say(slot_summary, voice=voice)
    
    if not available_slots:
        response.hangup()
        return None

    metadata["available_slots"] = available_slots
    metadata["target_date"] = tomorrow_date
    upsert_call_state(CallSid, "select_time", language, metadata)
    
    gather = Gather(num_digits=1, input="speech dtmf", action=f"{WEBHOOK_BASE_URL}?step=collect_symptoms")
    response.append(gather)
    return None

def handle_booking(user_input, language, CallSid, metadata, response):
    """Final booking handler including vehicle details."""
    choice = metadata.get("time_slot_choice")
    slots = metadata.get("available_slots", [])
    target_date = metadata.get("target_date")
    svc = metadata.get("selected_service", {})
    
    chosen_slot = None
    if choice == "1": # Morning
        chosen_slot = next((s for s in slots if int(s.split(':')[0]) < 12), None)
    elif choice == "2": # Afternoon
        chosen_slot = next((s for s in slots if int(s.split(':')[0]) >= 12), None)
    
    voice = "Polly.Lupe" if language == "es" else "Polly.Matthew"
    if chosen_slot:
        appt_time = f"{target_date}T{chosen_slot}:00"
        aid = str(uuid.uuid4())
        
        # Build comprehensive notes
        notes_parts = []
        if metadata.get("vehicle_info"): notes_parts.append(f"Vehicle: {metadata['vehicle_info']}")
        if metadata.get("license_plate"): notes_parts.append(f"Plate: {metadata['license_plate']}")
        if metadata.get("symptoms"): notes_parts.append(f"Issue: {metadata['symptoms']}")
        final_notes = " | ".join(notes_parts)
        
        # Use Primary for write
        with DatabaseContextManager(read_only=False) as conn:
            cursor = conn.cursor()
            cursor.execute(fmt_query("""
                INSERT INTO appointments (id, customer_name, phone_number, appointment_time, service_type, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """), (aid, metadata.get("customer_name", "Voice Customer"), metadata.get("from_phone"), appt_time, svc.get('name', 'General Service'), 'pending', final_notes))
            conn.commit()
        
        upsert_call_state(CallSid, "completed", language, metadata, aid)
        response.say(f"Confirmed. See you at {chosen_slot}. Goodbye.", voice=voice)
        response.hangup()
    else:
        response.say("Sorry, that slot is gone.", voice=voice)
        response.redirect(f"{WEBHOOK_BASE_URL}?step=select_time")
    return None

def handle_symptoms_processing(user_input, language, CallSid, metadata, response):
    """Summarizes user symptoms using LLM."""
    from llm_service import generate_response
    
    symptoms = user_input or "No description provided."
    if user_input and len(user_input) > 5:
        system_prompt = "Summarize car issue in 1 sentence for a mechanic. Brief and technical. Speak to the mechanic directly."
        try:
            summary = generate_response(user_input, "", system_prompt)
            if "trouble thinking" not in summary.lower():
                symptoms = summary
        except Exception:
            pass
            
    metadata["symptoms"] = symptoms
    upsert_call_state(CallSid, "confirm_booking", language, metadata)
    return "confirm_booking"

def handle_emergency(user_input, language, CallSid, metadata, response):
    """Emergency routing handler."""
    with DatabaseContextManager(read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute(fmt_query("SELECT * FROM services WHERE is_emergency = 1 ORDER BY name"))
        services = [dict(row) for row in cursor.fetchall()]
    
    metadata["services"] = services
    upsert_call_state(CallSid, "emergency_services", language, metadata)
    
    voice = "Polly.Lupe" if language == "es" else "Polly.Matthew"
    response.say("Emergency services available:", voice=voice)
    for idx, s in enumerate(services, 1):
        response.say(f"For {s['name']}, press {idx}", voice=voice)
    
    gather = Gather(num_digits=1, input="dtmf", action=f"{WEBHOOK_BASE_URL}?step=confirm_emergency")
    response.append(gather)
    return None

def get_tree_node(step: str) -> Optional[dict]:
    """Retrieve node from the decision tree."""
    return DECISION_TREE.get(step)

# --- Webhook Handler ---

@router.post("/webhook", dependencies=[Depends(validate_twilio_request)])
def twilio_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    CallSid: str = Form(...),
    From: str = Form(...),
    Digits: Optional[str] = Form(None),
    SpeechResult: Optional[str] = Form(None),
    step: str = "start"
):
    """Handle incoming Twilio calls with speech and DTMF support."""
    response = VoiceResponse()
    try:
        voice = get_setting("ivr_voice", "alice")
        language = get_setting("ivr_language", "en-US")
        call_state = get_call_state(CallSid) or {"call_sid": CallSid, "current_step": "welcome", "language": "en", "metadata": {}}
        language = call_state.get("language", "en")
        voice = "Polly.Lupe" if language == "es" else "Polly.Matthew"
        metadata = call_state.get("metadata", {})
        metadata["from_phone"] = From
        input_data = Digits if Digits else SpeechResult
        if input_data: log_ivr_interaction(CallSid, step, input_data)
        intent = None
        llm_result = {}
        masking_enabled = get_setting("ivr_latency_masking_enabled", "true").lower() == "true"
        if SpeechResult and step != "processing":
            if masking_enabled:
                background_tasks.add_task(process_ivr_intent_async, CallSid, SpeechResult)
                response.say(get_random_filler(), voice=voice)
                response.redirect(f"{WEBHOOK_BASE_URL}?step=processing")
                return Response(content=str(response), media_type="application/xml")
            else:
                try:
                    llm_result = classify_intent(SpeechResult)
                    intent = llm_result.get("intent")
                except Exception:
                    intent = "unknown"
        elif step == "processing":
            result_key = get_redis_result_key(CallSid)
            result_data = redis_client.get(result_key) if redis_client else None
            if result_data:
                llm_result = json.loads(result_data)
                intent = llm_result.get("intent")
                if redis_client: redis_client.delete(result_key)
                metadata["wait_count"] = 0
            else:
                wait_count = int(metadata.get("wait_count", 0))
                if wait_count * 2 < int(get_setting("ivr_processing_timeout", "10")):
                    metadata["wait_count"] = wait_count + 1
                    upsert_call_state(CallSid, "processing", language, metadata)
                    response.redirect(f"{WEBHOOK_BASE_URL}?step=processing")
                    return Response(content=str(response), media_type="application/xml")
                else:
                    intent = "unknown"
        node = get_tree_node(step)
        
        # Smart routing for processing state
        if step == "processing":
            if intent:
                # Handle Smart Jump from LLM intent
                ns = handle_smart_jump(intent, llm_result, CallSid, metadata, response, language)
                if ns:
                    response.redirect(f"{WEBHOOK_BASE_URL}?step={ns}")
                    return Response(content=str(response), media_type="application/xml")
                else:
                    # Fallback to menu if jump didn't trigger
                    response.redirect(f"{WEBHOOK_BASE_URL}?step=main_menu_{language}")
                    return Response(content=str(response), media_type="application/xml")
            else:
                # Still waiting or unknown, repeat current node if we have one, or go to menu
                response.redirect(f"{WEBHOOK_BASE_URL}?step=main_menu_{language}")
                return Response(content=str(response), media_type="application/xml")

        if node:
            update_decision_path(CallSid, step)
            node_type = node.get("type")
            if node_type == "gather":
                gc = node.get("gather_config", {})
                
                # Check for handler if it's a gather node with logic
                handler_name = node.get("handler")
                if input_data:
                    if handler_name == "handle_vehicle_collection": 
                        ns = handle_vehicle_collection(input_data, language, CallSid, metadata, response)
                        if ns: 
                            response.redirect(f"{WEBHOOK_BASE_URL}?step={ns}")
                            return Response(content=str(response), media_type="application/xml")
                    elif handler_name == "handle_plate_collection":
                        ns = handle_plate_collection(input_data, language, CallSid, metadata, response)
                        if ns:
                            response.redirect(f"{WEBHOOK_BASE_URL}?step={ns}")
                            return Response(content=str(response), media_type="application/xml")

                next_s = node.get("transitions", {}).get(Digits or SpeechResult or "default", node.get("default", step))
                gather = Gather(num_digits=gc.get("num_digits", 1), timeout=gc.get("timeout", 5), input=gc.get("input", "dtmf"), action=f"{WEBHOOK_BASE_URL}?step={next_s}")
                gather.say(node.get(f"prompt_{language}", node.get("prompt_en")), voice=voice)
                response.append(gather)
            elif node_type == "function":
                handler_name = node.get("handler")
                ns = None
                if handler_name == "handle_smart_jump": ns = handle_smart_jump(intent, llm_result, CallSid, metadata, response, language)
                elif handler_name == "handle_symptoms_processing": ns = handle_symptoms_processing(input_data, language, CallSid, metadata, response)
                elif handler_name == "handle_booking": ns = handle_booking(None, language, CallSid, metadata, response)
                if ns: response.redirect(f"{WEBHOOK_BASE_URL}?step={ns}")
            elif node_type == "dynamic":
                handler_name = node.get("handler")
                if handler_name == "handle_service_category": handle_service_category(input_data, language, CallSid, metadata, response)
                elif handler_name == "handle_time_selection": handle_time_selection(input_data, language, CallSid, metadata, response)
                elif handler_name == "handle_emergency": handle_emergency(input_data, language, CallSid, metadata, response)
            elif node_type == "terminal":
                response.say(node.get(f"prompt_{language}", node.get("prompt_en")), voice=voice)
                response.hangup()
            track_decision(CallSid, step, input_data)
            return Response(content=str(response), media_type="application/xml")
        response.say("Goodbye.", voice=voice)
        response.hangup()
        return Response(content=str(response), media_type="application/xml")
    except Exception as e:
        logger.error(f"IVR Error: {e}")
        response.say("An error occurred.", voice="Polly.Matthew")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")
