import json
import os
from typing import List, Dict, Optional, Any

import httpx
import pandas as pd # <-- 1. وارد کردن Pandas

# مسیر فایل اکسل (نسبت به مسیر پروژه)
EXCEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "data", "appointments.xlsx")

# --- توابع ابزار برای اکسل ---

async def query_excel(query: str) -> str:
    """
    خواند داده‌ها از فایل اکسل appointments.xlsx بر اساس یک کوئری متنی.
    خروجی به صورت JSON از ردیف‌های فیلتر شده خواهد بود.
    """
    try:
        print(f"[Excel Query] Looking for file at: {EXCEL_PATH}")
        print(f"[Excel Query] File exists: {os.path.exists(EXCEL_PATH)}")
        print(f"[Excel Query] Query: {query}")
        
        if not os.path.exists(EXCEL_PATH):
            error_msg = f"فایل اکسل در مسیر مشخص شده یافت نشد: {EXCEL_PATH}"
            print(f"[Excel Query] ERROR: {error_msg}")
            return json.dumps({"error": error_msg}, ensure_ascii=False)

        df = pd.read_excel(EXCEL_PATH)
        print(f"[Excel Query] Loaded {len(df)} rows from Excel")
        print(f"[Excel Query] Columns: {list(df.columns)}")
        
        # فیلتر کردن بر اساس query
        filtered_df = df.copy()
        
        query_lower = query.lower()
        
        # فیلتر بر اساس تخصص
        if "اعصاب" in query or "نورولوژی" in query or "neurolog" in query_lower:
            if "specialty" in df.columns:
                filtered_df = df[df["specialty"].str.contains("اعصاب|نورولوژی", case=False, na=False, regex=True)]
                print(f"[Excel Query] Filtered by specialty (اعصاب/نورولوژی)")
        elif "قلب" in query or "cardio" in query_lower:
            if "specialty" in df.columns:
                filtered_df = df[df["specialty"].str.contains("قلب", case=False, na=False, regex=True)]
                print(f"[Excel Query] Filtered by specialty (قلب)")
        elif "داخلی" in query or "internal" in query_lower:
            if "specialty" in df.columns:
                filtered_df = df[df["specialty"].str.contains("داخلی", case=False, na=False, regex=True)]
                print(f"[Excel Query] Filtered by specialty (داخلی)")
        elif "پوست" in query or "dermat" in query_lower:
            if "specialty" in df.columns:
                filtered_df = df[df["specialty"].str.contains("پوست", case=False, na=False, regex=True)]
                print(f"[Excel Query] Filtered by specialty (پوست)")
        
        # اگر فیلتری اعمال نشد، تمام داده‌ها را برمی‌گردانیم
        if len(filtered_df) == len(df):
            print(f"[Excel Query] No specific filter applied, returning all data")
        
        print(f"[Excel Query] Filtered to {len(filtered_df)} rows")
        
        result = filtered_df.to_json(orient="records", force_ascii=False)
        print(f"[Excel Query] Returning {len(result)} characters of JSON")
        return result
    
    except Exception as e:
        error_msg = f"خطا در پردازش اکسل برای کوئری '{query}': {str(e)}"
        print(f"[Excel Query] EXCEPTION: {error_msg}")
        import traceback
        traceback.print_exc()
        return json.dumps({"error": error_msg}, ensure_ascii=False)


