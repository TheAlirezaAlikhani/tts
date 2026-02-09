# راهنمای استفاده از سیستم ماژولار

## ساختار پروژه

```
app/
├── core/
│   └── llm_service.py      # هسته LLM (فقط ارتباط با API)
├── modules/
│   ├── base.py            # کلاس پایه برای همه ماژول‌ها
│   ├── hospital.py        # ماژول بیمارستان
│   ├── hotel.py           # ماژول هتل
│   └── internet_sales.py  # ماژول فروش اینترنت
├── config.py              # تنظیمات و انتخاب ماژول فعال
└── main.py                # سرور اصلی
```

## نحوه تغییر ماژول فعال

### روش 1: Environment Variable
```bash
# Windows PowerShell
$env:ACTIVE_MODULE="hotel"
python main.py

# Linux/Mac
export ACTIVE_MODULE=hotel
python main.py
```

### روش 2: تغییر در config.py
```python
ACTIVE_MODULE_NAME = "hotel"  # یا "hospital" یا "internet_sales"
```

## افزودن ماژول جدید

1. فایل جدید در `app/modules/` ایجاد کنید (مثلاً `restaurant.py`)
2. از `BaseModule` ارث‌بری کنید
3. متدهای لازم را پیاده‌سازی کنید:
   - `name`: نام ماژول
   - `description`: توضیحات
   - `system_prompt`: پیام سیستم برای LLM
   - `functions`: لیست توابع
   - `execute_function`: اجرای توابع
4. ماژول را به `app/config.py` اضافه کنید:

```python
from app.modules.restaurant import RestaurantModule

AVAILABLE_MODULES = {
    "hospital": HospitalModule,
    "hotel": HotelModule,
    "internet_sales": InternetSalesModule,
    "restaurant": RestaurantModule,  # اضافه کنید
}
```

## مثال: ماژول رستوران

```python
from app.modules.base import BaseModule

class RestaurantModule(BaseModule):
    @property
    def name(self) -> str:
        return "restaurant"
    
    @property
    def system_prompt(self) -> str:
        return "شما یک دستیار صوتی فارسی هستید که به عنوان مسئول رزرو رستوران کار می‌کنید..."
    
    @property
    def functions(self) -> List[Dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "check_table_availability",
                    "description": "...",
                    "parameters": {...}
                }
            }
        ]
    
    async def execute_function(self, function_name: str, arguments: Dict[str, Any]) -> str:
        if function_name == "check_table_availability":
            # منطق شما
            return json.dumps({...})
```
