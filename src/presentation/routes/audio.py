"""
Audio endpoints - Speech to Text using OpenAI Whisper
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from ...infrastructure.openai.audio_client import AudioClient

router = APIRouter()


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = Form("es")
):
    """
    Transcribe audio to text using OpenAI Whisper API
    
    Args:
        file: Audio file (webm, mp3, wav, etc.)
        language: Language code (es, en, etc.)
    
    Returns:
        {
            "text": "transcribed text",
            "language": "es",
            "duration": 5.2
        }
    """
    try:
        audio_client = AudioClient()
        
        audio_bytes = await file.read()
        
        result = await audio_client.transcribe(
            audio_file=audio_bytes,
            filename=file.filename or "audio.webm",
            language=language
        )
        
        # Return in format expected by frontend
        return {
            "success": True,
            "text": result.get("text", ""),
            "language": result.get("language", language),
            "duration": result.get("duration", 0)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