async def update_excel(patient: str, doctor: str, date: str, time: str) -> str:
    """
    نوبت را در فایل اکسل appointments.xlsx ثبت می‌کند.
    """
    try:
        if not os.path.exists(EXCEL_PATH):
            return json.dumps({"error": f"فایل اکسل در مسیر مشخص شده یافت نشد: {EXCEL_PATH}"}, ensure_ascii=False)
            
        df = pd.read_excel(EXCEL_PATH)
        
        # منطق رزرو: پیدا کردن ردیف خالی با doctor، date و time مشخص
        # فرض می‌کنیم ستون 'booked_by' وجود دارد و برای ردیف‌های خالی، 'booked_by' مقدار ندارد.
        mask = (df["doctor"] == doctor) & (df["date"] == date) & (df["time"] == time) & (df["booked_by"].isnull())
        
        if any(mask):
            # برای اطمینان از اینکه فقط یک ردیف را آپدیت می‌کنیم، اولین تطابق را می‌گیریم
            idx_to_update = df[mask].index[0]
            df.loc[idx_to_update, "booked_by"] = patient
            
            df.to_excel(EXCEL_PATH, index=False)
            return json.dumps({"status": "success", "message": f"نوبت برای {patient} با دکتر {doctor} در تاریخ {date} ساعت {time} رزرو شد."}, ensure_ascii=False)
        else:
            # بررسی می‌کنیم آیا نوبت اشغال شده است یا اصلا وجود ندارد
            existing_mask = (df["doctor"] == doctor) & (df["date"] == date) & (df["time"] == time)
            if any(existing_mask) and not df.loc[existing_mask, "booked_by"].isnull().all():
                 return json.dumps({"status": "failed", "message": "این نوبت قبلا رزرو شده است."}, ensure_ascii=False)
            else:
                 return json.dumps({"status": "failed", "message": "نوبت با مشخصات درخواستی یافت نشد (دکتر، تاریخ یا زمان اشتباه است)."}, ensure_ascii=False)
            
    except Exception as e:
        return json.dumps({"error": f"خطا در آپدیت اکسل: {str(e)}"}, ensure_ascii=False)


# --- تعریف توابع برای LLM ---
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
    },
    { # <-- 2. اضافه کردن تابع Query
        "type": "function",
        "function": {
            "name": "query_excel",
            "description": "هنگامی که کاربر اطلاعاتی را در مورد داده‌های ثبت شده (مانند لیست قرارها، تخصص‌ها یا تاریخ‌ها) از فایل اکسل می‌خواهد، از این تابع استفاده کن. خروجی این تابع JSON است.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "توصیف متنی دقیق از آنچه باید جستجو شود، برای مثال: 'تمام تخصص ها' یا 'نوبت های دکتر قلب در تاریخ 1403-05-01'."
                    }
                },
                "required": ["query"]
            }
        }
    },
    { # <-- 2. اضافه کردن تابع Update
        "type": "function",
        "function": {
            "name": "update_excel",
            "description": "هنگامی که کاربر می‌خواهد یک نوبت جدید رزرو کند یا داده‌ای را در فایل اکسل تغییر دهد، از این تابع استفاده کن.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient": {"type": "string", "description": "نام بیمار یا فردی که نوبت را رزرو می‌کند."},
                    "doctor": {"type": "string", "description": "نام دکتر مورد نظر."},
                    "date": {"type": "string", "description": "تاریخ نوبت به فرمت YYYY-MM-DD (مثلاً 1403-05-01)."},
                    "time": {"type": "string", "description": "زمان نوبت به فرمت HH:MM (مثلاً 10:00)."}
                },
                "required": ["patient", "doctor", "date", "time"]
            }
        }
    }
]

# --- اجرای توابع ---
async def execute_function(function_name: str, arguments: Dict[str, Any]) -> str:
    """Execute a function call and return the result."""
    if function_name == "get_creator_info":
        return json.dumps({
            "name": "علیرضا علیخانی",
            "phone": "0 910 358 53 87",
            "role": "سازنده و طراح این سیستم"
        }, ensure_ascii=False)
    
    # <-- 4. اجرای توابع جدید
    elif function_name == "query_excel":
        return await query_excel(arguments.get("query", ""))
        
    elif function_name == "update_excel":
        return await update_excel(
            patient=arguments.get("patient", ""),
            doctor=arguments.get("doctor", ""),
            date=arguments.get("date", ""),
            time=arguments.get("time", "")
        )
        
    else:
        return json.dumps({"error": f"Unknown function: {function_name}"}, ensure_ascii=False)

# ... بقیه کلاس OpenRouterLLM و تنظیمات LLM ثابت می‌ماند ...

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
            Dict with 'content' (str) and optionally 'tool_calls' (dict)
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
