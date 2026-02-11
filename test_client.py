import asyncio
import pyaudio
import websockets


CHANNELS = 1
GEMINI_OUTPUT_RATE = 24000  # Gemini Live audio output sample rate
CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16


async def play_audio_stream(audio_queue: asyncio.Queue):
    """
    Continuously play audio from queue using PyAudio stream
    This ensures smooth, uninterrupted playback without skipping words
    """
    p = pyaudio.PyAudio()
    
    # Use a larger buffer for smoother playback
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=GEMINI_OUTPUT_RATE,
        output=True,
        frames_per_buffer=CHUNK_SIZE * 2,  # Larger buffer
    )
    
    try:
        while True:
            # Get audio chunk from queue (wait if needed)
            audio_data = await audio_queue.get()
            
            if audio_data is None:  # Sentinel to stop
                break
            
            # Write audio to stream (blocking write ensures proper timing)
            # This prevents audio from playing too fast
            stream.write(audio_data)
            
    except asyncio.CancelledError:
        pass
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()


async def main():
    uri = "ws://127.0.0.1:8000/audio?token=hospital_token_abc123xyz"
    # uri = "wss://tts.liara.run/audio"
    
    print("=" * 60)
    print("Gemini Live Client - Audio Receiver")
    print("=" * 60)
    print("Server handles microphone and connects to Gemini Live")
    print("This client only receives and plays audio from Gemini")
    print("Press Ctrl+C to exit")
    print()

    # Queue for audio chunks - larger buffer to prevent dropping chunks
    # We wait for space instead of dropping, so no words are skipped
    audio_queue = asyncio.Queue(maxsize=50)  # Larger buffer to prevent word skipping
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to server!")
            print("Server is listening to microphone and streaming to Gemini...")
            print("You will hear Gemini's responses here.\n")
            
            # Start audio playback task
            playback_task = asyncio.create_task(play_audio_stream(audio_queue))
            
            try:
                # Continuously receive audio from server
                while True:
                    try:
                        # Receive audio data from server (Gemini's speech)
                        data = await websocket.recv()
                        
                        if isinstance(data, str):
                            # Text messages from server (debug/info)
                            print(f"📝 {data}")
                        else:
                            # Audio data - add to playback queue
                            # Wait for space instead of dropping chunks (prevents word skipping)
                            await audio_queue.put(data)
                        
                    except websockets.exceptions.ConnectionClosed:
                        print("❌ Connection closed by server")
                        break
                    except Exception as e:
                        print(f"❌ Error receiving message: {e}")
                        import traceback
                        traceback.print_exc()
                        break
            finally:
                # Stop playback
                await audio_queue.put(None)
                await playback_task
                    
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Connection error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
