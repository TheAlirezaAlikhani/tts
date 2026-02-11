import re
import json
import asyncio
import pyaudio
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from app.config import get_active_module, get_module_name_from_token
from app.modules.registry import get_module_by_name
from app.core.gemini_live_service import GeminiLiveService, GeminiLiveSession

# Handle Python < 3.11 compatibility for ExceptionGroup
try:
    from exceptiongroup import BaseExceptionGroup
except ImportError:
    try:
        BaseExceptionGroup = __builtins__.get('BaseExceptionGroup', Exception)
    except:
        BaseExceptionGroup = Exception

# Audio Configuration for server-side microphone
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
CHUNK_SIZE = 1024

app = FastAPI()
connections = []

# بارگذاری ماژول فعال
active_module = get_active_module()

# Initialize Gemini Live service
gemini_service = GeminiLiveService()

# Initialize PyAudio
pya = pyaudio.PyAudio()

# Store Gemini Live sessions per WebSocket connection
gemini_sessions: dict = {}


@app.get("/data")
async def get_excel_data():
    """
    REST API endpoint برای دریافت تمام داده‌های فایل اکسل ماژول فعال
    برای استفاده در اپلیکیشن‌های frontend
    """
    try:
        result = await active_module.get_excel_data()
        
        if result.get("status") == "error":
            raise HTTPException(
                status_code=404 if "یافت نشد" in result.get("message", "") else 500,
                detail=result.get("message", "خطای نامشخص")
            )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"خطا در خواندن داده‌ها: {str(e)}"
        )


async def function_executor(function_name: str, arguments: dict) -> str:
    """
    Execute function calls from Gemini Live API using the active module
    
    Args:
        function_name: Name of the function to execute
        arguments: Function arguments
        
    Returns:
        Function result as JSON string
    """
    try:
        print(f"[Function Call] Executing: {function_name}", flush=True)
        print(f"[Function Call] Arguments: {arguments}", flush=True)
        
        result = await active_module.execute_function(function_name, arguments)
        print(f"[Function Call] Result: {result[:200]}...", flush=True)
        
        return result
    except Exception as e:
        error_msg = f"Error executing function {function_name}: {str(e)}"
        print(f"[Function Call] ❌ Error: {error_msg}", flush=True)
        import traceback
        traceback.print_exc()
        return json.dumps({"error": error_msg}, ensure_ascii=False)


async def listen_microphone(gemini_session: GeminiLiveSession):
    """
    Capture audio from server's microphone and send to Gemini Live
    """
    mic_info = pya.get_default_input_device_info()
    audio_stream = await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=SEND_SAMPLE_RATE,
        input=True,
        input_device_index=mic_info["index"],
        frames_per_buffer=CHUNK_SIZE,
    )
    
    try:
        while gemini_session.running:
            data = await asyncio.to_thread(audio_stream.read, CHUNK_SIZE, exception_on_overflow=False)
            await gemini_session.send_audio(data)
    except asyncio.CancelledError:
        pass
    finally:
        if audio_stream:
            audio_stream.stop_stream()
            audio_stream.close()


