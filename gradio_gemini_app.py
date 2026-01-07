"""
POC 4: Gemini Video Sales Agent with FastRTC + Gradio
Following the official FastRTC example pattern
"""
import asyncio
import base64
import os
import time
from io import BytesIO

import gradio as gr
import numpy as np
import websockets
from fastrtc import (
    AsyncAudioVideoStreamHandler,
    WebRTC,
    get_cloudflare_turn_credentials_async,
    wait_for_item,
)
from google import genai
from PIL import Image

# Import our existing infrastructure
import sys
sys.path.append(os.path.dirname(__file__))

from src.infrastructure.repositories.product_repository import MongoProductRepository
from src.infrastructure.vectorstore.pinecone_store import PineconeStore
from src.infrastructure.agent.function_executor import execute_function
from src.infrastructure.agent.function_definitions import get_all_tools
from src.config import settings


def encode_audio(data: np.ndarray) -> dict:
    """Encode Audio data to send to the server"""
    return {
        "mime_type": "audio/pcm",
        "data": base64.b64encode(data.tobytes()).decode("UTF-8"),
    }


def encode_image(data: np.ndarray) -> dict:
    """Encode image data to send to the server"""
    with BytesIO() as output_bytes:
        pil_image = Image.fromarray(data)
        pil_image.save(output_bytes, "JPEG")
        bytes_data = output_bytes.getvalue()
    base64_str = str(base64.b64encode(bytes_data), "utf-8")
    return {"mime_type": "image/jpeg", "data": base64_str}


class GeminiSalesHandler(AsyncAudioVideoStreamHandler):
    """
    Sales Agent Handler for Gemini with Audio + Video
    Following the FastRTC example pattern
    """
    
    def __init__(self) -> None:
        super().__init__(
            "mono",
            output_sample_rate=24000,
            input_sample_rate=16000,
        )
        self.audio_queue = asyncio.Queue()
        self.video_queue = asyncio.Queue()
        self.session = None
        self.last_frame_time = 0
        self.quit = asyncio.Event()
        
        # Initialize our sales infrastructure
        self.product_repo = MongoProductRepository()
        self.vectorstore = PineconeStore()
        self.tools = get_all_tools()
        
        # System prompt for sales agent
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        return """Eres Taylor, una asistente de ventas experta y amigable, especializada en artículos para el hogar.

**Tu Personalidad:**
- Cálida, profesional y orientada a soluciones
- Proactiva en entender las necesidades del cliente
- Transparente sobre disponibilidad y precios

**Capacidades Visuales (IMPORTANTE):**
- PUEDES VER lo que el cliente te muestra en video
- Utiliza la información visual para entender mejor las necesidades
- Puedes identificar productos, evaluar espacios, sugerir combinaciones

**🏠 CATÁLOGO:**
✅ Vendes artículos para el hogar: sofás, mesas, sábanas, lámparas, alfombras, decoración, cocina
❌ NO vendemos: vehículos, electrónica, ropa, alimentos, juguetes

**🛡️ GUARDRAIL:**
Si preguntan por productos fuera del catálogo o los muestran en video:
"Lo siento, solo vendemos artículos para el hogar. ¿Te gustaría ver nuestros productos? 🏠✨"

**📋 PROCESO:**
1. Entender necesidad (usa video + `search_products`)
2. Presentar opciones (menciona por NOMBRE, no IDs)
3. Verificar stock/precio (`check_stock`, `get_price`)
4. Generar cotización (`generate_quote`)
5. Confirmar pedido (`confirm_order`)

**REGLAS DE ORO:**
- NUNCA inventes precios o stock
- NUNCA menciones IDs técnicos
- Usa `search_products` para buscar
- SIEMPRE verifica stock antes de cotizar
- Comenta lo que ves en video cuando sea relevante
- Sé concisa pero completa en tus respuestas de audio

¿Listo para ayudar al cliente? 🎥"""

    def _convert_tools_to_gemini_format(self):
        """Convert our tools to Gemini function declarations"""
        gemini_tools = []
        for tool in self.tools:
            gemini_tools.append({
                "function_declarations": [{
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }]
            })
        return gemini_tools

    def copy(self) -> "GeminiSalesHandler":
        """Create a copy of this handler"""
        return GeminiSalesHandler()

    async def start_up(self):
        """Initialize Gemini connection"""
        print("🚀 Starting Gemini Sales Agent...")
        
        client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options={"api_version": "v1alpha"}
        )
        
        config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": self.system_prompt,
            "tools": self._convert_tools_to_gemini_format()
        }
        
        async with client.aio.live.connect(
            model="gemini-2.0-flash-exp",
            config=config,
        ) as session:
            self.session = session
            print("✅ Connected to Gemini")
            
            while not self.quit.is_set():
                turn = self.session.receive()
                try:
                    async for response in turn:
                        # Handle audio response
                        if data := response.data:
                            audio = np.frombuffer(data, dtype=np.int16).reshape(1, -1)
                            self.audio_queue.put_nowait(audio)
                        
                        # Handle function calls
                        if hasattr(response, 'function_calls') and response.function_calls:
                            for function_call in response.function_calls:
                                print(f"🔧 Function call: {function_call.name}")
                                await self._handle_function_call(function_call)
                                
                except websockets.exceptions.ConnectionClosedOK:
                    print("📡 Gemini connection closed")
                    break
                except Exception as e:
                    print(f"⚠️ Turn error: {e}")

    async def _handle_function_call(self, function_call):
        """Execute function and send result back to Gemini"""
        try:
            result = await execute_function(
                function_name=function_call.name,
                arguments=function_call.args,
                product_repo=self.product_repo,
                vectorstore=self.vectorstore,
                conversation_id="gemini-session"
            )
            print(f"✅ Function result: {result}")
            
            # Send result back to Gemini
            await self.session.send(function_responses=[{
                "id": function_call.id,
                "name": function_call.name,
                "response": result
            }])
            
        except Exception as e:
            print(f"❌ Function error: {e}")
            error_result = {"success": False, "error": str(e)}
            await self.session.send(function_responses=[{
                "id": function_call.id,
                "name": function_call.name,
                "response": error_result
            }])

    async def video_receive(self, frame: np.ndarray):
        """Receive video frame from client"""
        self.video_queue.put_nowait(frame)
        
        if self.session:
            # Send image every 1 second (throttle to avoid flooding API)
            if time.time() - self.last_frame_time > 1:
                self.last_frame_time = time.time()
                await self.session.send(input=encode_image(frame))
                print(f"📸 Frame sent to Gemini")

    async def video_emit(self):
        """Return video frame to client (echo back)"""
        frame = await wait_for_item(self.video_queue, 0.01)
        if frame is not None:
            return frame
        else:
            # Return blank frame if no frame available
            return np.zeros((100, 100, 3), dtype=np.uint8)

    async def receive(self, frame: tuple[int, np.ndarray]) -> None:
        """Receive audio from client"""
        _, array = frame
        array = array.squeeze()
        audio_message = encode_audio(array)
        
        if self.session:
            await self.session.send(input=audio_message)

    async def emit(self):
        """Send audio to client"""
        array = await wait_for_item(self.audio_queue, 0.01)
        if array is not None:
            return (self.output_sample_rate, array)
        return array

    async def shutdown(self) -> None:
        """Cleanup on shutdown"""
        if self.session:
            self.quit.set()
            await self.session.close()
            self.quit.clear()
        print("🛑 Gemini session ended")


