"""Compatibility shim — use services.llm instead."""
from services.llm import (
    classify_intent,
    generate_response,
    generate_repair_note,
    analyze_schedule,
)

__all__ = ["classify_intent", "generate_response", "generate_repair_note", "analyze_schedule"]
