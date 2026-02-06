import asyncio
import os
import tempfile
from io import BytesIO

import pyaudio
import wave
import websockets
from playsound import playsound


CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 5  # length of recording from mic


def record_to_wav_bytes() -> bytes:
    """Record audio from the default microphone and return it as WAV bytes."""
    p = pyaudio.PyAudio()

    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    print(f"Recording for {RECORD_SECONDS} seconds... Speak now.")
    frames = []

    for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)

    print("Recording finished.")

    stream.stop_stream()
    stream.close()
    p.terminate()

    # Save to an in-memory WAV
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))

    return buffer.getvalue()


async def main():
    uri = "ws://127.0.0.1:8000/audio"
    async with websockets.connect(uri) as websocket:
        audio_bytes = record_to_wav_bytes()

        await websocket.send(audio_bytes)
        print("Audio sent, waiting for transcription...")

        # 1) Receive transcription text
        text_response = await websocket.recv()
        print("Transcription:", text_response)

        # 2) Receive TTS audio bytes and play them
        print("Waiting for TTS audio...")
        audio_data = await websocket.recv()

        if isinstance(audio_data, str):
            # Server might send an error as text instead of audio bytes
            print("Server TTS message:", audio_data)
        else:
            temp_file = os.path.join(tempfile.gettempdir(), "ws_tts_reply.mp3")
            with open(temp_file, "wb") as f:
                f.write(audio_data)

            print("Playing TTS audio...")
            playsound(temp_file)

            try:
                os.remove(temp_file)
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())