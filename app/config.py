"""
تنظیمات پروژه - انتخاب ماژول فعال
"""
import os
from app.modules.hospital import HospitalModule
from app.modules.hotel import HotelModule
from app.modules.internet_sales import InternetSalesModule
from app.modules.base import BaseModule

# ماژول فعال - می‌تواند از environment variable یا فایل config خوانده شود
ACTIVE_MODULE_NAME = os.getenv("ACTIVE_MODULE", "hospital")  # پیش‌فرض: hospital

# دیکشنری همه ماژول‌های موجود
AVAILABLE_MODULES = {
    "hospital": HospitalModule,
    "hotel": HotelModule,
    "internet_sales": InternetSalesModule,
}


def get_active_module() -> BaseModule:
    """
    دریافت ماژول فعال
    
    Returns:
        نمونه ماژول فعال
    """
    if ACTIVE_MODULE_NAME not in AVAILABLE_MODULES:
        print(f"⚠️  Warning: Module '{ACTIVE_MODULE_NAME}' not found. Using 'hospital' as default.")
        return HospitalModule()
    
    module_class = AVAILABLE_MODULES[ACTIVE_MODULE_NAME]
    module = module_class()
    print(f"✅ Active module: {module.name} - {module.description}")
    return module
