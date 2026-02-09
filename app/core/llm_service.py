import json
import os
import asyncio
from typing import List, Dict, Optional, Any

import httpx


class OpenRouterLLM:
    """
    Core LLM service - فقط ارتباط با API OpenRouter
    بدون هیچ منطق کسب و کاری
    """
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
        ارسال پیام‌ها به OpenRouter API و دریافت پاسخ.
        از function calling پشتیبانی می‌کند.
        """
        payload = {
            "model": self.model,
            "messages": messages,
        }

        if reasoning:
            payload["reasoning"] = {"enabled": True}

        # اضافه کردن function calling
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Retry logic for rate limits
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                print(f"[LLM] Sending request (Attempt {attempt + 1}/{max_retries})")
                
                response = await self.client.post(
                    self.api_url,
                    headers=headers,
                    json=payload
                )
                
                # Handle rate limit (429)
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        retry_after = int(response.headers.get('Retry-After', retry_delay))
                        wait_time = retry_after * (2 ** attempt)
                        print(f"[LLM] Rate limit hit (429). Waiting {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise Exception("Rate limit exceeded. Please wait a moment and try again.")
                
                response.raise_for_status()
                
                # پردازش پاسخ موفق
                result = response.json()
                assistant_message = result['choices'][0]['message']

                # Debug logging
                print(f"[LLM] Response keys: {assistant_message.keys()}")
                if 'tool_calls' in assistant_message:
                    print(f"[LLM] ✅ Tool calls found: {len(assistant_message['tool_calls'])}")
                else:
                    print(f"[LLM] ❌ No tool_calls in response")

                # بررسی function calls
                if 'tool_calls' in assistant_message and assistant_message['tool_calls']:
                    return {
                        'content': assistant_message.get('content', ''),
                        'tool_calls': assistant_message['tool_calls'],
                        'reasoning_details': assistant_message.get('reasoning_details')
                    }

                # استخراج محتوا
                content = assistant_message.get('content', '')

                # حفظ reasoning_details اگر وجود دارد
                if 'reasoning_details' in assistant_message:
                    return {
                        'content': content,
                        'reasoning_details': assistant_message.get('reasoning_details')
                    }

                return {'content': content}
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    retry_after = int(e.response.headers.get('Retry-After', retry_delay))
                    wait_time = retry_after * (2 ** attempt)
                    print(f"[LLM] Rate limit error (429). Waiting {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"OpenRouter API error: {e}")
            except httpx.HTTPError as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"[LLM] HTTP error. Waiting {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"OpenRouter API error: {e}")
            except KeyError as e:
                raise Exception(f"Unexpected API response format: {e}")

    async def close(self):
        """بستن HTTP client."""
        await self.client.aclose()


# Initialize LLM with API key from environment or default
OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    "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"
)

llm = OpenRouterLLM(api_key=OPENROUTER_API_KEY)
