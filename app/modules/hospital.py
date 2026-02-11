"""
ماژول اپراتور رزرو نوبت بیمارستان
"""
import json
import os
import re
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
        
        # State سشن برای مدیریت شماره تلفن در هر اتصال
        # هر اتصال WebSocket یک نمونه جدا از HospitalModule دریافت می‌کند،
        # بنابراین این مقادیر به‌صورت per-connection هستند.
        self.pending_phone: str | None = None
        self.current_phone: str | None = None
        self.phone_confirmed: bool = False

    def _format_mobile_for_speech(self, digits: str) -> str:
        """
        فرمت‌کردن شماره موبایل برای خواندن صوتی
        
        مثال:
            09123456789 -> "0 912 345 67 89"
        اگر الگو مطابق نبود، رقم‌به‌رقم با فاصله برمی‌گردد.
        """
        if len(digits) == 11 and digits.startswith("0"):
            return f"{digits[0]} {digits[1:4]} {digits[4:7]} {digits[7:9]} {digits[9:11]}"
        return " ".join(digits)
    
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
        return """شما یک دستیار صوتی فارسی هستید که به عنوان اپراتور رزرو نوبت بیمارستان کار می‌کنید. 

مهم: شما دسترسی به توابع (functions) دارید که می‌توانید از آن‌ها استفاده کنید:
- برای جستجو در نوبت‌ها (مثلاً "آیا نوبت خالی وجود دارد؟" یا "لیست دکترها را بگو") از تابع query_appointments استفاده کن
- برای رزرو نوبت از تابع book_appointment استفاده کن
 - برای دریافت و ذخیره شماره تلفن کاربر از تابع set_user_phone استفاده کن
 - برای تأیید یا رد شماره تلفن گفته‌شده از تابع confirm_phone استفاده کن

هنگامی که کاربر شماره تلفن خود را برای رزرو اعلام می‌کند:
- ابتدا همیشه تابع set_user_phone را صدا بزن تا شماره نرمال‌سازی و در سیستم ذخیره شود.
- متن برگشتی این تابع (message_for_user) را برای کاربر بخوان و از او بخواه تأیید کند که شماره صحیح است.
- بعد از پاسخ کاربر (بله/خیر)، تابع confirm_phone را با مقدار مناسب صدا بزن.
- تنها در صورتی که شماره تلفن تأیید شده باشد (توسط confirm_phone)، اجازه داری از book_appointment برای ثبت نوبت استفاده کنی.
- اگر شماره اشتباه بود، از کاربر بخواه شماره صحیح را دوباره بگوید و دوباره از set_user_phone استفاده کن.

هنگامی که کاربر در مورد نوبت‌ها، دکترها، یا تاریخ‌ها سوال می‌پرسد، حتماً از توابع استفاده کن و اطلاعات را از سیستم دریافت کن. هرگز نگو که نمی‌توانی این کار را انجام دهی - همیشه از توابع استفاده کن.

پاسخ‌های خود را کوتاه (حداکثر 2-3 جمله)، فقط به فارسی و بدون ایموجی بنویسید."""
    
    @property
    def functions(self) -> List[Dict]:
        """توابع اختصاصی ماژول بیمارستان (توابع مشترک به صورت خودکار اضافه می‌شوند)"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "query_appointments",
                    "description": "این تابع برای جستجو و دریافت اطلاعات نوبت‌ها استفاده می‌شود. همیشه از این تابع استفاده کن وقتی کاربر می‌پرسد: 'آیا نوبت خالی وجود دارد؟'، 'لیست دکترها را بگو'، 'نوبت‌های خالی را نشان بده'، 'چه تخصص‌هایی موجود است؟'، یا هر سوال دیگری در مورد نوبت‌ها، دکترها، یا تاریخ‌ها. هرگز نگو که نمی‌توانی این اطلاعات را بدهی - همیشه از این تابع استفاده کن.",
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
                            "patient": {
                                "type": "string",
                                "description": "نام بیمار یا فردی که نوبت را رزرو می‌کند."
                            },
                            "doctor": {
                                "type": "string",
                                "description": "نام دکتر مورد نظر."
                            },
                            "date": {
                                "type": "string",
                                "description": "تاریخ نوبت به فرمت YYYY-MM-DD (مثلاً 1403-05-01)."
                            },
                            "time": {
                                "type": "string",
                                "description": "زمان نوبت به فرمت HH:MM (مثلاً 10:00)."
                            }
                        },
                        "required": ["patient", "doctor", "date", "time"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "set_user_phone",
                    "description": "این تابع برای دریافت و نرمال‌سازی شماره تلفن کاربر و ذخیره آن برای رزرو نوبت استفاده می‌شود. هر زمان کاربر شماره تلفن خود را گفت و هنوز شماره‌ای تأیید نشده، از این تابع استفاده کن.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "phone": {
                                "type": "string",
                                "description": "شماره تلفنی که کاربر بیان کرده است (ممکن است شامل فاصله یا کاراکترهای غیرعددی باشد)."
                            }
                        },
                        "required": ["phone"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "confirm_phone",
                    "description": "بعد از این‌که شماره تلفن برای کاربر خوانده شد، برای تأیید یا رد شماره از این تابع استفاده کن. اگر کاربر گفت شماره درست است، confirmation را 'yes' قرار بده، و اگر گفت اشتباه است 'no' قرار بده.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "confirmation": {
                                "type": "string",
                                "description": "تأیید کاربر برای شماره تلفن. مقدار می‌تواند 'yes' یا 'no' یا معادل فارسی آن‌ها باشد (مثلاً 'بله'، 'نه')."
                            }
                        },
                        "required": ["confirmation"]
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
        
        elif function_name == "set_user_phone":
            return await self._set_user_phone(
                phone=arguments.get("phone", "")
            )
        
        elif function_name == "confirm_phone":
            return await self._confirm_phone(
                confirmation=arguments.get("confirmation", "")
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
            
            # قبل از رزرو، باید شماره تلفن کاربر تأیید شده باشد
            if not self.phone_confirmed or not self.current_phone:
                return json.dumps(
                    {
                        "status": "phone_not_confirmed",
                        "message": "قبل از رزرو نوبت، باید شماره تلفن شما دریافت و تأیید شود. لطفاً شماره تلفن خود را بگویید.",
                    },
                    ensure_ascii=False,
                )
            
            if not os.path.exists(self.excel_path):
                return json.dumps({"error": f"فایل اکسل یافت نشد: {self.excel_path}"}, ensure_ascii=False)
            
            df = pd.read_excel(self.excel_path)
            
            # تبدیل ستون booked_by به object (string) برای جلوگیری از خطای dtype
            # این کار ضروری است چون pandas ممکن است ستون را به float64 تبدیل کند اگر NaN داشته باشد
            if "booked_by" in df.columns:
                df["booked_by"] = df["booked_by"].astype("object")
            
            # بررسی وجود نوبت خالی
            mask = (df["doctor"] == doctor) & (df["date"] == date) & (df["time"] == time)
            available = df[mask & (df["booked_by"].isna())]
            
            if len(available) > 0:
                # رزرو نوبت
                idx = available.index[0]
                df.at[idx, "booked_by"] = patient
                
                 # در صورت وجود ستون شماره تلفن، آن را نیز ذخیره می‌کنیم
                if "phone" in df.columns and self.current_phone:
                    df.at[idx, "phone"] = self.current_phone
                
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

    async def _set_user_phone(self, phone: str) -> str:
        """دریافت و نرمال‌سازی شماره تلفن کاربر و ذخیره در state سشن"""
        try:
            raw_phone = (phone or "").strip()
            print(f"[Hospital] set_user_phone raw: {raw_phone}")
            
            if not raw_phone:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "شماره تلفن دریافت نشد. لطفاً شماره خود را دوباره و با وضوح بگویید.",
                    },
                    ensure_ascii=False,
                )
            
            # حذف تمام کاراکترهای غیر عددی
            normalized = re.sub(r"\D+", "", raw_phone)
            print(f"[Hospital] set_user_phone normalized: {normalized}")
            
            if len(normalized) < 8:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "شماره تلفن نامعتبر است. لطفاً شماره خود را به‌طور کامل و با دقت بگویید.",
                    },
                    ensure_ascii=False,
                )
            
            # به‌روزرسانی state سشن
            self.pending_phone = normalized
            self.current_phone = None
            self.phone_confirmed = False
            
            # فرمت مناسب برای خواندن صوتی (0 912 345 67 89)
            spoken_phone = self._format_mobile_for_speech(normalized)
            message_for_user = f"شماره شما {spoken_phone} است. آیا درست است؟ لطفاً بگویید بله یا خیر."
            
            return json.dumps(
                {
                    "status": "pending_confirmation",
                    "normalized_phone": normalized,
                    "message_for_user": message_for_user,
                },
                ensure_ascii=False,
            )
        except Exception as e:
            error_msg = f"خطا در پردازش شماره تلفن: {str(e)}"
            print(f"[Hospital] ERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            return json.dumps({"error": error_msg}, ensure_ascii=False)

    async def _confirm_phone(self, confirmation: str) -> str:
        """تأیید یا رد شماره تلفن ذخیره شده در state سشن"""
        try:
            print(f"[Hospital] confirm_phone raw confirmation: {confirmation}")
            
            if not self.pending_phone:
                return json.dumps(
                    {
                        "status": "no_phone",
                        "message": "هنوز شماره تلفنی دریافت نشده است. لطفاً شماره تلفن خود را بگویید.",
                    },
                    ensure_ascii=False,
                )
            
            text = (confirmation or "").strip().lower()
            
            positive_values = {
                "yes",
                "y",
                "true",
                "1",
                "ok",
                "okay",
                "بله",
                "آره",
                "درسته",
                "صحیح است",
            }
            negative_values = {
                "no",
                "n",
                "false",
                "0",
                "نه",
                "خیر",
                "اشتباه",
                "غلط",
            }
            
            if text in positive_values:
                # تأیید شماره
                self.current_phone = self.pending_phone
                self.phone_confirmed = True
                
                message_for_user = (
                    f"خیلی خوب، شماره {self.current_phone} برای شما ثبت و تأیید شد. "
                    f"حالا می‌توانم رزرو نوبت را ادامه دهم."
                )
                
                return json.dumps(
                    {
                        "status": "confirmed",
                        "phone": self.current_phone,
                        "message_for_user": message_for_user,
                    },
                    ensure_ascii=False,
                )
            
            if text in negative_values:
                # رد شماره
                old_phone = self.pending_phone
                self.pending_phone = None
                self.current_phone = None
                self.phone_confirmed = False
                
                message_for_user = (
                    f"شماره {old_phone} تأیید نشد. لطفاً شماره تلفن صحیح خود را دوباره و با دقت بگویید."
                )
                
                return json.dumps(
                    {
                        "status": "rejected",
                        "message_for_user": message_for_user,
                    },
                    ensure_ascii=False,
                )
            
            # پاسخ نامشخص – از کاربر بخواه دوباره واضح بگوید بله یا خیر
            return json.dumps(
                {
                    "status": "unknown",
                    "message_for_user": "لطفاً به‌طور واضح بگویید آیا شماره تلفن خوانده‌شده درست است یا نه. فقط یکی از عبارت‌های بله یا نه را بگویید.",
                },
                ensure_ascii=False,
            )
        except Exception as e:
            error_msg = f"خطا در تأیید شماره تلفن: {str(e)}"
            print(f"[Hospital] ERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            return json.dumps({"error": error_msg}, ensure_ascii=False)
