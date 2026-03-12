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
from database import get_db_connection, update_appointment_status, fmt_query, DatabaseContextManager
from services.llm import classify_intent, generate_response
from services.call_state import get_call_state, upsert_call_state, get_setting, log_ivr_interaction, track_decision, update_decision_path
from utils.ivr_helper import get_random_filler, get_redis_result_key, clear_ivr_state, parse_filler_phrases_setting, apply_latency_mask
from utils.background_tasks import process_ivr_intent_async
from security import redis_client
from routes.twilio.smart_jump import process_smart_jump
from observability.tracing import set_twilio_context, update_phase, get_trace_context
from observability.tracing import PHASE_WEBHOOK_RECEIVED, PHASE_STT_STARTED, PHASE_LLM_STARTED, PHASE_LLM_COMPLETE, PHASE_TTS_READY


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

    if not (TWILIO_AUTH_TOKEN and TWILIO_AUTH_TOKEN.strip()):
        logger.error("Twilio webhook validation failed: TWILIO_AUTH_TOKEN is not set (create twilio-secrets with TWILIO_AUTH_TOKEN)")
        raise HTTPException(
            status_code=503,
            detail="Twilio webhook not configured. Set TWILIO_AUTH_TOKEN (e.g. via twilio-secrets).",
        )

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
        # Set trace context early for Twilio requests (CallSid, AccountSid)
        call_sid = params.get("CallSid") or ""
        account_sid = params.get("AccountSid") or ""
        if isinstance(call_sid, list):
            call_sid = call_sid[0] if call_sid else ""
        if isinstance(account_sid, list):
            account_sid = account_sid[0] if account_sid else ""
        if call_sid:
            set_twilio_context(call_sid, account_sid)
        
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
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating Twilio request: {type(e).__name__}: {e}")
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
# get_call_state, get_setting, log_ivr_interaction, track_decision, update_decision_path
# are imported from services.call_state