@app.websocket("/audio")
async def audio_stream(websocket: WebSocket):
    """
    WebSocket endpoint that connects client to Gemini Live.
    Server handles microphone input, client only receives audio output.
    
    Authentication: Client must provide 'token' query parameter.
    Example: ws://server/audio?token=hospital_token_abc123xyz
    """
    connection_id = id(websocket)
    gemini_session = None
    mic_task = None
    module = None
    
    try:
        # Extract and validate token from query parameters
        token = websocket.query_params.get("token")
        if not token:
            print(f"[Connection {connection_id}] ❌ Authentication failed: No token provided in query parameters", flush=True)
            print(f"[Connection {connection_id}] Expected format: ws://server/audio?token=YOUR_TOKEN", flush=True)
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token required")
            return
        
        # Mask token in logs for security (show only first 8 chars)
        token_mask = token[:8] + "..." if len(token) > 8 else "***"
        print(f"[Connection {connection_id}] 🔐 Authentication attempt with token: {token_mask}", flush=True)
        
        # Resolve module from token
        try:
            module_name = get_module_name_from_token(token)
            print(f"[Connection {connection_id}] ✅ Token validated successfully", flush=True)
            print(f"[Connection {connection_id}] 📦 Resolved module: {module_name}", flush=True)
        except ValueError as e:
            print(f"[Connection {connection_id}] ❌ Authentication failed: Invalid token ({token_mask})", flush=True)
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return
        
        # Get module instance for this connection
        try:
            module = get_module_by_name(module_name)
            print(f"[Connection {connection_id}] ✅ Module instance created: {module.name}", flush=True)
            print(f"[Connection {connection_id}] 📋 Module description: {module.description}", flush=True)
        except ValueError as e:
            print(f"[Connection {connection_id}] ❌ Module initialization failed: {e}", flush=True)
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Module not available")
            return
        
        # Accept WebSocket connection after authentication
        await websocket.accept()
        connections.append(websocket)
        
        # Create connection-specific function executor
        async def connection_function_executor(function_name: str, arguments: dict) -> str:
            """
            Execute function calls from Gemini Live API using the connection's module
            """
            try:
                print(f"[Function Call] Executing: {function_name}", flush=True)
                print(f"[Function Call] Arguments: {arguments}", flush=True)
                
                result = await module.execute_function(function_name, arguments)
                print(f"[Function Call] Result: {result[:200]}...", flush=True)
                
                return result
            except Exception as e:
                error_msg = f"Error executing function {function_name}: {str(e)}"
                print(f"[Function Call] ❌ Error: {error_msg}", flush=True)
                import traceback
                traceback.print_exc()
                return json.dumps({"error": error_msg}, ensure_ascii=False)
        
        # Create Gemini Live session with system prompt and tools
        print(f"[Connection {connection_id}] 🔧 Setting up Gemini Live session for module: {module.name}", flush=True)
        all_functions = module.get_common_functions() + module.functions
        print(f"[Connection {connection_id}] 📊 Total functions available: {len(all_functions)}", flush=True)
        print(f"[Connection {connection_id}]   - Common functions: {len(module.get_common_functions())}", flush=True)
        print(f"[Connection {connection_id}]   - Module-specific functions: {len(module.functions)}", flush=True)
        
        config = gemini_service.get_session_config(
            system_prompt=module.system_prompt,
            tools=all_functions  # Pass the actual functions
        )
        session_function_executor = connection_function_executor
        
        # Use async context manager for session
        async with gemini_service.client.aio.live.connect(
            model=gemini_service.model,
            config=config
        ) as session:
            gemini_session = GeminiLiveSession(session, session_function_executor)
            gemini_sessions[connection_id] = gemini_session
            
            print(f"[Connection {connection_id}] ✅ Connected to Gemini Live (Module: {module.name})", flush=True)
            
            # Start background tasks
            async with asyncio.TaskGroup() as tg:
                # Task 1: Capture microphone and send to Gemini
                mic_task = tg.create_task(listen_microphone(gemini_session))
                
                # Task 2: Receive audio from Gemini and forward to WebSocket client
                receive_task = tg.create_task(gemini_session.receive_realtime_loop(websocket))
                
                # Task 3: Send realtime audio loop (for queued audio)
                send_task = tg.create_task(gemini_session.send_realtime_loop())
                
                # Wait for WebSocket disconnect
                # Create a task that waits for disconnect
                async def wait_for_disconnect():
                    try:
                        # Try to receive (will raise on disconnect)
                        while True:
                            await websocket.receive()  # This blocks until disconnect
                    except WebSocketDisconnect:
                        print(f"[Connection {connection_id}] Client disconnected", flush=True)
                        gemini_session.running = False
                    except Exception as e:
                        print(f"[Connection {connection_id}] Connection error: {e}", flush=True)
                        gemini_session.running = False
                
                disconnect_task = tg.create_task(wait_for_disconnect())
                await disconnect_task
        
    except BaseExceptionGroup as eg:
        # Handle exception group from TaskGroup
        print(f"[Connection {connection_id}] ❌ TaskGroup error:", flush=True)
        import traceback
        traceback.print_exc()
    except WebSocketDisconnect:
        print(f"[Connection {connection_id}] WebSocket disconnected", flush=True)
    except Exception as e:
        print(f"[Connection {connection_id}] ❌ Unexpected error: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if gemini_session:
            gemini_session.running = False
            try:
                await gemini_session.close()
            except Exception as e:
                print(f"[Connection {connection_id}] Error closing Gemini session: {e}", flush=True)
        
        if connection_id in gemini_sessions:
            del gemini_sessions[connection_id]
        
        if websocket in connections:
            connections.remove(websocket)
        
        if module:
            print(f"[Connection {connection_id}] 🧹 Connection cleaned up (Module: {module.name})", flush=True)
        else:
            print(f"[Connection {connection_id}] 🧹 Connection cleaned up (No module was loaded)", flush=True)
        print(f"[Connection {connection_id}] 📊 Active connections: {len(connections)}", flush=True)
