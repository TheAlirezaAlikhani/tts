import json
import os
from typing import List, Dict, Optional, Any

import httpx


# Function definitions for the LLM
FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_creator_info",
            "description": "اگر کاربر درمورد سازنده یا طراح این کار و سیستم پرسید، اطلاعات سازنده را برگردان",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


# Function implementations
async def execute_function(function_name: str, arguments: Dict[str, Any]) -> str:
    """Execute a function call and return the result."""
    if function_name == "get_creator_info":
        # Return structured data that the LLM can use to form a response
        return json.dumps({
            "name": "علیرضا علیخانی",
            "phone": "0 910 358 53 87",
            "role": "سازنده و طراح این سیستم"
        }, ensure_ascii=False)
    else:
        return json.dumps({"error": f"Unknown function: {function_name}"}, ensure_ascii=False)


class OpenRouterLLM:
    def __init__(self, api_key: str, model: str = "stepfun/step-3.5-flash:free"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        reasoning: bool = False,
        tools: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Send messages to OpenRouter API and return the assistant's response.
        Supports function calling.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            reasoning: Whether to enable reasoning mode
            tools: List of function definitions (defaults to FUNCTIONS)
            
        Returns:
            Dict with 'content' (str) and optionally 'function_call' (dict)
        """
        payload = {
            "model": self.model,
            "messages": messages,
        }
        
        if reasoning:
            payload["reasoning"] = {"enabled": True}
        
        # Add function calling support
        if tools is None:
            tools = FUNCTIONS
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"  # Let the model decide when to call functions
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            # Debug: Log the payload (without sensitive data)
            debug_payload = {k: v for k, v in payload.items() if k != 'messages'}
            if 'tools' in payload:
                debug_payload['tools'] = [{"type": t.get("type"), "function": {"name": t.get("function", {}).get("name")}} for t in payload['tools']]
            print(f"[LLM Debug] Sending request with tools: {bool(payload.get('tools'))}")
            
            response = await self.client.post(
                self.api_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            assistant_message = result['choices'][0]['message']
            
            # Debug: Log what we received
            print(f"[LLM Debug] Response keys: {assistant_message.keys()}")
            if 'tool_calls' in assistant_message:
                print(f"[LLM Debug] ✅ Tool calls found: {len(assistant_message['tool_calls'])}")
            else:
                print(f"[LLM Debug] ❌ No tool_calls in response")
            
            # Check for function calls
            if 'tool_calls' in assistant_message and assistant_message['tool_calls']:
                return {
                    'content': assistant_message.get('content', ''),
                    'tool_calls': assistant_message['tool_calls'],
                    'reasoning_details': assistant_message.get('reasoning_details')
                }
            
            # Extract content
            content = assistant_message.get('content', '')
            
            # Preserve reasoning_details if present for next call
            if 'reasoning_details' in assistant_message:
                return {
                    'content': content,
                    'reasoning_details': assistant_message.get('reasoning_details')
                }
            
            return {'content': content}
            
        except httpx.HTTPError as e:
            raise Exception(f"OpenRouter API error: {e}")
        except KeyError as e:
            raise Exception(f"Unexpected API response format: {e}")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Initialize LLM with API key from environment or default
OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    "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"
)

llm = OpenRouterLLM(api_key=OPENROUTER_API_KEY)
