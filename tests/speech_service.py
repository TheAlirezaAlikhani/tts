import speech_recognition as sr
from io import BytesIO


def transcribe_audio(audio_bytes: bytes):
    r = sr.Recognizer()

    # تبدیل bytes به منبع قابل خواندن توسط speech_recognition
    audio_data = BytesIO(audio_bytes)

    # مستقیماً از BytesIO به عنوان AudioFile استفاده می‌کنیم
    with sr.AudioFile(audio_data) as source:
        audio_content = r.record(source)

    try:
        text = r.recognize_google(audio_content, language="fa-IR")  # انتخاب زبان فارسی یا انگلیسی
        return text
    except sr.UnknownValueError:
        return "صدای نامفهوم بود"
    except sr.RequestError as e:
        return f"خطای ارتباط با سرویس گوگل: {e}"