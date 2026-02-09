"""
ماژول اپراتور رزرو نوبت بیمارستان
"""
import json
import os
from typing import List, Dict, Any
import pandas as pd
from app.modules.base import BaseModule


class HospitalModule(BaseModule):
    """ماژول مدیریت نوبت‌های بیمارستان"""
    
    def __init__(self):
        # مسیر فایل اکسل برای این ماژول
        self.excel_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "appointments.xlsx"
        )
    
    def get_excel_path(self):
        """بازگرداندن مسیر فایل اکسل"""
        return self.excel_path
    
    @property
    def name(self) -> str:
        return "hospital"
    
    @property
    def description(self) -> str:
        return "اپراتور رزرو نوبت بیمارستان"
    
    @property
    def system_prompt(self) -> str:
        return "شما یک دستیار صوتی فارسی هستید که به عنوان اپراتور رزرو نوبت بیمارستان کار می‌کنید. پاسخ‌های خود را کوتاه (حداکثر 2-3 جمله)، فقط به فارسی و بدون ایموجی بنویسید."
    
    @property
    def functions(self) -> List[Dict]:
        """توابع اختصاصی ماژول بیمارستان (توابع مشترک به صورت خودکار اضافه می‌شوند)"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "query_appointments",
                    "description": "هنگامی که کاربر اطلاعاتی را در مورد نوبت‌های ثبت شده (مانند لیست نوبت‌ها، تخصص‌ها یا تاریخ‌ها) می‌خواهد، از این تابع استفاده کن.",
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
            {
                "type": "function",
                "function": {
                    "name": "book_appointment",
                    "description": "هنگامی که کاربر می‌خواهد یک نوبت جدید رزرو کند، از این تابع استفاده کن.",
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
    
    async def execute_function(self, function_name: str, arguments: Dict[str, Any]) -> str:
        """اجرای توابع ماژول بیمارستان"""
        # ابتدا چک کردن توابع مشترک (مثل get_creator_info)
        try:
            result = await super().execute_function(function_name, arguments)
            return result
        except NotImplementedError:
            # اگر تابع مشترک نبود، توابع اختصاصی ماژول را چک می‌کنیم
            pass
        
        # توابع اختصاصی ماژول بیمارستان
        if function_name == "query_appointments":
            return await self._query_appointments(arguments.get("query", ""))
        
        elif function_name == "book_appointment":
            return await self._book_appointment(
                patient=arguments.get("patient", ""),
                doctor=arguments.get("doctor", ""),
                date=arguments.get("date", ""),
                time=arguments.get("time", "")
            )
        
        else:
            return json.dumps({"error": f"Unknown function: {function_name}"}, ensure_ascii=False)
    
    async def _query_appointments(self, query: str) -> str:
        """جستجو در نوبت‌ها"""
        try:
            print(f"[Hospital] Query: {query}")
            print(f"[Hospital] Excel path: {self.excel_path}")
            print(f"[Hospital] File exists: {os.path.exists(self.excel_path)}")
            
            if not os.path.exists(self.excel_path):
                return json.dumps({"error": f"فایل اکسل یافت نشد: {self.excel_path}"}, ensure_ascii=False)
            
            df = pd.read_excel(self.excel_path)
            print(f"[Hospital] Loaded {len(df)} rows")
            
            # فیلتر کردن
            filtered_df = df.copy()
            query_lower = query.lower()
            
            if "اعصاب" in query or "نورولوژی" in query:
                if "specialty" in df.columns:
                    filtered_df = df[df["specialty"].str.contains("اعصاب|نورولوژی", case=False, na=False, regex=True)]
            elif "قلب" in query:
                if "specialty" in df.columns:
                    filtered_df = df[df["specialty"].str.contains("قلب", case=False, na=False, regex=True)]
            elif "داخلی" in query:
                if "specialty" in df.columns:
                    filtered_df = df[df["specialty"].str.contains("داخلی", case=False, na=False, regex=True)]
            elif "پوست" in query:
                if "specialty" in df.columns:
                    filtered_df = df[df["specialty"].str.contains("پوست", case=False, na=False, regex=True)]
            
            print(f"[Hospital] Filtered to {len(filtered_df)} rows")
            return filtered_df.to_json(orient="records", force_ascii=False)
        
        except Exception as e:
            error_msg = f"خطا در جستجوی نوبت‌ها: {str(e)}"
            print(f"[Hospital] ERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            return json.dumps({"error": error_msg}, ensure_ascii=False)
    
    async def _book_appointment(self, patient: str, doctor: str, date: str, time: str) -> str:
        """رزرو نوبت"""
        try:
            print(f"[Hospital] Booking: {patient} with {doctor} on {date} at {time}")
            
            if not os.path.exists(self.excel_path):
                return json.dumps({"error": f"فایل اکسل یافت نشد: {self.excel_path}"}, ensure_ascii=False)
            
            df = pd.read_excel(self.excel_path)
            
            # بررسی وجود نوبت خالی
            mask = (df["doctor"] == doctor) & (df["date"] == date) & (df["time"] == time)
            available = df[mask & (df["booked_by"].isna())]
            
            if len(available) > 0:
                # رزرو نوبت
                idx = available.index[0]
                df.at[idx, "booked_by"] = patient
                df.to_excel(self.excel_path, index=False)
                
                return json.dumps({
                    "status": "success",
                    "message": f"نوبت با موفقیت برای {patient} رزرو شد."
                }, ensure_ascii=False)
            else:
                return json.dumps({
                    "status": "failed",
                    "message": "نوبت با مشخصات درخواستی یافت نشد یا قبلاً رزرو شده است."
                }, ensure_ascii=False)
        
        except Exception as e:
            error_msg = f"خطا در رزرو نوبت: {str(e)}"
            print(f"[Hospital] ERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            return json.dumps({"error": error_msg}, ensure_ascii=False)
