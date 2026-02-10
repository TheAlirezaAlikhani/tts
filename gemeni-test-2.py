"""
## Documentation
Quickstart: https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_LiveAPI.py

## Setup

To install the dependencies for this script, run:

```
pip install google-genai opencv-python pyaudio pillow mss
```
"""

import os
import asyncio
import base64
import io
import json
import traceback

import cv2
import pyaudio
import PIL.Image

import argparse

from google import genai
from google.genai import types
from google.genai.types import Type

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"

DEFAULT_MODE = "none"

client = genai.Client(
    http_options={"api_version": "v1beta"},
    api_key='AIzaSyAci0goLhrBMBV5ox-fkIMM4x6E7JVndLs',
)

tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="test",
                description="A test function that accepts a word parameter and prints a test message.",
                parameters=genai.types.Schema(
                    type = genai.types.Type.OBJECT,
                    required = ["Word"],
                    properties = {
                        "Word": genai.types.Schema(
                            type = genai.types.Type.STRING,
                            description = "A word to test with"
                        ),
                    },
                ),
            ),
        ]
    ),
]

CONFIG = types.LiveConnectConfig(
    response_modalities=[
        "AUDIO",
    ],
    media_resolution="MEDIA_RESOLUTION_MEDIUM",
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
        )
    ),
    context_window_compression=types.ContextWindowCompressionConfig(
        trigger_tokens=25600,
        sliding_window=types.SlidingWindow(target_tokens=12800),
    ),
    tools=tools,
)

pya = pyaudio.PyAudio()


