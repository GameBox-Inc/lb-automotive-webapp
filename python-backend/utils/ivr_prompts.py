"""
Matrix-driven IVR prompts. Loads prompts from data/ivr_prompts.json so copy can be
edited without code changes. Future: extend with FAQ-style response keys.
"""
import json
from pathlib import Path
from typing import Optional

_IVR_PROMPTS_CACHE: Optional[dict] = None


def _prompts_path() -> Path:
    base = Path(__file__).resolve().parent.parent
    # Prefer config/ (tracked in git); fallback to data/ if present
    for subdir in ("config", "data"):
        p = base / subdir / "ivr_prompts.json"
        if p.exists():
            return p
    return base / "config" / "ivr_prompts.json"


def load_ivr_prompts() -> dict:
    """Load and cache the IVR prompt matrix. Returns empty dict on missing file or parse error."""
    global _IVR_PROMPTS_CACHE
    if _IVR_PROMPTS_CACHE is not None:
        return _IVR_PROMPTS_CACHE
    path = _prompts_path()
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                _IVR_PROMPTS_CACHE = json.load(f)
        else:
            _IVR_PROMPTS_CACHE = {}
    except (json.JSONDecodeError, OSError):
        _IVR_PROMPTS_CACHE = {}
    return _IVR_PROMPTS_CACHE


def get_step_prompt(step: str, language: str) -> Optional[str]:
    """
    Return the prompt text for a decision-tree step from the matrix.
    language: 'en' or 'es'. Returns None if step or lang not in matrix.
    """
    data = load_ivr_prompts()
    steps = data.get("steps") or {}
    node = steps.get(step)
    if not node:
        return None
    key = "prompt_es" if language == "es" else "prompt_en"
    return node.get(key)


def get_response(key: str, language: str, **format_kwargs) -> str:
    """
    Return the response text for a handler from the matrix.
    key: entry in responses (e.g. 'no_slots', 'save_time_confirm').
    language: 'en' or 'es'.
    format_kwargs: optional placeholders for .format() (e.g. time_spoken=..., date_spoken=...).
    Returns the string, or a fallback if key missing.
    """
    data = load_ivr_prompts()
    responses = data.get("responses") or {}
    entry = responses.get(key)
    if not entry:
        return "Please continue." if language != "es" else "Por favor continúe."
    text = entry.get("es" if language == "es" else "en", entry.get("en", "Please continue."))
    if format_kwargs:
        try:
            text = text.format(**format_kwargs)
        except KeyError:
            pass
    return text