# --- Decision Tree Structure ---
DECISION_TREE = {
    "start": {
        "type": "gather",
        "prompt_en": "Hi, this is L-B Automotive. How can we help you today? Say appointment, status update, or speak to someone.",
        "prompt_es": "Hola, L-B Automotive. ¿En qué podemos ayudarle? Diga cita, actualización, o hablar con alguien.",
        "gather_config": {
            "num_digits": 1,
            "timeout": 8,
            "bargein": True,
            "speech_timeout": "auto",
            "input": "speech dtmf"
        },
        "transitions": {
            "1": "collect_vehicle",
            "2": "emergency_services",
            "3": "transfer_representative"
        },
        "default": "start"
    },
    
    "main_menu_en": {
        "type": "gather",
        "prompt_en": "For an appointment, press 1 or say appointment. For emergencies, press 2 or say emergency.",
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
        "prompt_en": "What's the year, make and model of your vehicle? Or press star to skip.",
        "prompt_es": "¿Año, marca y modelo de su vehículo? O presione asterisco para saltar.",
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

    "select_service_detail": {
        "type": "dynamic",
        "handler": "handle_select_service_detail"
    },

    "save_service_selection": {
        "type": "function",
        "handler": "handle_save_service_selection"
    },

    "confirm_emergency": {
        "type": "dynamic",
        "handler": "handle_confirm_emergency"
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
    
    "save_time_choice": {
        "type": "function",
        "handler": "handle_save_time_choice"
    },
    "collect_symptoms": {
        "type": "gather",
        "prompt_en": "Briefly describe the issue—for example, oil change or brakes. After the beep.",
        "prompt_es": "Describa el problema brevemente, por ejemplo cambio de aceite o frenos. Después del tono.",
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
    },
    
    "transfer_representative": {
        "type": "terminal",
        "prompt_en": "Connecting you to a representative. One moment please.",
        "prompt_es": "Conectando con un representante. Un momento por favor."
    },
    
    "check_status": {
        "type": "terminal",
        "prompt_en": "I'll have a service advisor call you back with a status update on your vehicle shortly. Goodbye.",
        "prompt_es": "Un asesor de servicio le llamará pronto con una actualización sobre su vehículo. Adiós."
    }
}


def handle_smart_jump(intent, llm_result, CallSid, metadata, response, language):
    """
    Handles 'Smart Jump' - detecting intent/service and skipping menu steps.
    Used by the tree 'function' node.
    """
    if process_smart_jump(intent, llm_result, CallSid, metadata, response, language):
        return None # Jump occurred, redirect already added
    return "start"

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

def handle_contact_collection(user_input, language, CallSid, metadata, response):
    """User confirmed (pressed 1) on confirm_details — advance to booking."""
    upsert_call_state(CallSid, "collect_contact", language, metadata)
    return "confirm_booking"

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
    from services.llm import analyze_schedule
    
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
    
    gather = Gather(num_digits=1, input="speech dtmf", action=f"{WEBHOOK_BASE_URL}?step=save_time_choice")
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

def handle_save_time_choice(user_input, language, CallSid, metadata, response):
    """Save morning (1) / afternoon (2) choice and advance to symptoms."""
    if user_input in ("1", "2"):
        metadata["time_slot_choice"] = user_input
        upsert_call_state(CallSid, "save_time_choice", language, metadata)
        return "collect_symptoms"
    return "select_time"


def handle_symptoms_processing(user_input, language, CallSid, metadata, response):
    """Summarizes user symptoms using LLM."""
    from services.llm import generate_response
    
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

def handle_select_service_detail(user_input, language, CallSid, metadata, response):
    """Show services in selected category and gather for service selection."""
    categories = metadata.get("categories", [])
    if not categories:
        voice = "Polly.Lupe" if language == "es" else "Polly.Matthew"
        response.say("Please start over.", voice=voice)
        response.redirect(f"{WEBHOOK_BASE_URL}?step=start")
        return None
    try:
        idx = int(user_input or "1") - 1
        category = categories[idx] if 0 <= idx < len(categories) else categories[0]
    except (ValueError, TypeError):
        category = categories[0]
    with DatabaseContextManager(read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute(fmt_query("SELECT id, name, duration FROM services WHERE category = ? ORDER BY name"), (category,))
        services = [dict(row) for row in cursor.fetchall()]
    metadata["category_services"] = services
    metadata["selected_category"] = category
    upsert_call_state(CallSid, "select_service_detail", language, metadata)
    voice = "Polly.Lupe" if language == "es" else "Polly.Matthew"
    response.say(f"Services in {category.replace('_', ' ')}:", voice=voice)
    for i, s in enumerate(services, 1):
        response.say(f"For {s['name']}, press {i}", voice=voice)
    gather = Gather(num_digits=1, input="dtmf", action=f"{WEBHOOK_BASE_URL}?step=save_service_selection")
    response.append(gather)
    return None

def handle_save_service_selection(user_input, language, CallSid, metadata, response):
    """Save selected service and advance to time selection."""
    services = metadata.get("category_services", [])
    if not services:
        return "select_service_category"
    try:
        idx = int(user_input or "1") - 1
        svc = services[idx] if 0 <= idx < len(services) else services[0]
    except (ValueError, TypeError):
        svc = services[0]
    metadata["selected_service"] = {"id": svc["id"], "name": svc["name"], "duration": svc.get("duration", 60)}
    metadata.pop("category_services", None)
    upsert_call_state(CallSid, "select_time", language, metadata)
    return "select_time"

def handle_confirm_emergency(user_input, language, CallSid, metadata, response):
    """Confirm emergency service selection and provide next steps."""
    services = metadata.get("services", [])
    if not services:
        voice = "Polly.Lupe" if language == "es" else "Polly.Matthew"
        response.say("Please start over.", voice=voice)
        response.redirect(f"{WEBHOOK_BASE_URL}?step=start")
        return None
    try:
        idx = int(user_input or "1") - 1
        svc = services[idx] if 0 <= idx < len(services) else services[0]
    except (ValueError, TypeError):
        svc = services[0]
    voice = "Polly.Lupe" if language == "es" else "Polly.Matthew"
    response.say(f"You selected {svc['name']}. A representative will call you shortly. Goodbye.", voice=voice)
    response.hangup()
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
    AccountSid: Optional[str] = Form(None),
    From: str = Form(...),
    Digits: Optional[str] = Form(None),
    SpeechResult: Optional[str] = Form(None),
    step: str = "start"
):
    """Handle incoming Twilio calls with speech and DTMF support."""
    set_twilio_context(CallSid, AccountSid or "")
    update_phase(PHASE_WEBHOOK_RECEIVED)
    response = VoiceResponse()
    try:
        voice = get_setting("ivr_voice", "alice")
        language = get_setting("ivr_language", "en-US")
        call_state = get_call_state(CallSid) or {"call_sid": CallSid, "current_step": "start", "language": "en", "metadata": {}}
        language = call_state.get("language", "en")
        voice = "Polly.Lupe" if language == "es" else "Polly.Matthew"
        metadata = call_state.get("metadata", {})
        metadata["from_phone"] = From
        
        # Analytic Fix: Ensure call_state exists before track_decision
        if not get_call_state(CallSid):
            upsert_call_state(CallSid, step, language, metadata)
        
        input_data = Digits if Digits else SpeechResult
        if input_data: log_ivr_interaction(CallSid, step, input_data)
        intent = None
        llm_result = {}
        masking_enabled = get_setting("ivr_latency_masking_enabled", "true").lower() == "true"
        if SpeechResult and step != "processing":
            update_phase(PHASE_STT_STARTED)
            if masking_enabled:
                trace_ctx = get_trace_context()
                conv_ctx = f"Last intent: {metadata.get('last_intent', 'none')}, step: {step}"
                background_tasks.add_task(process_ivr_intent_async, CallSid, SpeechResult, trace_ctx, conv_ctx)
                filler_mode = get_setting("ivr_filler_mode", "voice_only").lower()
                thinking_url = get_setting("ivr_thinking_sound_url", "") if filler_mode in ("sound_only", "hybrid") else None
                phrases = parse_filler_phrases_setting(get_setting("ivr_filler_phrases", ""))
                filler_phrase = get_random_filler(phrases) if phrases else get_random_filler()
                apply_latency_mask(response, voice, filler_mode, thinking_url or None, filler_phrase)
                update_phase(PHASE_TTS_READY)
                response.redirect(f"{WEBHOOK_BASE_URL}?step=processing")
                logger.info("IVR response", extra={**get_trace_context(), "step": step, "intent": "masking_redirect"})
                return Response(content=str(response), media_type="application/xml")
            else:
                try:
                    update_phase(PHASE_LLM_STARTED)
                    llm_result = classify_intent(SpeechResult)
                    update_phase(PHASE_LLM_COMPLETE)
                    intent = llm_result.get("intent")
                except Exception:
                    intent = "unknown"
        elif step == "processing":
            update_phase(PHASE_LLM_COMPLETE)
            result_key = get_redis_result_key(CallSid)
            result_data = redis_client.get(result_key) if redis_client else None
            if result_data:
                llm_result = json.loads(result_data)
                intent = llm_result.get("intent")
                if redis_client: redis_client.delete(result_key)
                metadata["wait_count"] = 0
                metadata["last_intent"] = intent
                upsert_call_state(CallSid, "processing", language, metadata)
            else:
                wait_count = int(metadata.get("wait_count", 0))
                if wait_count * 2 < int(get_setting("ivr_processing_timeout", "10")):
                    metadata["wait_count"] = wait_count + 1
                    upsert_call_state(CallSid, "processing", language, metadata)
                    update_phase(PHASE_TTS_READY)
                    filler_mode = get_setting("ivr_filler_mode", "voice_only").lower()
                    thinking_url = get_setting("ivr_thinking_sound_url", "") if filler_mode in ("sound_only", "hybrid") else None
                    phrases = parse_filler_phrases_setting(get_setting("ivr_filler_phrases", ""))
                    filler_phrase = get_random_filler(phrases) if phrases else get_random_filler()
                    apply_latency_mask(response, voice, filler_mode, thinking_url or None, filler_phrase)
                    response.redirect(f"{WEBHOOK_BASE_URL}?step=processing")
                    logger.info("IVR response", extra={**get_trace_context(), "step": step, "intent": "processing_poll"})
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
                    update_phase(PHASE_TTS_READY)
                    response.redirect(f"{WEBHOOK_BASE_URL}?step={ns}")
                    return Response(content=str(response), media_type="application/xml")
                else:
                    update_phase(PHASE_TTS_READY)
                    response.redirect(f"{WEBHOOK_BASE_URL}?step=main_menu_{language}")
                    return Response(content=str(response), media_type="application/xml")
            else:
                update_phase(PHASE_TTS_READY)
                response.redirect(f"{WEBHOOK_BASE_URL}?step=main_menu_{language}")
                return Response(content=str(response), media_type="application/xml")

        if node:
            update_decision_path(CallSid, step)
            node_type = node.get("type")
            if node_type == "gather":
                gc = node.get("gather_config", {})
                # Timeout / no input: repair or transfer after max retries
                if not input_data:
                    step_repair = metadata.get("step_repair_count") or {}
                    repair_count = step_repair.get(step, 0) + 1
                    step_repair[step] = repair_count
                    metadata["step_repair_count"] = step_repair
                    upsert_call_state(CallSid, step, language, metadata)
                    max_repairs = int(get_setting("ivr_repair_max_retries", "3"))
                    if repair_count > max_repairs:
                        response.say("Let me connect you to someone who can help.", voice=voice)
                        response.redirect(f"{WEBHOOK_BASE_URL}?step=transfer_representative")
                        logger.info("IVR response", extra={**get_trace_context(), "step": step, "repair": "transfer"})
                        return Response(content=str(response), media_type="application/xml")
                    response.say("Sorry, I didn't catch that. Let's try again.", voice=voice)
                    # Fall through to re-present same gather below (next_s = step, so we re-gather same step)
                    next_s = step
                else:
                    next_s = node.get("transitions", {}).get(Digits or SpeechResult or "default", node.get("default", step))
                # Check for handler if it's a gather node with logic
                handler_name = node.get("handler")
                if input_data:
                    if handler_name == "handle_vehicle_collection": 
                        ns = handle_vehicle_collection(input_data, language, CallSid, metadata, response)
                        if ns:
                            update_phase(PHASE_TTS_READY)
                            response.redirect(f"{WEBHOOK_BASE_URL}?step={ns}")
                            return Response(content=str(response), media_type="application/xml")
                    elif handler_name == "handle_plate_collection":
                        ns = handle_plate_collection(input_data, language, CallSid, metadata, response)
                        if ns:
                            update_phase(PHASE_TTS_READY)
                            response.redirect(f"{WEBHOOK_BASE_URL}?step={ns}")
                            return Response(content=str(response), media_type="application/xml")

                next_s = node.get("transitions", {}).get(Digits or SpeechResult or "default", node.get("default", step))
                gather_kw = dict(
                    num_digits=gc.get("num_digits", 1),
                    timeout=gc.get("timeout", 5),
                    input=gc.get("input", "dtmf"),
                    action=f"{WEBHOOK_BASE_URL}?step={next_s}",
                )
                if "speech" in gc.get("input", ""):
                    gather_kw["barge_in"] = gc.get("bargein", True)
                    gather_kw["speech_timeout"] = gc.get("speech_timeout") or get_setting("ivr_speech_timeout", "auto")
                gather = Gather(**gather_kw)
                prompt_text = node.get(f"prompt_{language}", node.get("prompt_en")) or "Please continue."
                gather.say(prompt_text, voice=voice)
                response.append(gather)
            elif node_type == "function":
                handler_name = node.get("handler")
                ns = None
                if handler_name == "handle_smart_jump": ns = handle_smart_jump(intent, llm_result, CallSid, metadata, response, language)
                elif handler_name == "handle_save_time_choice": ns = handle_save_time_choice(input_data, language, CallSid, metadata, response)
                elif handler_name == "handle_symptoms_processing": ns = handle_symptoms_processing(input_data, language, CallSid, metadata, response)
                elif handler_name == "handle_booking": ns = handle_booking(None, language, CallSid, metadata, response)
                elif handler_name == "handle_contact_collection": ns = handle_contact_collection(input_data, language, CallSid, metadata, response)
                elif handler_name == "handle_save_service_selection": ns = handle_save_service_selection(input_data, language, CallSid, metadata, response)
                if ns: response.redirect(f"{WEBHOOK_BASE_URL}?step={ns}")
            elif node_type == "dynamic":
                handler_name = node.get("handler")
                if handler_name == "handle_service_category": handle_service_category(input_data, language, CallSid, metadata, response)
                elif handler_name == "handle_time_selection": handle_time_selection(input_data, language, CallSid, metadata, response)
                elif handler_name == "handle_emergency": handle_emergency(input_data, language, CallSid, metadata, response)
                elif handler_name == "handle_select_service_detail": handle_select_service_detail(input_data, language, CallSid, metadata, response)
                elif handler_name == "handle_confirm_emergency": handle_confirm_emergency(input_data, language, CallSid, metadata, response)
            elif node_type == "terminal":
                response.say(node.get(f"prompt_{language}", node.get("prompt_en")), voice=voice)
                response.hangup()
            track_decision(CallSid, step, input_data)
            update_phase(PHASE_TTS_READY)
            logger.info("IVR response", extra={**get_trace_context(), "step": step, "node_type": node_type})
            return Response(content=str(response), media_type="application/xml")
        update_phase(PHASE_TTS_READY)
        response.say("Goodbye.", voice=voice)
        response.hangup()
        logger.info("IVR response", extra={**get_trace_context(), "step": step, "fallback": "goodbye"})
        return Response(content=str(response), media_type="application/xml")
    except Exception as e:
        update_phase("error")
        logger.error(f"IVR Error: {e}", extra=get_trace_context())
        response.say("An error occurred.", voice="Polly.Matthew")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")
