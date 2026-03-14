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
from utils.ivr_helper import (
    get_random_filler,
    get_redis_result_key,
    clear_ivr_state,
    parse_filler_phrases_setting,
    apply_latency_mask,
    is_actionable_transcript,
    get_first_turn_intent,
    get_closest_slot,
)
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

        # 4. Traefik Gateway API URLRewrite: backend sees /api/twilio/... (no /lb-automotive, internal host).
        #    Use the configured WEBHOOK_BASE_URL + request query so validation matches Twilio console exactly.
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        used_fallback_base = False
        if (
            parsed.path.startswith("/api/twilio")
            and not parsed.path.startswith("/lb-automotive")
            and "twilio.kozytherocket.space" not in parsed.netloc
        ):
            base = (WEBHOOK_BASE_URL or "").rstrip("/") or "https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook"
            url = f"{base}?{parsed.query}" if parsed.query else base
            used_fallback_base = True

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
        
        # Get the signature header and validate
        signature = request.headers.get("X-Twilio-Signature", "")
        logger.info(f"Validating Twilio signature for URL={url}")

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


def ensure_recording_disclaimer_once(response: VoiceResponse, voice: str, language: str, metadata: dict) -> None:
    """
    Play recording disclaimer once per call using settings:
      - ivr_recording_disclaimer_en
      - ivr_recording_disclaimer_es
    """
    try:
        if metadata.get("disclaimer_played"):
            return
        key = "ivr_recording_disclaimer_es" if language == "es" else "ivr_recording_disclaimer_en"
        default_msg = "This call may be recorded for quality and training purposes."
        text = get_setting(key, default_msg) or default_msg
        if text:
            response.say(text, voice=voice)
            metadata["disclaimer_played"] = True
    except Exception as e:
        logger.error(f"Error playing recording disclaimer: {e}")


def smooth_hangup(response: VoiceResponse, voice: str, language: str, message: Optional[str] = None, pause_seconds: int = 2) -> None:
    """
    Say an optional message, pause briefly, then hang up for a smoother end.
    """
    try:
        if message:
            response.say(message, voice=voice)
        # Twilio supports <Pause>; use a short pause before hangup
        response.pause(length=pause_seconds)
    except Exception:
        # Even if pause fails, we still want to hang up cleanly
        pass
    response.hangup()