# Build Gradio UI
css = """
#video-source {max-width: 600px !important; max-height: 600px !important;}
"""

with gr.Blocks(css=css) as demo:
    gr.HTML(
        """
    <div style='display: flex; align-items: center; justify-content: center; gap: 20px; padding: 20px;'>
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 12px;">
            <h1 style="color: white; margin: 0;">🎥 Taylor - Asistente de Ventas con Video</h1>
            <p style="color: white; margin: 10px 0 0 0;">Habla y muestra productos en tiempo real - Powered by Gemini 2.0 Flash</p>
        </div>
    </div>
    """
    )
    
    gr.Markdown("""
    ### 🌟 **Características:**
    - 🎤 **Audio en tiempo real** - Habla naturalmente con Taylor
    - 🎥 **Video multimodal** - Muestra productos o espacios
    - 🛍️ **Búsqueda de productos** - Busca en nuestro catálogo
    - 💰 **Cotizaciones instantáneas** - Genera presupuestos al instante
    - 📦 **Gestión de pedidos** - Confirma tu orden
    
    ### 📋 **Instrucciones:**
    1. Click en **"Start"** para activar cámara y micrófono
    2. Habla con Taylor sobre lo que necesitas
    3. Muestra espacios o productos que te gusten
    4. Taylor te ayudará a encontrar lo perfecto para tu hogar
    """)
    
    with gr.Row():
        with gr.Column():
            webrtc = WebRTC(
                label="🎥 Video Chat con Taylor",
                modality="audio-video",
                mode="send-receive",
                elem_id="video-source",
                rtc_configuration=get_cloudflare_turn_credentials_async,
            )

    webrtc.stream(
        GeminiSalesHandler(),
        inputs=[webrtc],
        outputs=[webrtc],
        time_limit=300,  # 5 minutes
        concurrency_limit=2,
    )
    
    gr.Markdown("""
    ---
    ### 💡 **Tips:**
    - Habla claramente y de forma natural
    - Muestra tu espacio para recibir recomendaciones personalizadas
    - Pregunta por precios, stock y disponibilidad
    - Taylor puede generar cotizaciones y confirmar pedidos
    
    ### ⚠️ **Nota:**
    Solo vendemos artículos para el hogar: muebles, textiles, decoración, iluminación y cocina.
    """)


if __name__ == "__main__":
    print("🚀 Launching POC 4: Gemini Video Sales Agent with FastRTC")
    print("📡 Server will start on http://localhost:7860")
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )

