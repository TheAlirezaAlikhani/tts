"""
تنظیمات پروژه - انتخاب ماژول فعال
"""
import os
from app.modules.hospital import HospitalModule
from app.modules.hotel import HotelModule
from app.modules.internet_sales import InternetSalesModule
from app.modules.base import BaseModule

# ماژول فعال - می‌تواند از environment variable یا فایل config خوانده شود
# این فقط برای REST API endpoint استفاده می‌شود
ACTIVE_MODULE_NAME = os.getenv("ACTIVE_MODULE", "hospital")  # پیش‌فرض: hospital

# دیکشنری همه ماژول‌های موجود
AVAILABLE_MODULES = {
    "hospital": HospitalModule,
    "hotel": HotelModule,
    "internet_sales": InternetSalesModule,
}

# Token → Module mapping for multi-tenant support
# Format: { "access_token": "module_name" }
# Tokens should be long, unguessable random strings for security
# You can also load this from environment variables or a JSON file
TOKEN_TO_MODULE = {
    # Example tokens - replace with your actual secure tokens
    # You can generate secure tokens using: python -c "import secrets; print(secrets.token_urlsafe(32))"
    os.getenv("HOSPITAL_TOKEN", "hospital_token_abc123xyz"): "hospital",
    os.getenv("HOTEL_TOKEN", "hotel_token_def456uvw"): "hotel",
    os.getenv("INTERNET_SALES_TOKEN", "internet_sales_token_ghi789rst"): "internet_sales",
}


def get_active_module() -> BaseModule:
    """
    دریافت ماژول فعال (برای REST API endpoint)
    
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


def get_module_name_from_token(token: str) -> str:
    """
    دریافت نام ماژول از access token
    
    Args:
        token: Access token از client
        
    Returns:
        نام ماژول (مثلاً 'hospital', 'hotel')
        
    Raises:
        ValueError: اگر token معتبر نباشد
    """
    if not token:
        raise ValueError("Token is required")
    
    module_name = TOKEN_TO_MODULE.get(token)
    if not module_name:
        raise ValueError(f"Invalid token: {token}")
    
    return module_name
