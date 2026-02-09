"""
Base module interface - همه ماژول‌ها باید از این کلاس ارث‌بری کنند
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import json


class BaseModule(ABC):
    """
    کلاس پایه برای همه ماژول‌های استفاده
    هر ماژول باید این متدها را پیاده‌سازی کند
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """نام ماژول (مثلاً 'hospital', 'hotel', etc.)"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """توضیحات ماژول"""
        pass
    
    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """پیام سیستم برای LLM"""
        pass
    
    def get_common_functions(self) -> List[Dict]:
        """
        توابع مشترک که در همه ماژول‌ها استفاده می‌شوند
        مثل get_creator_info
        """
        return [
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
    
    @property
    @abstractmethod
    def functions(self) -> List[Dict]:
        """
        لیست توابع اختصاصی این ماژول
        این توابع با توابع مشترک (get_common_functions) ترکیب می‌شوند
        """
        pass
    
    async def execute_function(self, function_name: str, arguments: Dict[str, Any]) -> str:
        """
        اجرای یک تابع از این ماژول
        ابتدا توابع مشترک را چک می‌کند، سپس توابع اختصاصی ماژول
        
        Args:
            function_name: نام تابع
            arguments: آرگومان‌های تابع
            
        Returns:
            نتیجه به صورت JSON string
        """
        # چک کردن توابع مشترک
        if function_name == "get_creator_info":
            return json.dumps({
                "name": "علیرضا علیخانی",
                "phone": "0910 358 53 87",
                "role": "سازنده و طراح این سیستم"
            }, ensure_ascii=False)
        
        # اگر تابع مشترک نبود، باید در ماژول پیاده‌سازی شود
        raise NotImplementedError(
            f"تابع '{function_name}' باید در ماژول {self.__class__.__name__} پیاده‌سازی شود"
        )
    
    def get_excel_path(self) -> Optional[str]:
        """
        مسیر فایل اکسل این ماژول (اختیاری)
        اگر ماژول از اکسل استفاده نمی‌کند، None برگرداند
        
        Returns:
            مسیر فایل اکسل یا None
        """
        return None
    
    async def get_excel_data(self) -> Dict[str, Any]:
        """
        خواندن تمام داده‌های فایل اکسل (اختیاری)
        برای استفاده در REST API
        
        Returns:
            دیکشنری شامل status, count, data
        """
        excel_path = self.get_excel_path()
        if not excel_path:
            return {
                "status": "error",
                "message": "این ماژول از فایل اکسل استفاده نمی‌کند"
            }
        
        try:
            import pandas as pd
            import numpy as np
            import os
            
            if not os.path.exists(excel_path):
                return {
                    "status": "error",
                    "message": f"فایل اکسل یافت نشد: {excel_path}"
                }
            
            df = pd.read_excel(excel_path)
            
            # Replace NaN, inf, and -inf values with None
            df = df.replace([np.nan, np.inf, -np.inf], None)
            
            # Convert DataFrame to dict
            result = df.to_dict(orient="records")
            
            # Clean for JSON serialization
            def clean_for_json(obj):
                if isinstance(obj, dict):
                    return {k: clean_for_json(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_for_json(item) for item in obj]
                elif pd.isna(obj) or (isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj))):
                    return None
                else:
                    return obj
            
            cleaned_result = clean_for_json(result)
            
            return {
                "status": "success",
                "count": len(cleaned_result),
                "data": cleaned_result
            }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"خطا در خواندن فایل اکسل: {str(e)}"
            }
