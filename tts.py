import asyncio
import os
import tempfile

import edge_tts
from playsound import playsound


class PersianTTS:
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.voice = "fa-IR-DilaraNeural"  # Persian female voice
        
    async def synthesize_to_file(self, text: str, filename: str) -> str:
        """
        Generate speech for the given text and save it to the given filename.
        Returns the path to the saved file.
        """
        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(filename)
        return filename

    async def synthesize_to_bytes(self, text: str) -> bytes:
        """
        Generate speech and return the audio as bytes (for sending over WebSocket).
        """
        temp_file = os.path.join(self.temp_dir, "temp_speech_ws.mp3")
        await self.synthesize_to_file(text, temp_file)

        with open(temp_file, "rb") as f:
            data = f.read()

        try:
            os.remove(temp_file)
        except Exception:
            pass

        return data

    async def speak_async(self, text: str) -> None:
        """
        Convert text to speech and play it locally (for direct testing).
        """
        temp_file = os.path.join(self.temp_dir, "temp_speech.mp3")
        await self.synthesize_to_file(text, temp_file)
        playsound(temp_file)
        try:
            os.remove(temp_file)
        except Exception:
            pass

    def speak(self, text: str) -> None:
        """
        Synchronous wrapper for speak_async (CLI/local use).
        """
        asyncio.run(self.speak_async(text))


async def tts_bytes(text: str) -> bytes:
    """
    Convenience function: return TTS audio bytes for the given text.
    """
    engine = PersianTTS()
    return await engine.synthesize_to_bytes(text)


def tts(text: str) -> None:
    """
    Convenience function: speak the given text locally.
    """
    engine = PersianTTS()
    print(text)
    engine.speak(text)


if __name__ == "__main__":
    sample = input("Enter Persian text: ")
    tts(sample)
