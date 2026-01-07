"""
OpenAI Audio Client - Whisper API
Handles audio transcription using Whisper model
"""
import aiohttp
from typing import Dict, Any, Optional
from ...config import settings


class AudioClient:
    """
    HTTP client for OpenAI Whisper API
    Transcribes audio to text
    """
    
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.base_url = "https://api.openai.com/v1"
    
    async def transcribe(
        self,
        audio_file: bytes,
        filename: str = "audio.webm",
        language: str = "es",
        model: str = "whisper-1"
    ) -> Dict[str, Any]:
        """
        Transcribe audio to text using Whisper API
        
        Args:
            audio_file: Audio file bytes
            filename: Name of the audio file (with extension)
            language: Language code (es, en, etc.). Use None for auto-detect
            model: Whisper model to use (whisper-1)
        
        Returns:
            {
                "text": "texto transcrito",
                "language": "es",
                "duration": 5.2
            }
        """
        url = f"{self.base_url}/audio/transcriptions"
        
        # Prepare multipart form data
        form_data = aiohttp.FormData()
        
        # Determine content type based on filename
        content_type = self._get_content_type(filename)
        
        form_data.add_field(
            'file',
            audio_file,
            filename=filename,
            content_type=content_type
        )
        form_data.add_field('model', model)
        
        # Language is optional - if not provided, Whisper auto-detects
        if language:
            form_data.add_field('language', language)
        
        # Response format
        form_data.add_field('response_format', 'verbose_json')
        
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=form_data, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Whisper API error: {response.status} - {error_text}")
                    
                    result = await response.json()
                    
                    return {
                        "text": result.get("text", ""),
                        "language": result.get("language"),
                        "duration": result.get("duration")
                    }
        
        except aiohttp.ClientError as e:
            raise Exception(f"Network error calling Whisper API: {str(e)}")
        except Exception as e:
            raise Exception(f"Error transcribing audio: {str(e)}")
    
    def _get_content_type(self, filename: str) -> str:
        """Get content type based on file extension"""
        extension = filename.lower().split('.')[-1]
        
        content_types = {
            'webm': 'audio/webm',
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'mp4': 'audio/mp4',
            'm4a': 'audio/mp4',
            'ogg': 'audio/ogg',
            'flac': 'audio/flac'
        }
        
        return content_types.get(extension, 'audio/webm')
