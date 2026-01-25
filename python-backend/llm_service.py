import requests
import json
import logging

logger = logging.getLogger(__name__)

import functools

import os

# LLM Provider Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

# Ollama Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "smollm2:135m")

# Anthropic Claude Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

# Initialize Anthropic client if API key is provided
anthropic_client = None
if LLM_PROVIDER == "anthropic" and ANTHROPIC_API_KEY:
    try:
        from anthropic import Anthropic
        anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
        logger.info("Anthropic Claude API client initialized")
    except ImportError:
        logger.warning("Anthropic package not installed. Install with: pip install anthropic")
    except Exception as e:
        logger.error(f"Failed to initialize Anthropic client: {e}")
elif LLM_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
    logger.warning("LLM_PROVIDER is set to 'anthropic' but ANTHROPIC_API_KEY is not set. Falling back to Ollama.")
    LLM_PROVIDER = "ollama"

def generate_response(prompt: str, context: str = "", system_prompt: str = None) -> str:
    """
    Generate a response using the configured LLM provider (Ollama or Anthropic Claude).
    
    Args:
        prompt: User prompt/question
        context: Additional context for the prompt
        system_prompt: System prompt/instructions (for Anthropic)
    
    Returns:
        Generated response text
    """
    if LLM_PROVIDER == "anthropic" and anthropic_client:
        return _generate_response_anthropic(prompt, context, system_prompt)
    else:
        return _generate_response_ollama(prompt, context)


def _generate_response_anthropic(prompt: str, context: str = "", system_prompt: str = None) -> str:
    """Generate response using Anthropic Claude API."""
    try:
        # Combine context and prompt
        user_message = f"{context}\n\n{prompt}" if context else prompt
        
        # Default system prompt if not provided
        if not system_prompt:
            system_prompt = "You are a helpful assistant for an automotive service business."
        
        message = anthropic_client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        
        # Extract text from response
        if message.content and len(message.content) > 0:
            return message.content[0].text.strip()
        return "I'm having trouble thinking right now."
    except Exception as e:
        logger.error(f"Anthropic Claude generation error: {e}")
        # Fallback to Ollama if available
        if OLLAMA_HOST:
            logger.info("Falling back to Ollama")
            return _generate_response_ollama(prompt, context)
        return "I'm having trouble thinking right now."


def _generate_response_ollama(prompt: str, context: str = "") -> str:
    """Generate response using local Ollama instance."""
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": f"{context}\n\nUser: {prompt}\nAssistant:",
            "stream": False
        }
        response = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=10)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        logger.error(f"Ollama generation error: {e}")
        return "I'm having trouble thinking right now."

@functools.lru_cache(maxsize=100)
def classify_intent(text: str) -> dict:
    """
    Use LLM to classify intent and extract entities from text.
    Returns structured JSON: {"intent": "appointment"|"emergency"|"unknown", "service": "...", "time": "..."}
    """
    system_prompt = """You are an IVR assistant. Extract INTENT, SERVICE, and TIME from user input.
    
Return ONLY valid JSON in this exact format:
{"intent": "appointment"|"emergency"|"spanish"|"other"|"unknown", "service": "..."|null, "time": "..."|null}

Examples:
User: "I need an oil change tomorrow"
{"intent": "appointment", "service": "oil change", "time": "tomorrow"}

User: "My car won't start, I'm stuck"
{"intent": "emergency", "service": "car wont start", "time": null}

User: "Habla español?"
{"intent": "spanish", "service": null, "time": null}

User: "What are your hours?"
{"intent": "other", "service": null, "time": null}"""
    
    try:
        if LLM_PROVIDER == "anthropic" and anthropic_client:
            # Use Anthropic Claude for classification
            user_prompt = f"User Input: {text}\n\nReturn ONLY the JSON object, no other text:"
            
            message = anthropic_client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=200,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            result = message.content[0].text.strip() if message.content else ""
        else:
            # Use Ollama for classification
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": f"{system_prompt}\nUser Input: {text}\nJSON:",
                "stream": False,
                "format": "json" 
            }
            response = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=5)
            response.raise_for_status()
            result = response.json().get("response", "")
        
        # Cleanup: Remove markdown code blocks if present
        if result.strip().startswith("```"):
            result = result.replace("```json", "").replace("```", "").strip()
        
        # Cleanup: sometimes models add text before/after
        start = result.find("{")
        end = result.rfind("}")
        if start != -1 and end != -1:
            result = result[start:end+1]
            
        return json.loads(result)
    except Exception as e:
        logger.error(f"LLM classification error ({LLM_PROVIDER}): {e}. Result was: {result if 'result' in locals() else 'N/A'}")
        return {"intent": "unknown"}

def generate_repair_note(text: str) -> str:
    """
    Format a rough repair note into a professional structured note.
    """
    system_prompt = """You are a professional automotive service writer.
    Your task is to rephrase the mechanic's rough notes into a clear, professional repair note.
    Guidelines: Fix grammar, use professional terminology, be concise."""
    return generate_response(text, "", system_prompt)

def analyze_schedule(slots: list, date_str: str, service_name: str) -> str:
    """
    Analyze available slots and generate a natural language summary for IVR.
    Optimized for SmolLM 135M with fallback when LLM unavailable.
    """
    if not slots:
        return f"I apologize, but we are fully booked for that day. Please call back to speak with an advisor."
    
    # Strictly limit to listing times to avoid oversharing/hallucination
    prompt = f"""Task: List these times for a customer.
Slots: {', '.join(slots)}

Instructions:
- Say "We have openings at:" then list the times.
- Group if possible (e.g. "several in the morning").
- DO NOT mention the repair details.
- DO NOT give advice.
- End with "Please say the time you want."

Response:"""

    response = generate_response(prompt, "")
    
    # Check if LLM failed and provide structured fallback
    if "trouble thinking" in response.lower() or len(response) < 20:
        # Generate a simple time listing as fallback
        morning_slots = [s for s in slots if int(s.split(':')[0]) < 12]
        afternoon_slots = [s for s in slots if int(s.split(':')[0]) >= 12]
        
        parts = []
        if morning_slots:
            parts.append(f"We have {len(morning_slots)} morning slots available")
        if afternoon_slots:
            parts.append(f"{len(afternoon_slots)} afternoon slots")
        
        response = f"{' and '.join(parts)}. For morning, press 1. For afternoon, press 2."
    
    # Cleanup if model repeats prompt
    if "Task:" in response:
        response = response.split("Response:")[-1].strip()
        
    return response
