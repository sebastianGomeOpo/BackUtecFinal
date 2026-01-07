"""
OpenAI HTTP Client - Pure HTTP implementation using httpx
No SDK dependencies, direct API calls
"""
import httpx
import json
from typing import Dict, List, Any, Optional
from ...config import settings


class OpenAIHTTPClient:
    """Pure HTTP client for OpenAI Conversations + Responses API"""
    
    BASE_URL = "https://api.openai.com/v1"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.openai_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def create_conversation(self, metadata: Dict[str, Any] = None) -> Dict:
        """
        Create a new conversation
        POST /v1/conversations
        
        Args:
            metadata: Optional metadata (max 16 key-value pairs)
        
        Returns:
            {"id": "conv_123", "object": "conversation", "created_at": 1741900000, "metadata": {...}}
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/conversations",
                headers=self.headers,
                json={"metadata": metadata or {}},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def get_conversation(self, conversation_id: str) -> Dict:
        """
        Get a conversation by ID
        GET /v1/conversations/{conversation_id}
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/conversations/{conversation_id}",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def delete_conversation(self, conversation_id: str) -> Dict:
        """
        Delete a conversation
        DELETE /v1/conversations/{conversation_id}
        """
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.BASE_URL}/conversations/{conversation_id}",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def list_conversation_items(
        self,
        conversation_id: str,
        limit: int = 20,
        order: str = "desc",
        after: str = None
    ) -> Dict:
        """
        List items in a conversation
        GET /v1/conversations/{conversation_id}/items
        
        Returns:
            {
                "object": "list",
                "data": [...],
                "first_id": "msg_abc",
                "last_id": "msg_xyz",
                "has_more": false
            }
        """
        params = {"limit": limit, "order": order}
        if after:
            params["after"] = after
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/conversations/{conversation_id}/items",
                headers=self.headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def get_conversation_messages(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        """
        Get conversation messages in a simple format for analysis
        
        Returns:
            [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."},
                ...
            ]
        """
        try:
            items = await self.list_conversation_items(conversation_id, limit=limit, order="asc")
            messages = []
            
            for item in items.get("data", []):
                # Extract message content based on item type
                if item.get("type") == "message":
                    role = item.get("role", "unknown")
                    # Extract text content from various possible structures
                    content = ""
                    if "content" in item:
                        if isinstance(item["content"], list):
                            for content_part in item["content"]:
                                if content_part.get("type") == "text":
                                    content += content_part.get("text", "")
                        elif isinstance(item["content"], str):
                            content = item["content"]
                    
                    if content:
                        messages.append({
                            "role": role,
                            "content": content
                        })
            
            return messages
        except Exception as e:
            print(f"Error getting conversation messages: {e}")
            return []
    
    async def add_conversation_items(
        self,
        conversation_id: str,
        items: List[Dict[str, Any]]
    ) -> Dict:
        """
        Add items to a conversation
        POST /v1/conversations/{conversation_id}/items
        
        Args:
            conversation_id: ID of the conversation
            items: List of items to add (up to 20 items)
                   Example: [{"type": "message", "role": "assistant", "content": [...]}]
        
        Returns:
            {"object": "list", "data": [...]}
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/conversations/{conversation_id}/items",
                headers=self.headers,
                json={"items": items},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def create_response(
        self,
        model: str,
        input_data: Any,
        conversation: str = None,
        instructions: str = None,
        tools: List[Dict] = None,
        reasoning: Dict = None,
        text: Dict = None,
        temperature: float = None,
        max_output_tokens: int = None,
        stream: bool = False
    ) -> Dict:
        """
        Create a model response
        POST /v1/responses
        
        Args:
            model: Model ID (e.g., "gpt-5-mini-2025-08-07")
            input_data: Text string or array of messages
            conversation: Conversation ID (OpenAI loads history automatically)
            instructions: System prompt
            tools: Array of tool definitions for function calling
            reasoning: {"effort": "minimal" | "low" | "medium" | "high"}
            text: {"verbosity": "low" | "medium" | "high"}
            temperature: Sampling temperature (0-2)
            max_output_tokens: Max tokens to generate
            stream: Stream response
        
        Returns:
            Response object with output, usage, etc.
        """
        payload = {
            "model": model,
            "input": input_data
        }
        
        if conversation:
            payload["conversation"] = conversation
        
        if instructions:
            payload["instructions"] = instructions
        
        if tools:
            payload["tools"] = tools
        
        if reasoning:
            payload["reasoning"] = reasoning
        
        if text:
            payload["text"] = text
        
        if temperature is not None:
            payload["temperature"] = temperature
        
        if max_output_tokens:
            payload["max_output_tokens"] = max_output_tokens
        
        if stream:
            payload["stream"] = True
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/responses",
                headers=self.headers,
                json=payload,
                timeout=60.0  # Longer timeout for AI responses
            )
            
            # If error, log the response for debugging
            if response.status_code != 200:
                error_detail = response.text
                print(f"❌ OpenAI API Error {response.status_code}: {error_detail}")
            
            response.raise_for_status()
            result = response.json()
            
            # Log response structure if there are tool calls
            if result.get("output"):
                for item in result["output"]:
                    if item.get("type") == "function_call":
                        print(f"📞 Function call detected: {item.get('call_id')} - {item.get('name')}")
            
            return result
    
    async def get_response(self, response_id: str) -> Dict:
        """
        Get a response by ID
        GET /v1/responses/{response_id}
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/responses/{response_id}",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def delete_response(self, response_id: str) -> Dict:
        """
        Delete a response
        DELETE /v1/responses/{response_id}
        """
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.BASE_URL}/responses/{response_id}",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    def extract_output_text(self, response: Dict) -> str:
        """
        Extract text from response output
        
        Args:
            response: Response object from create_response()
        
        Returns:
            Aggregated text from output
        """
        if not response.get("output"):
            return ""
        
        texts = []
        for item in response["output"]:
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        texts.append(content.get("text", ""))
        
        return "\n".join(texts)
    
    def has_tool_calls(self, response: Dict) -> bool:
        """Check if response contains tool calls"""
        if not response.get("output"):
            return False
        
        for item in response["output"]:
            if item.get("type") == "function_call":
                return True
        
        return False
    
    def extract_tool_calls(self, response: Dict) -> List[Dict]:
        """
        Extract tool calls from response
        
        Returns:
            [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "search_products",
                        "arguments": "{\"query\": \"lámpara\"}"
                    }
                }
            ]
        """
        tool_calls = []
        
        if not response.get("output"):
            return tool_calls
        
        for item in response["output"]:
            if item.get("type") == "function_call":
                # OpenAI uses call_id and the function data is at top level
                tool_calls.append({
                    "id": item.get("call_id"),  # Use call_id, not id
                    "type": "function",
                    "function": {
                        "name": item.get("name"),  # Name is at top level
                        "arguments": item.get("arguments")  # Arguments is at top level
                    }
                })
        
        return tool_calls
