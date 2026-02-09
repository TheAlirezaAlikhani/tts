"""
ماژول مسئول پذیرش هتل
"""
import json
import os
from typing import List, Dict, Any
import pandas as pd
from app.modules.base import BaseModule


class HotelModule(BaseModule):
    """ماژول مدیریت رزرو هتل"""
    
    def __init__(self):
        self.excel_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "hotel_reservations.xlsx"
        )
    
    def get_excel_path(self):
        """بازگرداندن مسیر فایل اکسل"""
        return self.excel_path
    
    @property
    def name(self) -> str:
        return "hotel"
    
    @property
    def description(self) -> str:
        return "مسئول پذیرش هتل"
    
    @property
    def system_prompt(self) -> str:
        return "شما یک دستیار صوتی فارسی هستید که به عنوان مسئول پذیرش هتل کار می‌کنید. پاسخ‌های خود را کوتاه (حداکثر 2-3 جمله)، فقط به فارسی و بدون ایموجی بنویسید."
    
    @property
    def functions(self) -> List[Dict]:
        """توابع اختصاصی ماژول هتل (توابع مشترک به صورت خودکار اضافه می‌شوند)"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "query_rooms",
                    "description": "هنگامی که کاربر در مورد اتاق‌های خالی، قیمت‌ها یا امکانات می‌پرسد، از این تابع استفاده کن.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "توصیف متنی از آنچه باید جستجو شود."
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "book_room",
                    "description": "هنگامی که کاربر می‌خواهد یک اتاق رزرو کند، از این تابع استفاده کن.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "guest_name": {"type": "string", "description": "نام مهمان."},
                            "room_number": {"type": "string", "description": "شماره اتاق."},
                            "check_in": {"type": "string", "description": "تاریخ ورود به فرمت YYYY-MM-DD."},
                            "check_out": {"type": "string", "description": "تاریخ خروج به فرمت YYYY-MM-DD."}
                        },
                        "required": ["guest_name", "room_number", "check_in", "check_out"]
                    }
                }
            }
        ]
    
    async def execute_function(self, function_name: str, arguments: Dict[str, Any]) -> str:
        """اجرای توابع ماژول هتل"""
        # ابتدا چک کردن توابع مشترک (مثل get_creator_info)
        try:
            result = await super().execute_function(function_name, arguments)
            return result
        except NotImplementedError:
            # اگر تابع مشترک نبود، توابع اختصاصی ماژول را چک می‌کنیم
            pass
        
        # توابع اختصاصی ماژول هتل
        if function_name == "query_rooms":
            # TODO: پیاده‌سازی جستجوی اتاق‌ها
            return json.dumps({"message": "این تابع در حال توسعه است"}, ensure_ascii=False)
        
        elif function_name == "book_room":
            # TODO: پیاده‌سازی رزرو اتاق
            return json.dumps({"message": "این تابع در حال توسعه است"}, ensure_ascii=False)
        
        else:
            return json.dumps({"error": f"Unknown function: {function_name}"}, ensure_ascii=False)