class AudioLoop:
    def __init__(self, video_mode=DEFAULT_MODE):
        self.video_mode = video_mode

        self.audio_in_queue = None
        self.out_queue = None

        self.session = None

        self.send_text_task = None
        self.receive_audio_task = None
        self.play_audio_task = None

        self.audio_stream = None

    async def send_text(self):
        while True:
            text = await asyncio.to_thread(
                input,
                "message > ",
            )
            if text.lower() == "q":
                break
            if self.session is not None:
                await self.session.send_client_content(
                    turns=types.Content(parts=[types.Part(text=text or "")]),
                    turn_complete=True,
                )

    def _get_frame(self, cap):
        # Read the frameq
        ret, frame = cap.read()
        # Check if the frame was read successfully
        if not ret:
            return None
        # Fix: Convert BGR to RGB color space
        # OpenCV captures in BGR but PIL expects RGB format
        # This prevents the blue tint in the video feed
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)  # Now using RGB frame
        img.thumbnail([1024, 1024])

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        mime_type = "image/jpeg"
        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_frames(self):
        # This takes about a second, and will block the whole program
        # causing the audio pipeline to overflow if you don't to_thread it.
        cap = await asyncio.to_thread(
            cv2.VideoCapture, 0
        )  # 0 represents the default camera

        while True:
            frame = await asyncio.to_thread(self._get_frame, cap)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            if self.out_queue is not None:
                await self.out_queue.put(frame)

        # Release the VideoCapture object
        cap.release()

    def _get_screen(self):
        try:
            import mss  # pytype: disable=import-error # pylint: disable=g-import-not-at-top
        except ImportError as e:
            raise ImportError("Please install mss package using 'pip install mss'") from e
        sct = mss.mss()
        monitor = sct.monitors[0]

        i = sct.grab(monitor)

        mime_type = "image/jpeg"
        image_bytes = mss.tools.to_png(i.rgb, i.size)
        img = PIL.Image.open(io.BytesIO(image_bytes))

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_screen(self):

        while True:
            frame = await asyncio.to_thread(self._get_screen)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            if self.out_queue is not None:
                await self.out_queue.put(frame)

    async def send_realtime(self):
        while True:
            if self.out_queue is not None:
                msg = await self.out_queue.get()
                if self.session is not None:
                    if msg["mime_type"].startswith("audio/"):
                        await self.session.send_realtime_input(audio=msg)
                    else:
                        await self.session.send_realtime_input(media=msg)

    async def listen_audio(self):
        mic_info = pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            if self.out_queue is not None:
                await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def handle_function_call(self, function_call):
        """Handle function calls from Gemini"""
        print(f"\n[FUNCTION CALL HANDLER] Processing function call...", flush=True)
        print(f"[FUNCTION CALL HANDLER] Function call type: {type(function_call)}", flush=True)
        print(f"[FUNCTION CALL HANDLER] Function call attributes: {[a for a in dir(function_call) if not a.startswith('_')]}", flush=True)
        
        function_name = None
        arguments = {}
        
        # Extract function name and arguments
        # Handle FunctionCall objects directly (from tool_call.function_calls list)
        if hasattr(function_call, 'name'):
            # Direct function_call structure
            function_name = function_call.name
            print(f"[FUNCTION CALL HANDLER] Found function name via .name: {function_name}", flush=True)
            if hasattr(function_call, 'args'):
                args = function_call.args
                print(f"[FUNCTION CALL HANDLER] Found args via .args: {args}", flush=True)
                if isinstance(args, dict):
                    arguments = args
                elif isinstance(args, str):
                    try:
                        arguments = json.loads(args)
                    except Exception as e:
                        print(f"[FUNCTION CALL HANDLER] Error parsing args as JSON: {e}", flush=True)
                        arguments = {}
        elif hasattr(function_call, 'function'):
            # Nested function structure
            function_name = function_call.function.name
            print(f"[FUNCTION CALL HANDLER] Found function name via .function.name: {function_name}", flush=True)
            if hasattr(function_call.function, 'args'):
                args = function_call.function.args
                print(f"[FUNCTION CALL HANDLER] Found args via .function.args: {args}", flush=True)
                if isinstance(args, dict):
                    arguments = args
                elif isinstance(args, str):
                    try:
                        arguments = json.loads(args)
                    except Exception as e:
                        print(f"[FUNCTION CALL HANDLER] Error parsing args as JSON: {e}", flush=True)
                        arguments = {}
        else:
            print(f"[FUNCTION CALL HANDLER] ❌ Could not extract function name from function_call", flush=True)
            print(f"[FUNCTION CALL HANDLER] Available attributes: {[a for a in dir(function_call) if not a.startswith('_')]}", flush=True)
            return
        
        print(f"[FUNCTION CALL HANDLER] Function name: {function_name}", flush=True)
        print(f"[FUNCTION CALL HANDLER] Arguments: {arguments}", flush=True)
        
        if function_name == "test":
            # Print test string when test function is called
            word = arguments.get("Word", "No word provided")
            print(f"\n" + "="*60, flush=True)
            print(f"[TEST FUNCTION CALLED] ✅ Test function executed!", flush=True)
            print(f"[TEST] Word parameter: '{word}'", flush=True)
            print(f"[TEST] 🎉 This is a test string printed when the test function is called!", flush=True)
            print(f"="*60 + "\n", flush=True)
            
            # Send function result back to Gemini
            result = {
                "status": "success",
                "message": f"Test function executed successfully with word: {word}",
                "word_received": word
            }
            
            try:
                # Extract function call ID (REQUIRED for Live API tool responses)
                # According to Live API docs: https://ai.google.dev/gemini-api/docs/live-tools
                # FunctionResponse MUST include the id from the function call
                function_call_id = getattr(function_call, 'id', None)
                print(f"[TEST] Function call ID: {function_call_id}", flush=True)
                
                if not function_call_id:
                    print(f"[TEST] ⚠️ WARNING: No function call ID found! This may cause errors.", flush=True)
                
                # For Live API, use send_tool_response with function_responses
                # Each FunctionResponse MUST include: id, name, and response
                function_response = types.FunctionResponse(
                    id=function_call_id,  # REQUIRED: ID from the function call
                    name="test",
                    response=result  # result is already a dict
                )
                
                # Use send_tool_response (not send_client_content) for Live API tool responses
                await self.session.send_tool_response(
                    function_responses=[function_response]
                )
                print(f"[TEST] ✅ Function result sent back to Gemini via send_tool_response", flush=True)
            except Exception as e:
                print(f"[TEST] ❌ Error sending function result: {e}", flush=True)
                print(f"[TEST] Error type: {type(e)}", flush=True)
                import traceback
                traceback.print_exc()
            except Exception as e:
                print(f"[TEST] ❌ Error sending function result: {e}", flush=True)
                import traceback
                traceback.print_exc()
        else:
            print(f"\n[FUNCTION CALL] Unknown function: {function_name}", flush=True)
            print(f"[FUNCTION CALL] Arguments received: {arguments}", flush=True)

    async def receive_audio(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        while True:
            if self.session is not None:
                try:
                    turn = self.session.receive()
                    print(f"[RECEIVE] Waiting for turn...", flush=True)
                    async for response in turn:
                        try:
                            # Debug: Check response structure
                            response_has_parts = hasattr(response, 'parts') and response.parts
                            response_has_text = hasattr(response, 'text') and response.text
                            
                            # Only log when there's something interesting (parts, text, or tool_call)
                            if response_has_parts or response_has_text or (hasattr(response, 'tool_call') and response.tool_call):
                                print(f"[RECEIVE] Got response - has_parts: {response_has_parts}, has_text: {response_has_text}, has_tool_call: {hasattr(response, 'tool_call') and response.tool_call}", flush=True)
                            
                            # Check for function calls first (before audio/text)
                            # In Live API, function calls come as 'tool_call' not 'function_call'
                            function_calls = None
                            
                            # PRIMARY: Check for tool_call (Live API uses tool_call)
                            # tool_call is a LiveServerToolCall object with function_calls (plural) attribute
                            if hasattr(response, 'tool_call') and response.tool_call:
                                try:
                                    tool_call = response.tool_call
                                    # tool_call.function_calls is a list of FunctionCall objects
                                    if hasattr(tool_call, 'function_calls') and tool_call.function_calls:
                                        function_calls = tool_call.function_calls
                                        print(f"\n[DEBUG] ✅ Found tool_call on response with {len(function_calls)} function call(s)", flush=True)
                                        for i, fc in enumerate(function_calls):
                                            if hasattr(fc, 'name'):
                                                print(f"[DEBUG] Function call {i}: name={fc.name}, args={getattr(fc, 'args', {})}", flush=True)
                                except Exception as e:
                                    print(f"[DEBUG] Error accessing tool_call: {e}", flush=True)
                                    import traceback
                                    traceback.print_exc()
                            
                            # Fallback: Check response.parts for function_call
                            if not function_calls and response_has_parts:
                                try:
                                    for part in response.parts:
                                        # Check for function_call in part
                                        if hasattr(part, 'function_call') and part.function_call:
                                            if not function_calls:
                                                function_calls = []
                                            function_calls.append(part.function_call)
                                            print(f"\n[DEBUG] ✅ Found function_call in parts: {part.function_call.name}", flush=True)
                                        # Also check for tool_call in parts
                                        if hasattr(part, 'tool_call') and part.tool_call:
                                            if not function_calls:
                                                function_calls = []
                                            function_calls.append(part.tool_call)
                                            print(f"\n[DEBUG] ✅ Found tool_call in parts", flush=True)
                                except Exception as e:
                                    print(f"[DEBUG] Error checking parts: {e}", flush=True)
                                    import traceback
                                    traceback.print_exc()
                            
                            # Fallback: Check if response itself has function_call
                            if not function_calls and hasattr(response, 'function_call') and response.function_call:
                                try:
                                    function_calls = [response.function_call]
                                    print(f"\n[DEBUG] ✅ Found function_call on response: {response.function_call.name}", flush=True)
                                except Exception as e:
                                    print(f"[DEBUG] Error accessing function_call: {e}", flush=True)
                            
                            # Debug: Print response structure if we suspect a function call
                            if response_has_parts or response_has_text:
                                print(f"[DEBUG] Response type: {type(response).__name__}", flush=True)
                                if response_has_parts:
                                    print(f"[DEBUG] Response has {len(response.parts)} parts", flush=True)
                                    for i, part in enumerate(response.parts):
                                        part_attrs = [a for a in dir(part) if not a.startswith('_') and not callable(getattr(part, a, None))]
                                        print(f"[DEBUG] Part {i} type: {type(part).__name__}, attributes: {part_attrs}", flush=True)
                                        # Try to access function_call directly to see what happens
                                        if hasattr(part, 'function_call'):
                                            try:
                                                fc = part.function_call
                                                print(f"[DEBUG] Part {i} function_call value: {fc}", flush=True)
                                                print(f"[DEBUG] Part {i} function_call type: {type(fc)}", flush=True)
                                            except Exception as e:
                                                print(f"[DEBUG] Part {i} Error accessing function_call: {e}", flush=True)
                            
                            # Handle function calls
                            if function_calls:
                                print(f"\n[FUNCTION CALL] ✅ Detected {len(function_calls)} function call(s)", flush=True)
                                for func_call in function_calls:
                                    try:
                                        await self.handle_function_call(func_call)
                                        print(f"[FUNCTION CALL] ✅ Function call handling completed", flush=True)
                                    except Exception as e:
                                        print(f"[FUNCTION CALL] ❌ Error handling function call: {e}", flush=True)
                                        import traceback
                                        traceback.print_exc()
                                # Continue to receive Gemini's follow-up response after function call
                                print(f"[FUNCTION CALL] Waiting for Gemini's follow-up response...", flush=True)
                            else:
                                # Debug: If we have parts but no function calls, log it
                                if response_has_parts:
                                    print(f"[DEBUG] Response has parts but no function_call detected", flush=True)
                            
                            # Handle audio response
                            if data := response.data:
                                self.audio_in_queue.put_nowait(data)
                                continue
                            
                            # Handle text response
                            if text := response.text:
                                print(text, end="", flush=True)
                                
                        except Exception as response_err:
                            print(f"[RECEIVE] ❌ Error processing response: {response_err}", flush=True)
                            import traceback
                            traceback.print_exc()
                            # Continue to next response instead of breaking

                    # If you interrupt the model, it sends a turn_complete.
                    # For interruptions to work, we need to stop playback.
                    # So empty out the audio queue because it may have loaded
                    # much more audio than has played yet.
                    while not self.audio_in_queue.empty():
                        self.audio_in_queue.get_nowait()
                        
                except Exception as turn_err:
                    # Normal disconnect when user closes connection - don't log as error
                    if "disconnect" in str(turn_err).lower() or "closed" in str(turn_err).lower():
                        print(f"[RECEIVE] Connection closed/disconnected", flush=True)
                        break
                    
                    # Check for "Operation is not implemented" error (1008)
                    error_str = str(turn_err).lower()
                    if "operation is not implemented" in error_str or "1008" in error_str:
                        print(f"\n[ERROR] ⚠️ Model does not support function calling (error 1008)", flush=True)
                        print(f"[ERROR] The preview model does not support tools/function calling", flush=True)
                        print(f"[ERROR] Stopping receive loop to prevent infinite errors...", flush=True)
                        break
                    
                    print(f"[RECEIVE] ❌ Error in turn: {turn_err}", flush=True)
                    import traceback
                    traceback.print_exc()
                    # Continue to next turn instead of breaking

    async def play_audio(self):
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            if self.audio_in_queue is not None:
                bytestream = await self.audio_in_queue.get()
                await asyncio.to_thread(stream.write, bytestream)

    async def run(self):
        try:
            async with (
                client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                send_text_task = tg.create_task(self.send_text())
                tg.create_task(self.send_realtime())
                tg.create_task(self.listen_audio())
                if self.video_mode == "camera":
                    tg.create_task(self.get_frames())
                elif self.video_mode == "screen":
                    tg.create_task(self.get_screen())

                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())

                await send_text_task
                raise asyncio.CancelledError("User requested exit")

        except asyncio.CancelledError:
            pass
        except ExceptionGroup as EG:
            if self.audio_stream is not None:
                self.audio_stream.close()
                traceback.print_exception(EG)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        type=str,
        default=DEFAULT_MODE,
        help="pixels to stream from",
        choices=["camera", "screen", "none"],
    )
    args = parser.parse_args()
    main = AudioLoop(video_mode=args.mode)
    asyncio.run(main.run())