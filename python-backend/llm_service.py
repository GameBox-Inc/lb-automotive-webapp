import requests
import json
import logging

logger = logging.getLogger(__name__)

import functools

OLLAMA_HOST = "http://host.docker.internal:11434"
MODEL = "phi3" # Switched to lightweight model

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
    Use LLM to classify intent from text.
    Returns structured JSON: {"intent": "appointment"|"emergency"|"unknown", "entities": {...}}
    """
    system_prompt = """
    You are an intelligent IVR assistant for LB Automotive.
    Analyze the user's input and extract the intent and entities.
    
    Intents:
    - appointment: scheduling a service
    - emergency: urgent car issue (breakdown, flat tire, etc.)
    - other: anything else
    
    Return ONLY JSON format:
    {
      "intent": "string",
      "service": "string (optional)",
      "time": "string (optional)"
    }
    """
    
    try:
        payload = {
            "model": MODEL,
            "prompt": f"{system_prompt}\nUser Input: {text}\nJSON:",
            "stream": False,
            "format": "json" # Force JSON mode if model supports it
        }
        response = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=5)
        response.raise_for_status()
        result = response.json().get("response", "")
        return json.loads(result)
    except Exception as e:
        logger.error(f"Ollama classification error: {e}")
        return {"intent": "unknown"}
