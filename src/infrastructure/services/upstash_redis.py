"""
Upstash Redis Service - Volatile Memory Store

Usa Upstash Redis REST API para almacenar estado volátil de sesión:
- Últimos N mensajes de la conversación
- Estado de la sesión (stage, cart, etc.)
- Resúmenes de conversación
- TTL automático para limpieza

Beneficios sobre MongoDB para estado volátil:
- Sub-millisecond latency
- TTL nativo por key
- Operaciones atómicas
- Escalable multi-instancia
"""
import httpx
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from ...config import settings


class UpstashRedis:
    """Cliente para Upstash Redis REST API"""
    
    # TTL defaults (en segundos)
    SESSION_TTL = 3600  # 1 hora para sesión
    MESSAGES_TTL = 1800  # 30 min para mensajes
    SUMMARY_TTL = 7200  # 2 horas para resúmenes
    
    def __init__(self):
        self.base_url = settings.upstash_redis_rest_url
        self.token = settings.upstash_redis_rest_token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self._client = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client
    
    async def _execute(self, *args) -> Any:
        """Ejecuta un comando Redis via REST API"""
        start_time = time.time()
        try:
            # Upstash REST API format: POST with command as array
            url = self.base_url
            response = await self.client.post(
                url,
                headers=self.headers,
                json=list(args)
            )
            response.raise_for_status()
            result = response.json()
            
            elapsed = (time.time() - start_time) * 1000
            print(f"[REDIS] {args[0]} completed in {elapsed:.2f}ms")
            
            return result.get("result")
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            print(f"[REDIS] ERROR {args[0]} after {elapsed:.2f}ms: {e}")
            return None
    
    # ============================================================================
    # SESSION STATE (Hash)
    # ============================================================================
    
    async def set_session(self, conversation_id: str, data: Dict[str, Any], ttl: int = None) -> bool:
        """Guarda estado de sesión como hash"""
        key = f"session:{conversation_id}"
        ttl = ttl or self.SESSION_TTL
        
        # Convertir dict a pares key-value para HSET
        flat_data = {}
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                flat_data[k] = json.dumps(v)
            else:
                flat_data[k] = str(v) if v is not None else ""
        
        # HSET multiple fields
        args = ["HSET", key]
        for k, v in flat_data.items():
            args.extend([k, v])
        
        await self._execute(*args)
        await self._execute("EXPIRE", key, ttl)
        return True
    
    async def get_session(self, conversation_id: str) -> Dict[str, Any]:
        """Recupera estado de sesión"""
        key = f"session:{conversation_id}"
        result = await self._execute("HGETALL", key)
        
        if not result:
            return {}
        
        # Convertir lista plana a dict
        data = {}
        if isinstance(result, list):
            for i in range(0, len(result), 2):
                k = result[i]
                v = result[i + 1]
                # Intentar parsear JSON
                try:
                    data[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    data[k] = v
        
        return data
    
    async def update_session_field(self, conversation_id: str, field: str, value: Any) -> bool:
        """Actualiza un campo específico de la sesión"""
        key = f"session:{conversation_id}"
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        await self._execute("HSET", key, field, str(value))
        return True
    
    # ============================================================================
    # MESSAGES (List - últimos N mensajes)
    # ============================================================================
    
    async def push_message(self, conversation_id: str, message: Dict[str, Any], max_messages: int = 20) -> int:
        """Agrega mensaje a la lista y mantiene solo los últimos N"""
        key = f"messages:{conversation_id}"
        message_json = json.dumps(message)
        
        # RPUSH + LTRIM para mantener solo últimos N
        await self._execute("RPUSH", key, message_json)
        await self._execute("LTRIM", key, -max_messages, -1)
        await self._execute("EXPIRE", key, self.MESSAGES_TTL)
        
        # Retornar cantidad actual
        count = await self._execute("LLEN", key)
        return count or 0
    
    async def get_messages(self, conversation_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Recupera los últimos N mensajes"""
        key = f"messages:{conversation_id}"
        result = await self._execute("LRANGE", key, -limit, -1)
        
        if not result:
            return []
        
        messages = []
        for msg_json in result:
            try:
                messages.append(json.loads(msg_json))
            except (json.JSONDecodeError, TypeError):
                pass
        
        return messages
    
    async def get_message_count(self, conversation_id: str) -> int:
        """Retorna cantidad de mensajes almacenados"""
        key = f"messages:{conversation_id}"
        count = await self._execute("LLEN", key)
        return count or 0
    
    # ============================================================================
    # MEMORY STATE (Resúmenes)
    # ============================================================================
    
    async def set_memory(self, conversation_id: str, memory_data: Dict[str, Any]) -> bool:
        """Guarda estado de memoria (resumen, contador, etc.)"""
        key = f"memory:{conversation_id}"
        
        data = {
            "summary": memory_data.get("summary", ""),
            "messages_since_summary": str(memory_data.get("messages_since_summary", 0)),
            "total_messages": str(memory_data.get("total_messages", 0)),
            "summary_count": str(memory_data.get("summary_count", 0)),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        args = ["HSET", key]
        for k, v in data.items():
            args.extend([k, v])
        
        await self._execute(*args)
        await self._execute("EXPIRE", key, self.SUMMARY_TTL)
        return True
    
    async def get_memory(self, conversation_id: str) -> Dict[str, Any]:
        """Recupera estado de memoria"""
        key = f"memory:{conversation_id}"
        result = await self._execute("HGETALL", key)
        
        if not result:
            return {
                "summary": "",
                "messages_since_summary": 0,
                "total_messages": 0,
                "summary_count": 0
            }
        
        # Convertir lista plana a dict
        data = {}
        if isinstance(result, list):
            for i in range(0, len(result), 2):
                k = result[i]
                v = result[i + 1]
                data[k] = v
        
        # Convertir tipos
        return {
            "summary": data.get("summary", ""),
            "messages_since_summary": int(data.get("messages_since_summary", 0)),
            "total_messages": int(data.get("total_messages", 0)),
            "summary_count": int(data.get("summary_count", 0)),
            "updated_at": data.get("updated_at", "")
        }
    
    # ============================================================================
    # CART STATE (para operaciones atómicas)
    # ============================================================================
    
    async def set_cart(self, conversation_id: str, cart_items: List[Dict]) -> bool:
        """Guarda estado del carrito"""
        key = f"cart:{conversation_id}"
        await self._execute("SET", key, json.dumps(cart_items), "EX", self.SESSION_TTL)
        return True
    
    async def get_cart(self, conversation_id: str) -> List[Dict]:
        """Recupera estado del carrito"""
        key = f"cart:{conversation_id}"
        result = await self._execute("GET", key)
        
        if not result:
            return []
        
        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return []
    
    # ============================================================================
    # DISTRIBUTED LOCKS (para evitar operaciones duplicadas)
    # ============================================================================
    
    async def acquire_lock(self, lock_name: str, ttl: int = 10) -> bool:
        """Intenta adquirir un lock distribuido"""
        key = f"lock:{lock_name}"
        # SET NX (solo si no existe) con TTL
        result = await self._execute("SET", key, "1", "NX", "EX", ttl)
        return result == "OK"
    
    async def release_lock(self, lock_name: str) -> bool:
        """Libera un lock"""
        key = f"lock:{lock_name}"
        await self._execute("DEL", key)
        return True
    
    # ============================================================================
    # IDEMPOTENCY (para evitar procesamiento duplicado)
    # ============================================================================
    
    async def check_idempotency(self, conversation_id: str, event_id: str, ttl: int = 300) -> bool:
        """Verifica si un evento ya fue procesado. Retorna True si es nuevo."""
        key = f"idemp:{conversation_id}:{event_id}"
        result = await self._execute("SET", key, "1", "NX", "EX", ttl)
        return result == "OK"
    
    # ============================================================================
    # PRODUCT MAPPING (for budget proposals)
    # ============================================================================
    
    async def set_product_mapping(self, conversation_id: str, mapping: Dict[str, Any]) -> bool:
        """Guarda el mapeo de productos de una propuesta de presupuesto"""
        key = f"products:{conversation_id}"
        await self._execute("SET", key, json.dumps(mapping), "EX", self.SESSION_TTL)
        return True
    
    async def get_product_mapping(self, conversation_id: str) -> Dict[str, Any]:
        """Recupera el mapeo de productos"""
        key = f"products:{conversation_id}"
        result = await self._execute("GET", key)
        
        if not result:
            return {}
        
        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    # ============================================================================
    # UTILITY
    # ============================================================================
    
    async def delete_session(self, conversation_id: str) -> bool:
        """Elimina toda la data de una sesión"""
        keys = [
            f"session:{conversation_id}",
            f"messages:{conversation_id}",
            f"memory:{conversation_id}",
            f"cart:{conversation_id}"
        ]
        for key in keys:
            await self._execute("DEL", key)
        return True
    
    async def ping(self) -> bool:
        """Verifica conexión a Redis"""
        result = await self._execute("PING")
        return result == "PONG"


# Singleton instance
_redis_instance: Optional[UpstashRedis] = None


def get_redis() -> UpstashRedis:
    """Get Redis singleton instance"""
    global _redis_instance
    if _redis_instance is None:
        _redis_instance = UpstashRedis()
    return _redis_instance
