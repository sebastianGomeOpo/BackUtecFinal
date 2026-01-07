"""
TTS endpoints - Text to Speech using OpenAI API
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import aiohttp
from ...config import settings

router = APIRouter()


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "alloy"
    model: Optional[str] = "tts-1"
    speed: Optional[float] = 1.0


@router.post("/text-to-speech")
async def text_to_speech(request: TTSRequest):
    """
    Convert text to speech using OpenAI TTS API
    
    Args:
        text: Text to convert to speech
        voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
        model: TTS model (tts-1, tts-1-hd)
        speed: Speed of speech (0.25 to 4.0)
    
    Returns:
        Audio stream (mp3)
    """
    try:
        url = "https://api.openai.com/v1/audio/speech"
        
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": request.model,
            "input": request.text,
            "voice": request.voice,
            "speed": request.speed
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"OpenAI TTS API error: {error_text}"
                    )
                
                audio_content = await response.read()
                
                return StreamingResponse(
                    iter([audio_content]),
                    media_type="audio/mpeg",
                    headers={
                        "Content-Disposition": "inline; filename=speech.mp3"
                    }
                )
    
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
