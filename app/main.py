from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.speech_service import transcribe_audio
from tts import PersianTTS

app = FastAPI()
connections = []
tts_engine = PersianTTS()


@app.websocket("/audio")
async def audio_stream(websocket: WebSocket):
    await websocket.accept()
    connections.append(websocket)

    try:
        while True:
            try:
                # دریافت داده صوتی از کلاینت
                audio_chunk = await websocket.receive_bytes()

                # تبدیل گفتار به متن
                text = transcribe_audio(audio_chunk)
                await websocket.send_text(text)

                # تبدیل متن به گفتار و ارسال صوت به صورت باینری
                try:
                    tts_audio = await tts_engine.synthesize_to_bytes(text)
                    await websocket.send_bytes(tts_audio)
                except Exception as tts_err:
                    await websocket.send_text(f"خطا در تبدیل متن به گفتار: {tts_err}")

            except Exception as e:
                # جلوگیری از قطع ناگهانی اتصال در صورت خطا
                await websocket.send_text(f"خطا در پردازش صدا: {e}")
    except WebSocketDisconnect:
        connections.remove(websocket)
