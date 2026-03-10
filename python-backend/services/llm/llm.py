"""LLM service — Anthropic Claude for intent classification and response generation."""
import functools
import json
import logging
import os

from utils.reliability import graceful_fallback

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")
LLM_PROVIDER = "anthropic"

anthropic_client = None
if ANTHROPIC_API_KEY:
    try:
        from anthropic import Anthropic
        anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
        logger.info(f"Anthropic Claude API client initialized (using model: {ANTHROPIC_MODEL})")
    except ImportError:
        logger.warning("Anthropic package not installed. Install with: pip install anthropic")
    except Exception as e:
        logger.error(f"Failed to initialize Anthropic client: {e}")


def generate_response(prompt: str, context: str = "", system_prompt: str = None) -> str:
    """Generate a response using the Anthropic Claude API."""
    if anthropic_client:
        return _generate_response_anthropic(prompt, context, system_prompt)
    return "I'm having trouble thinking right now."


@graceful_fallback(fallback_value="I'm having trouble thinking right now.", circuit_name="llm_anthropic")
def _generate_response_anthropic(prompt: str, context: str = "", system_prompt: str = None) -> str:
    """Generate response using Anthropic Claude API."""
    user_message = f"{context}\n\n{prompt}" if context else prompt
    if not system_prompt:
        system_prompt = "Automotive assistant. Be brief."

    message = anthropic_client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    if message.content and len(message.content) > 0:
        return message.content[0].text.strip()
    return "I'm having trouble thinking right now."


@graceful_fallback(fallback_value={"intent": "unknown"}, circuit_name="llm_classifier")
@functools.lru_cache(maxsize=100)
def classify_intent(text: str) -> dict:
    """Classify intent and extract entities."""
    system_prompt = """Extract JSON: {"intent": "appointment"|"status_update"|"representative"|"emergency"|"spanish"|"other"|"unknown", "service": str|null, "time": str|null, "vehicle": str|null, "license_plate": str|null}
Only return JSON."""

    if anthropic_client:
        user_prompt = f"User Input: {text}\n\nReturn ONLY the JSON object, no other text:"
        message = anthropic_client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=200,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        result = message.content[0].text.strip() if message.content else '{"intent": "unknown"}'
    else:
        return {"intent": "unknown"}

    if result.strip().startswith("```"):
        result = result.replace("```json", "").replace("```", "").strip()
    start, end = result.find("{"), result.rfind("}")
    if start != -1 and end != -1:
        result = result[start : end + 1]
    return json.loads(result)


def generate_repair_note(text: str) -> str:
    """Format a rough repair note into a professional structured note."""
    system_prompt = "Professional service writer. Rephrase rough notes. Brief, professional, terminologically correct."
    return generate_response(text, "", system_prompt)


def analyze_schedule(slots: list, date_str: str, service_name: str) -> str:
    """Analyze available slots and generate a natural language summary for IVR."""
    if not slots:
        return "I apologize, but we are fully booked for that day. Please call back to speak with an advisor."

    prompt = f"List times: {', '.join(slots)}. Format: 'We have openings at: [times]'. Group if possible. No advice. Say 'Please say the time you want' at end."
    response = generate_response(prompt, "")

    if "trouble thinking" in response.lower() or len(response) < 20:
        morning_slots = [s for s in slots if int(s.split(":")[0]) < 12]
        afternoon_slots = [s for s in slots if int(s.split(":")[0]) >= 12]
        parts = []
        if morning_slots:
            parts.append(f"We have {len(morning_slots)} morning slots available")
        if afternoon_slots:
            parts.append(f"{len(afternoon_slots)} afternoon slots")
        response = f"{' and '.join(parts)}. For morning, press 1. For afternoon, press 2."

    if "Task:" in response:
        response = response.split("Response:")[-1].strip()
    return response
