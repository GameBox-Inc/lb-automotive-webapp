import json
import base64
import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.llm import generate_response

router = APIRouter(tags=["stream"])
logger = logging.getLogger(__name__)

@router.websocket("/api/twilio/stream")
async def websocket_endpoint(websocket: WebSocket):
    """
    Handle web socket audio stream from Twilio.
    Protocol:
    1. 'connected' event
    2. 'start' event (streamSid)
    3. 'media' events (payload: base64 audio chunks)
    4. 'stop' event
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted")
    
    stream_sid = None
    
    try:
        while True:
            # Receive message from Twilio
            message = await websocket.receive_text()
            data = json.loads(message)
            
            event = data.get("event")
            
            if event == "connected":
                logger.info("Twilio Media Stream Connected")
                
            elif event == "start":
                stream_sid = data.get("start", {}).get("streamSid")
                logger.info(f"Stream started: {stream_sid}")
                
            elif event == "media":
                payload = data.get("media", {}).get("payload")
                chunk = base64.b64decode(payload)
                # TODO: STT Processing here
                # 1. Accumulate chunks (VAD)
                # 2. Transcribe (Whisper)
                # 3. Send text to LLM (generate_response)
                # 4. Synthesize response (TTS)
                # 5. Send Audio back
                pass
                
            elif event == "stop":
                logger.info("Stream stopped")
                break
                
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass
