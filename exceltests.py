import pandas as pd
import os

# اطمینان از وجود پوشه data
if not os.path.exists("data"):
    os.makedirs("data")

# تعریف داده‌ها
data = {
    "doctor": ["دکتر احمدی", "دکتر کریمی", "دکتر حسینی", "دکتر احمدی", "دکتر محمدی"],
    "specialty": ["قلب", "اعصاب", "داخلی", "قلب", "پوست"],
    "date": ["1403-05-01", "1403-05-01", "1403-05-02", "1403-05-03", "1403-05-03"],
    "time": ["10:00", "11:00", "14:30", "10:00", "16:00"],
    "booked_by": ["مریم", None, "رضا", "علی", None] # None نشان دهنده نوبت خالی است
}

df = pd.DataFrame(data)

# ذخیره فایل در مسیر مورد نیاز
file_path = "data/appointments.xlsx"
df.to_excel(file_path, index=False)

print(f"فایل شبیه سازی شده در مسیر {file_path} با موفقیت ایجاد شد.")
print("محتوای اولیه فایل:")
print(df.to_string())
