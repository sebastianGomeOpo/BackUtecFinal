import asyncio
import httpx
import re

BASE_URL = "http://localhost:8000"

async def chat_interactivo():
    async with httpx.AsyncClient(timeout=120) as client:
        # Iniciar conversacion
        print("Conectando con Taylor...")
        r = await client.post(f"{BASE_URL}/api/agent/start", json={})

        print(f"Status: {r.status_code}")
        data = r.json()
        print(f"Respuesta: {data}")

        if r.status_code != 200:
            print(f"Error del servidor: {data}")
            return

        conv_id = data["conversation_id"]

        print("\n" + "="*50)
        print("Taylor:", data["message"])
        print("="*50)
        print("\n(Escribe 'salir' para terminar)\n")

        while True:
            msg = input("Tu: ").strip()
            if msg.lower() == "salir":
                print("Adios!")
                break
            if not msg:
                continue

            print("Taylor esta escribiendo...")
            r = await client.post(
                f"{BASE_URL}/api/agent/message",
                json={"conversation_id": conv_id, "message": msg}
            )
            data = r.json()

            respuesta = data.get("message", "Error")
            # Quitar HTML para ver mejor en terminal
            respuesta_limpia = re.sub(r'<[^>]+>', ' ', respuesta)
            respuesta_limpia = re.sub(r'\s+', ' ', respuesta_limpia).strip()

            print("\n" + "-"*50)
            print("Taylor:", respuesta_limpia[:1000])
            if len(respuesta_limpia) > 1000:
                print("... [respuesta larga truncada]")
            print("-"*50 + "\n")

if __name__ == "__main__":
    asyncio.run(chat_interactivo())