# --- Decision Tree Structure ---
# Prompts are written to be inquisitive and customer-service focused; future: extend to FAQ-style answers.
DECISION_TREE = {
    "start": {
        "type": "gather",
        "prompt_en": "Hi, thanks for calling L-B Automotive. We’re here to help—would you like to schedule an appointment, get a status update on your vehicle, or speak with someone? Just say what you need.",
        "prompt_es": "Hola, gracias por llamar a L-B Automotive. Estamos para ayudarle. ¿Le gustaría programar una cita, recibir una actualización de su vehículo o hablar con alguien? Diga lo que necesita.",
        "gather_config": {
            "num_digits": 1,
            "timeout": 8,
            "bargein": False,
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
        "prompt_en": "What can we do for you today? Press 1 or say appointment to schedule a visit. For something urgent, press 2 or say emergency.",
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
        "prompt_es": "¿En qué podemos ayudarle? Presione 1 o diga cita para programar. Si es urgente, presione 2 o diga emergencia.",
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
        "prompt_en": "If you’d like, we can note your license plate—just say the number, or press star to skip.",
        "prompt_es": "Si desea, podemos anotar su placa; diga el número o presione asterisco para saltar.",
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
        "prompt_en": "Does that work for you? Press 1 to confirm your appointment, or 9 to choose a different time.",
        "prompt_es": "¿Le queda bien? Presione 1 para confirmar su cita o 9 para elegir otro horario.",
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
        "prompt_en": "In a few words, what are you coming in for? For example, oil change, brakes, or a check engine light. After the beep.",
        "prompt_es": "En pocas palabras, ¿por qué nos visita? Por ejemplo, cambio de aceite, frenos o luz de motor. Después del tono.",
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
        "prompt_en": "Your appointment is all set. Thank you for choosing L-B Automotive—we look forward to seeing you. Goodbye.",
        "prompt_es": "Su cita quedó confirmada. Gracias por elegir L-B Automotive. Lo esperamos. Adiós."
    },

    "transfer_representative": {
        "type": "terminal",
        "prompt_en": "We’re connecting you with a team member now. Thanks for your patience—one moment please.",
        "prompt_es": "Le estamos conectando con un asesor. Gracias por su paciencia. Un momento por favor."
    },

    "check_status": {
        "type": "terminal",
        "prompt_en": "A service advisor will call you back shortly with an update on your vehicle. Is there anything else we can help with? If not, thanks for calling—goodbye.",
        "prompt_es": "Un asesor le llamará pronto con una actualización de su vehículo. ¿Algo más en lo que podamos ayudarle? Si no, gracias por llamar. Adiós."
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
    message = "¿Qué tipo de servicio necesita?" if language == "es" else "What type of service do you need? Choose one of the following."
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

def _format_slot_for_speech(slot_hm: str, language: str) -> str:
    """Format 'HH:MM' as spoken time for confirmation (e.g. '9 in the morning', '3 in the afternoon')."""
    try:
        parts = slot_hm.split(":")
        h, m = int(parts[0], 10), int(parts[1], 10) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return slot_hm
    if language == "es":
        if h < 12:
            return f"{h} de la mañana" if m == 0 else f"{h} y {m} de la mañana"
        return f"{h} de la tarde" if m == 0 else f"{h} y {m} de la tarde"
    if h == 0:
        return "12 in the morning" if m == 0 else f"12 {m} in the morning"
    if h < 12:
        return f"{h} in the morning" if m == 0 else f"{h} {m} in the morning"
    if h == 12:
        return "noon" if m == 0 else f"12 {m} in the afternoon"
    return f"{h} in the afternoon" if m == 0 else f"{h} {m} in the afternoon"


def handle_time_selection(user_input, language, CallSid, metadata, response):
    """Ask what time the customer would like; we recommend closest available when they answer (no slot count)."""
    import json
    from pathlib import Path
    from scheduling.engine import compute_availability

    selected_service = metadata.get("selected_service", {"id": "general", "name": "General Service"})
    voice = "Polly.Lupe" if language == "es" else "Polly.Matthew"

    # Try up to 7 days ahead so we don't say "no openings" when only a few days are closed or missing from config
    available_slots = []
    target_date = None
    for day_offset in range(1, 8):
        candidate = datetime.now() + timedelta(days=day_offset)
        candidate_date_str = candidate.strftime("%Y-%m-%d")
        engine_slots = compute_availability(
            service_id=selected_service.get('id'),
            date=candidate,
            technician_id=None,
            horizon_days=1,
        )
        raw_slots = sorted({s.start.strftime("%H:%M") for s in engine_slots})
        available_slots = [s for s in raw_slots if check_shop_bandwidth(candidate_date_str, s)]
        if available_slots:
            target_date = candidate_date_str
            break

    # #region agent log
    try:
        _log = Path(__file__).resolve().parent.parent.parent.parent / "debug-49c9c0.log"
        with open(_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"sessionId": "49c9c0", "timestamp": int(datetime.now().timestamp() * 1000), "location": "webhook.py:handle_time_selection", "message": "IVR time selection slots", "data": {"service_id": str(selected_service.get("id")), "target_date": target_date, "available_slots_count": len(available_slots) if available_slots else 0, "saying_fully_booked": not available_slots}, "hypothesisId": "H1"}) + "\n")
    except Exception:
        pass
    # #endregion

    if not available_slots or not target_date:
        if language == "es":
            response.say("Lamentamos no tener disponibilidad en los próximos días. Por favor reserve en línea. Gracias y hasta pronto.", voice=voice)
        else:
            response.say("We’re sorry we don’t have any openings in the next few days. We’d love to help—please try booking online, or call back another time. Goodbye.", voice=voice)
        response.hangup()
        return None

    # Match frontend: 30-min increments for tomorrow, hourly for later days
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    is_tomorrow = target_date == tomorrow_str
    display_slots = []
    for t in available_slots:
        parts = t.split(":")
        min_val = int(parts[1], 10) if len(parts) > 1 else 0
        if is_tomorrow:
            if min_val == 0 or min_val == 30:
                display_slots.append(t)
        else:
            if min_val == 0:
                display_slots.append(t)
    if not display_slots:
        display_slots = available_slots

    # Ask what time they’d like instead of stating slot count; we’ll recommend closest when they answer
    if language == "es":
        prompt = "Tenemos disponibilidad ese día. ¿Qué horario le vendría mejor? Puede decir una hora, por ejemplo las 3 o las 10 de la mañana, o decir mañana o tarde. Si prefiere, marque 1 para mañana o 2 para tarde."
    else:
        prompt = "We have openings that day. What time would work best for you? You can say a specific time—like 3 o’clock or 10 in the morning—or just morning or afternoon, and I’ll find the closest opening for you. If you prefer, press 1 for morning or 2 for afternoon."
    response.say(prompt, voice=voice)

    metadata["available_slots"] = display_slots
    metadata["target_date"] = target_date
    upsert_call_state(CallSid, "select_time", language, metadata)

    gather = Gather(num_digits=1, input="speech dtmf", action=f"{WEBHOOK_BASE_URL}?step=save_time_choice", timeout=8, speechTimeout="auto")
    response.append(gather)
    return None

def handle_booking(user_input, language, CallSid, metadata, response):
    """Final booking handler including vehicle details."""
    # Prefer explicitly chosen slot (from "what time" flow); else fall back to morning/afternoon 1/2
    chosen_slot = metadata.get("chosen_slot")
    if not chosen_slot:
        choice = metadata.get("time_slot_choice")
        slots = metadata.get("available_slots", [])
        if choice == "1":
            chosen_slot = next((s for s in slots if int(s.split(':')[0]) < 12), None)
        elif choice == "2":
            chosen_slot = next((s for s in slots if int(s.split(':')[0]) >= 12), None)
        if not chosen_slot and slots:
            chosen_slot = slots[0]
    target_date = metadata.get("target_date")
    svc = metadata.get("selected_service", {})
    
    voice = "Polly.Lupe" if language == "es" else "Polly.Matthew"
    if chosen_slot:
        appt_time = f"{target_date}T{chosen_slot}:00"
        aid = str(uuid.uuid4())
        # Start/end for scheduling engine conflict detection (same slot so duration from service or 60)
        duration_min = int(svc.get("duration") or svc.get("duration_minutes") or 60)
        start_ts = f"{target_date}T{chosen_slot}:00"
        try:
            start_dt = datetime.strptime(start_ts.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
            end_dt = start_dt + timedelta(minutes=duration_min)
            end_ts = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            end_ts = start_ts
        service_id_val = svc.get("id") or None

        # Build comprehensive notes
        notes_parts = []
        if metadata.get("vehicle_info"): notes_parts.append(f"Vehicle: {metadata['vehicle_info']}")
        if metadata.get("license_plate"): notes_parts.append(f"Plate: {metadata['license_plate']}")
        if metadata.get("symptoms"): notes_parts.append(f"Issue: {metadata['symptoms']}")
        final_notes = " | ".join(notes_parts)

        # Use Primary for write; set start_time/end_time/service_id/source so scheduling engine includes this in conflict detection
        with DatabaseContextManager(read_only=False) as conn:
            cursor = conn.cursor()
            cursor.execute(fmt_query("""
                INSERT INTO appointments (id, customer_name, phone_number, appointment_time, service_type, status, notes, start_time, end_time, service_id, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """), (aid, metadata.get("customer_name", "Voice Customer"), metadata.get("from_phone"), appt_time, svc.get("name", "General Service"), "pending", final_notes, start_ts, end_ts, service_id_val, "ivr"))
            conn.commit()
        
        upsert_call_state(CallSid, "completed", language, metadata, aid)
        time_spoken = _format_slot_for_speech(chosen_slot, language)
        if language == "es":
            response.say(f"Su cita quedó confirmada. La esperamos a las {time_spoken}. Gracias por elegir L-B Automotive. Hasta pronto.", voice=voice)
        else:
            response.say(f"Your appointment is confirmed. We’ll see you at {time_spoken}. Thank you for choosing L-B Automotive—we look forward to helping you. Goodbye.", voice=voice)
        response.hangup()
    else:
        if language == "es":
            response.say("Ese horario ya no está disponible. Le pedimos que elija otro. Un momento.", voice=voice)
        else:
            response.say("That time is no longer available. No worries—let’s find another time that works for you.", voice=voice)
        response.redirect(f"{WEBHOOK_BASE_URL}?step=select_time")
    return None

def handle_save_time_choice(user_input, language, CallSid, metadata, response):
    """Resolve preferred time (speech or 1/2) to closest slot, confirm it, then ask for reason for visit."""
    slots = metadata.get("available_slots", [])
    voice = "Polly.Lupe" if language == "es" else "Polly.Matthew"
    if not slots:
        response.say("We couldn’t find that time. Let’s try again." if language != "es" else "No encontramos ese horario. Intentemos de nuevo.", voice=voice)
        return "select_time"

    chosen_slot = get_closest_slot((user_input or "").strip(), slots)
    if not chosen_slot:
        chosen_slot = slots[0]
    metadata["chosen_slot"] = chosen_slot
    metadata["time_slot_choice"] = user_input
    upsert_call_state(CallSid, "save_time_choice", language, metadata)

    # Confirm recommended time in a customer-service way, then lead into describing the visit
    time_spoken = _format_slot_for_speech(chosen_slot, language)
    target_date = metadata.get("target_date", "")
    try:
        from datetime import datetime as dt
        d = dt.strptime(target_date, "%Y-%m-%d")
        date_spoken = d.strftime("%A, %B %d") if language != "es" else d.strftime("%A %d de %B")
    except Exception:
        date_spoken = target_date

    if language == "es":
        response.say(f"Perfecto. Le reservamos a las {time_spoken} el {date_spoken}—es la hora más cercana a lo que pidió. Ahora, en pocas palabras, ¿por qué nos visita? Por ejemplo, cambio de aceite o frenos. Después del tono.", voice=voice)
    else:
        response.say(f"I’d be happy to get you in at {time_spoken} on {date_spoken}—that’s our closest opening to what you asked for. Next, in a few words, what are you coming in for? For example, oil change or brakes. After the beep.", voice=voice)
    return "collect_symptoms"


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
    if language == "es":
        response.say("Entendemos que es urgente. Tenemos lo siguiente disponible:", voice=voice)
    else:
        response.say("We’re here to help. For urgent issues we have the following options:", voice=voice)
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
    if language == "es":
        response.say(f"Servicios en {category.replace('_', ' ')}. Elija uno:", voice=voice)
    else:
        response.say(f"For {category.replace('_', ' ')}, we have these options. Choose one:", voice=voice)
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
    Confidence: Optional[str] = Form(None),
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

        # Play recording disclaimer once per call at entry.
        ensure_recording_disclaimer_once(response, voice, language, metadata)
        
        # Analytic Fix: Ensure call_state exists before track_decision
        if not get_call_state(CallSid):
            upsert_call_state(CallSid, step, language, metadata)
        
        input_data = Digits if Digits else SpeechResult
        if input_data:
            log_ivr_interaction(CallSid, step, input_data)
        intent = None
        llm_result = {}
        masking_enabled = get_setting("ivr_latency_masking_enabled", "true").lower() == "true"

        # Start step: DTMF 1/2/3 -> redirect to transition (no re-gather).
        if step == "start" and Digits and Digits in ("1", "2", "3"):
            transitions = {"1": "collect_vehicle", "2": "emergency_services", "3": "transfer_representative"}
            next_step = transitions.get(Digits, "start")
            upsert_call_state(CallSid, next_step, language, metadata)
            response.redirect(f"{WEBHOOK_BASE_URL}?step={next_step}")
            logger.info(
                "IVR response",
                extra={**get_trace_context(), "step": step, "route": "dtmf", "next_step": next_step},
            )
            return Response(content=str(response), media_type="application/xml")

        # Speech at start: validate, direct-match, or send to LLM.
        go_to_processing = False
        if SpeechResult and step != "processing":
            update_phase(PHASE_STT_STARTED)
            transcript = (SpeechResult or "").strip()
            try:
                confidence = float(Confidence) if Confidence else None
            except (TypeError, ValueError):
                confidence = None

            if step == "start":
                min_confidence = float(get_setting("ivr_min_confidence", "0") or "0")
                # Duplicate guard: same transcript already sent to LLM
                if transcript and transcript == metadata.get("last_sent_to_llm"):
                    logger.info(
                        "IVR start speech",
                        extra={
                            **get_trace_context(),
                            "step": step,
                            "transcript": transcript,
                            "confidence": confidence,
                            "validation_passed": False,
                            "route": "reject",
                            "processing_skipped_reason": "duplicate",
                            "repair_played": metadata.get("start_gather_played", False),
                            "retry_count": (metadata.get("step_repair_count") or {}).get("start", 0),
                        },
                    )
                    go_to_processing = False
                else:
                    direct_intent = get_first_turn_intent(transcript)
                    if direct_intent:
                        llm_result = {"intent": direct_intent}
                        if process_smart_jump(direct_intent, llm_result, CallSid, metadata, response, language):
                            update_phase(PHASE_TTS_READY)
                            logger.info(
                                "IVR start speech",
                                extra={
                                    **get_trace_context(),
                                    "step": step,
                                    "transcript": transcript,
                                    "confidence": confidence,
                                    "route": "direct_match",
                                    "intent": direct_intent,
                                },
                            )
                            return Response(content=str(response), media_type="application/xml")
                        go_to_processing = False
                    elif not is_actionable_transcript(transcript, confidence, min_confidence=min_confidence):
                        logger.info(
                            "IVR start speech",
                            extra={
                                **get_trace_context(),
                                "step": step,
                                "transcript": transcript,
                                "confidence": confidence,
                                "validation_passed": False,
                                "route": "reject",
                                "processing_skipped_reason": "invalid_or_filler",
                                "repair_played": metadata.get("start_gather_played", False),
                                "retry_count": (metadata.get("step_repair_count") or {}).get("start", 0),
                            },
                        )
                        go_to_processing = False
                    else:
                        metadata["last_sent_to_llm"] = transcript
                        go_to_processing = True
                        logger.info(
                            "IVR start speech",
                            extra={
                                **get_trace_context(),
                                "step": step,
                                "transcript": transcript,
                                "confidence": confidence,
                                "validation_passed": True,
                                "route": "llm",
                            },
                        )
            else:
                go_to_processing = True

            if go_to_processing:
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
                if redis_client:
                    redis_client.delete(result_key)
                metadata["wait_count"] = 0
                metadata["last_intent"] = intent
                metadata.pop("last_sent_to_llm", None)
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
                metadata.pop("last_sent_to_llm", None)
                upsert_call_state(CallSid, f"main_menu_{language}", language, metadata)
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
                    # First-turn at start: do not play repair on the very first request (no user input yet).
                    if step == "start" and not metadata.get("start_gather_played"):
                        metadata["start_gather_played"] = True
                        upsert_call_state(CallSid, step, language, metadata)
                        next_s = step
                        logger.info(
                            "IVR response",
                            extra={
                                **get_trace_context(),
                                "step": step,
                                "repair_played": False,
                                "reason": "first_gather",
                            },
                        )
                    else:
                        step_repair = metadata.get("step_repair_count") or {}
                        repair_count = step_repair.get(step, 0) + 1
                        step_repair[step] = repair_count
                        metadata["step_repair_count"] = step_repair
                        upsert_call_state(CallSid, step, language, metadata)
                        max_repairs = int(get_setting("ivr_repair_max_retries", "3"))
                        if repair_count > max_repairs:
                            response.say(
                            "I’m having trouble hearing you. Let me connect you to someone who can help.",
                            voice=voice,
                            )
                            response.redirect(f"{WEBHOOK_BASE_URL}?step=transfer_representative")
                            logger.info(
                                "IVR response",
                                extra={
                                    **get_trace_context(),
                                    "step": step,
                                    "repair": "transfer",
                                    "repair_played": True,
                                    "repair_count": repair_count,
                                },
                            )
                            return Response(content=str(response), media_type="application/xml")
                        if language == "es":
                            response.say("No alcancé a escucharle bien. Intentemos de nuevo.", voice=voice)
                        else:
                            response.say("I didn't quite catch that. No problem, let's try that again.", voice=voice)
                        logger.info(
                            "IVR response",
                            extra={
                                **get_trace_context(),
                                "step": step,
                                "repair_played": True,
                                "repair_count": repair_count,
                            },
                        )
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
                    if step == "start":
                        gather_kw["barge_in"] = get_setting("ivr_start_bargein", "false").lower() == "true"
                    else:
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
                prompt_text = node.get(f"prompt_{language}", node.get("prompt_en"))
                smooth_hangup(response, voice, language, message=prompt_text)
            track_decision(CallSid, step, input_data)
            update_phase(PHASE_TTS_READY)
            logger.info("IVR response", extra={**get_trace_context(), "step": step, "node_type": node_type})
            return Response(content=str(response), media_type="application/xml")
        update_phase(PHASE_TTS_READY)
        smooth_hangup(response, voice, language, message="Goodbye.")
        logger.info("IVR response", extra={**get_trace_context(), "step": step, "fallback": "goodbye"})
        return Response(content=str(response), media_type="application/xml")
    except Exception as e:
        update_phase("error")
        logger.error(f"IVR Error: {e}", extra=get_trace_context())
        smooth_hangup(response, "Polly.Matthew", language, message="An error occurred.")
        return Response(content=str(response), media_type="application/xml")
