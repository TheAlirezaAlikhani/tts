"""
ماژول اپراتور فروش اینترنت
"""
import json
from typing import List, Dict, Any
from app.modules.base import BaseModule


class InternetSalesModule(BaseModule):
    """ماژول فروش و پشتیبانی اینترنت"""
    
    @property
    def name(self) -> str:
        return "internet_sales"
    
    @property
    def description(self) -> str:
        return "اپراتور فروش اینترنت"
    
    @property
    def system_prompt(self) -> str:
        return "شما یک دستیار صوتی فارسی هستید که به عنوان اپراتور فروش و پشتیبانی اینترنت کار می‌کنید. پاسخ‌های خود را کوتاه (حداکثر 2-3 جمله)، فقط به فارسی و بدون ایموجی بنویسید."
    
    @property
    def functions(self) -> List[Dict]:
        """توابع اختصاصی ماژول فروش اینترنت (توابع مشترک به صورت خودکار اضافه می‌شوند)"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "query_packages",
                    "description": "هنگامی که کاربر در مورد پکیج‌های اینترنت، قیمت‌ها یا سرعت می‌پرسد، از این تابع استفاده کن.",
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
            }
        ]
    
    async def execute_function(self, function_name: str, arguments: Dict[str, Any]) -> str:
        """اجرای توابع ماژول فروش اینترنت"""
        # ابتدا چک کردن توابع مشترک (مثل get_creator_info)
        try:
            result = await super().execute_function(function_name, arguments)
            return result
        except NotImplementedError:
            # اگر تابع مشترک نبود، توابع اختصاصی ماژول را چک می‌کنیم
            pass
        
        # توابع اختصاصی ماژول فروش اینترنت
        if function_name == "query_packages":
            # TODO: پیاده‌سازی جستجوی پکیج‌ها
            return json.dumps({"message": "این تابع در حال توسعه است"}, ensure_ascii=False)
        
        else:
            return json.dumps({"error": f"Unknown function: {function_name}"}, ensure_ascii=False)
