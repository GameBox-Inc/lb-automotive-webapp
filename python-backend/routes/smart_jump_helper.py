import logging
import os
from database import get_db_connection, upsert_call_state

logger = logging.getLogger(__name__)

# Use the same base URL logic as twilio_webhook to avoid circular import if possible
WEBHOOK_BASE_URL = os.getenv(
    "TWILIO_WEBHOOK_BASE_URL",
    "https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook"
)

def process_smart_jump(intent, llm_result, CallSid, metadata, response, language):
    """
    Encapsulates the logic for 'Smart Jump' - detecting intent/service and skipping menu steps.
    Returns True if a jump occurred (response modified), False otherwise.
    """
    if intent == "appointment" or intent == "spanish":
        # Check for Spanish intent via LLM
        if intent == "spanish":
            language = "es"
            upsert_call_state(CallSid, "main_menu_es", language)
            response.redirect(f"{WEBHOOK_BASE_URL}?step=main_menu_es")
            return True

        # If entity extraction found a service
        extracted_service = None
        if isinstance(llm_result, dict):
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
                
                # If we also extracted vehicle info, save it
                if llm_result.get("vehicle"):
                    metadata["vehicle_info"] = llm_result.get("vehicle")
                
                # Determine next step: if we have vehicle info, go to plate, else to vehicle
                next_step = "collect_plate" if metadata.get("vehicle_info") else "collect_vehicle"
                
                upsert_call_state(CallSid, next_step, language, metadata)
                response.redirect(f"{WEBHOOK_BASE_URL}?step={next_step}")
                return True

    return False
