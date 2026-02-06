import json
import os
from typing import List, Dict, Optional

import httpx


class OpenRouterLLM:
    def __init__(self, api_key: str, model: str = "stepfun/step-3.5-flash:free"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        reasoning: bool = False
    ) -> str:
        """
        Send messages to OpenRouter API and return the assistant's response.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            reasoning: Whether to enable reasoning mode
            
        Returns:
            The assistant's response text
        """
        payload = {
            "model": self.model,
            "messages": messages,
        }
        
        if reasoning:
            payload["reasoning"] = {"enabled": True}
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            response = await self.client.post(
                self.api_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            assistant_message = result['choices'][0]['message']
            
            # Extract content
            content = assistant_message.get('content', '')
            
            # Preserve reasoning_details if present for next call
            if 'reasoning_details' in assistant_message:
                return {
                    'content': content,
                    'reasoning_details': assistant_message.get('reasoning_details')
                }
            
            return content
            
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
