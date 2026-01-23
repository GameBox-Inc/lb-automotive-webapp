import requests
import json
import logging

logger = logging.getLogger(__name__)

import functools

import os

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
MODEL = os.getenv("OLLAMA_MODEL", "smollm2:135m")

def generate_response(prompt: str, context: str = "") -> str:
    """
    Generate a response from the local Ollama instance.
    """
    try:
        payload = {
            "model": MODEL,
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
    system_prompt = """
    You are an IVR assistant. Extract INTENT, SERVICE, and TIME.
    
    Examples:
    User: "I need an oil change tomorrow"
    {"intent": "appointment", "service": "oil change", "time": "tomorrow"}
    
    User: "My car won't start, I'm stuck"
    {"intent": "emergency", "service": "car wont start", "time": null}
    
    User: "Habla español?"
    {"intent": "spanish", "service": null, "time": null}
    
    User: "What are your hours?"
    {"intent": "other", "service": null, "time": null}
    """
    
    try:
        payload = {
            "model": MODEL,
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
        logger.error(f"Ollama classification error: {e}. Result was: {result if 'result' in locals() else 'N/A'}")
        return {"intent": "unknown"}

def generate_repair_note(text: str) -> str:
    """
    Format a rough repair note into a professional structured note.
    """
    system_prompt = """
    You are a professional automotive service writer.
    Your task is to rephrase the mechanic's rough notes into a clear, professional repair note.
    Guidelines: Fix grammar, use professional terminology, be concise.
    """
    return generate_response(text, system_prompt)

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
