"""
Public HTTPS GET for Twilio <Play> — no Twilio signature on this URL.

Audio IDs are unguessable UUIDs with short TTL in Redis (or in-process fallback).
"""
import logging

from fastapi import APIRouter
from fastapi.responses import Response

from services.tts.storage import get_audio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/twilio", tags=["twilio"])


@router.get("/tts-audio/{audio_id}")
async def serve_tts_audio(audio_id: str):
    data = get_audio(audio_id)
    if not data:
        return Response(status_code=404)
    return Response(content=data, media_type="audio/mpeg")
