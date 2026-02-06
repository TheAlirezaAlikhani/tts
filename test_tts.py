import asyncio
from tts import PersianTTS

async def test():
    tts = PersianTTS()
    try:
        audio = await tts.synthesize_to_bytes("سلام تست")
        print(f"Audio generated: {len(audio)} bytes")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
