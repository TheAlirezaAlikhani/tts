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
    # uri = "ws://127.0.0.1:8000/audio"
    uri = "wss://tts.liara.run/audio"
    
    print("=" * 60)
    print("Voice Chatbot - Continuous Conversation Mode")
    print("=" * 60)
    print("Press Ctrl+C to exit")
    print()
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to server. You can start speaking!")
            print()
            
            conversation_count = 0
            
            while True:
                try:
                    conversation_count += 1
                    print(f"\n--- Conversation {conversation_count} ---")
                    print("Recording... Speak now.")
                    
                    # Record audio
                    audio_bytes = record_to_wav_bytes()
                    print("Recording finished. Sending to server...")

                    # Send audio to server
                    await websocket.send(audio_bytes)

                    # Server sends: 1) Transcription, 2) LLM response, 3) TTS audio
                    messages_received = 0
                    tts_audio = None
                    
                    while messages_received < 3:
                        try:
                            data = await websocket.recv()
                            messages_received += 1
                            
                            if isinstance(data, str):
                                print(f"📝 {data}")
                            else:
                                # This should be the TTS audio (bytes)
                                tts_audio = data
                                print(f"🔊 Received TTS audio ({len(tts_audio)} bytes)")
                                break  # Got the audio, we're done
                                
                        except websockets.exceptions.ConnectionClosed:
                            print("❌ Connection closed by server")
                            return
                        except Exception as e:
                            print(f"❌ Error receiving message: {e}")
                            break

                    # Play TTS audio if we received it
                    if tts_audio:
                        temp_file = os.path.join(tempfile.gettempdir(), f"ws_tts_reply_{conversation_count}.mp3")
                        with open(temp_file, "wb") as f:
                            f.write(tts_audio)

                        print("🔊 Playing response...")
                        playsound(temp_file)

                        try:
                            os.remove(temp_file)
                        except Exception:
                            pass
                    
                    print("\nReady for next message...")
                    
                except KeyboardInterrupt:
                    print("\n\n👋 Exiting...")
                    break
                except Exception as e:
                    print(f"❌ Error in conversation: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue to next iteration
                    continue
                    
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Connection error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
