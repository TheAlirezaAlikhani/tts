"""
Gemini Live API Service - Handles real-time speech-to-speech with function calling
"""
import asyncio
import json
import os
from typing import Dict, List, Any, Optional, Callable, Awaitable
from google import genai
from google.genai import types


class GeminiLiveService:
    """
    Service wrapper for Gemini Live API that handles:
    - Real-time audio streaming (STT + TTS)
    - Function calling integration
    - Conversation management
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "models/gemini-2.5-flash-native-audio-preview-12-2025"):
        """
        Initialize Gemini Live service
        
        Args:
            api_key: Google API key (defaults to environment variable)
            model: Model name to use
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model = model
        
        self.client = genai.Client(
            api_key=self.api_key,
            http_options={"api_version": "v1beta"},
        )
        
        # Configuration for live session
        self.config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
                )
            ),
            context_window_compression=types.ContextWindowCompressionConfig(
                trigger_tokens=25600,
                sliding_window=types.SlidingWindow(target_tokens=12800),
            ),
        )
        
        # Audio configuration
        self.send_sample_rate = 16000
        self.receive_sample_rate = 24000
        
    def get_session_config(
        self,
        system_prompt: str,
        tools: Optional[List[Dict]] = None
    ) -> types.LiveConnectConfig:
        """
        Create session configuration with system prompt and tools
        
        Args:
            system_prompt: System prompt for the conversation
            tools: List of function definitions (OpenRouter format)
            
        Returns:
            LiveConnectConfig object
        """
        # Convert OpenRouter tools format to Gemini format if needed
        gemini_tools = None
        if tools:
            print(f"[DEBUG] Converting {len(tools)} tools to Gemini format...", flush=True)
            gemini_tools = self._convert_tools_to_gemini(tools)
            print(f"[DEBUG] Converted to {len(gemini_tools)} Tool(s) with {sum(len(t.function_declarations) for t in gemini_tools)} function declarations", flush=True)
        
        # Create session config with system instruction
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
                )
            ),
            context_window_compression=types.ContextWindowCompressionConfig(
                trigger_tokens=25600,
                sliding_window=types.SlidingWindow(target_tokens=12800),
            ),
        )
        
        # Add system instruction
        if system_prompt:
            config.system_instruction = types.Content(
                parts=[types.Part(text=system_prompt)]
            )
        
        # Add tools if provided
        # NOTE: Some models (especially preview models) may not support tools
        # If you get error 1008 "Operation is not implemented", the model doesn't support function calling
        if gemini_tools:
            try:
                config.tools = gemini_tools
                print(f"[DEBUG] ✅ Added {len(gemini_tools)} tool(s) to LiveConnectConfig", flush=True)
                for i, tool in enumerate(gemini_tools):
                    func_count = len(tool.function_declarations) if hasattr(tool, 'function_declarations') else 0
                    print(f"[DEBUG]   Tool {i+1}: {func_count} function(s)", flush=True)
                    if hasattr(tool, 'function_declarations'):
                        for j, func in enumerate(tool.function_declarations):
                            func_name = func.name if hasattr(func, 'name') else str(func)
                            print(f"[DEBUG]     Function {j+1}: {func_name}", flush=True)
            except Exception as e:
                print(f"[ERROR] Failed to add tools to config: {e}", flush=True)
                print(f"[WARNING] Model may not support function calling. Continuing without tools...", flush=True)
                # Don't set tools if it fails
        else:
            print("[INFO] No tools provided to LiveConnectConfig", flush=True)
        
        return config
    
    def _convert_tools_to_gemini(self, tools: List[Dict]) -> List[types.Tool]:
        """
        Convert OpenRouter tools format to Gemini format
        
        According to Gemini docs: https://ai.google.dev/gemini-api/docs/function-calling
        We can pass function declarations as dicts directly to types.Tool
        
        Args:
            tools: List of tools in OpenRouter format (OpenAI/OpenRouter format)
            
        Returns:
            List of Gemini Tool objects (all functions grouped into one Tool)
        """
        function_declarations = []
        
        for tool in tools:
            if tool.get("type") == "function":
                func_def = tool.get("function", {})
                name = func_def.get("name")
                description = func_def.get("description", "")
                parameters = func_def.get("parameters", {})
                
                if not name:
                    print(f"[WARNING] Skipping function without name: {func_def}", flush=True)
                    continue
                
                # Validate parameters schema
                if not isinstance(parameters, dict):
                    print(f"[WARNING] Invalid parameters for {name}, using empty schema", flush=True)
                    parameters = {"type": "object", "properties": {}, "required": []}
                
                # Ensure parameters has required fields (as per Gemini docs)
                if "type" not in parameters:
                    parameters["type"] = "object"
                if "properties" not in parameters:
                    parameters["properties"] = {}
                if "required" not in parameters:
                    parameters["required"] = []
                
                # Try Schema format first (like working gemeni-test-2.py)
                # If that fails, fallback to dict format (as shown in Live API docs)
                try:
                    # Convert properties to Schema objects
                    schema_properties = {}
                    for prop_name, prop_schema in parameters.get("properties", {}).items():
                        prop_type_str = prop_schema.get("type", "string")
                        prop_description = prop_schema.get("description", "")
                        
                        # Map string types to genai.types.Type enum
                        type_mapping = {
                            "string": types.Type.STRING,
                            "integer": types.Type.INTEGER,
                            "number": types.Type.NUMBER,
                            "boolean": types.Type.BOOLEAN,
                            "array": types.Type.ARRAY,
                            "object": types.Type.OBJECT
                        }
                        gemini_type = type_mapping.get(prop_type_str, types.Type.STRING)
                        
                        schema_properties[prop_name] = types.Schema(
                            type=gemini_type,
                            description=prop_description
                        )
                    
                    # Create Schema for the entire parameters object
                    parameters_schema = types.Schema(
                        type=types.Type.OBJECT,
                        required=parameters.get("required", []),
                        properties=schema_properties
                    )
                    
                    # Create FunctionDeclaration with Schema format (like working test file)
                    gemini_function = types.FunctionDeclaration(
                        name=name,
                        description=description or f"Function: {name}",
                        parameters=parameters_schema
                    )
                    function_declarations.append(gemini_function)
                    print(f"[DEBUG] ✅ Converted function: {name} (using Schema format)", flush=True)
                    print(f"[DEBUG]   Description: {description[:100]}...", flush=True)
                    print(f"[DEBUG]   Parameters: {len(schema_properties)} property(ies)", flush=True)
                except Exception as schema_err:
                    # Fallback to dict format (as shown in Live API docs)
                    print(f"[DEBUG] Schema format failed for {name}, trying dict format: {schema_err}", flush=True)
                    try:
                        # Use dict format directly (as per Live API docs)
                        gemini_function = {
                            "name": name,
                            "description": description or f"Function: {name}",
                            "parameters": parameters  # Use dict directly
                        }
                        function_declarations.append(gemini_function)
                        print(f"[DEBUG] ✅ Converted function: {name} (using dict format)", flush=True)
                    except Exception as dict_err:
                        print(f"[ERROR] Both Schema and dict formats failed for {name}: {dict_err}", flush=True)
                        import traceback
                        traceback.print_exc()
                        continue
        
        # Group all functions into a single Tool (Gemini's preferred format)
        # According to docs: types.Tool(function_declarations=[...])
        if function_declarations:
            tool = types.Tool(function_declarations=function_declarations)
            print(f"[DEBUG] Created Tool with {len(function_declarations)} function declarations", flush=True)
            return [tool]
        
        print("[WARNING] No function declarations created!", flush=True)
        return []
    
    def _convert_schema_to_gemini(self, schema: Dict):
        """
        Convert JSON schema to Gemini Schema format
        
        Args:
            schema: JSON schema dictionary
            
        Returns:
            Gemini Schema object or dict
        """
        # Extract properties and required fields
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        # Convert properties to Gemini format
        gemini_properties = {}
        for prop_name, prop_schema in properties.items():
            prop_type = prop_schema.get("type", "string")
            prop_description = prop_schema.get("description", "")
            
            # Map JSON schema types to Gemini types
            type_mapping = {
                "string": types.Type.STRING,
                "integer": types.Type.INTEGER,
                "number": types.Type.NUMBER,
                "boolean": types.Type.BOOLEAN,
                "array": types.Type.ARRAY,
                "object": types.Type.OBJECT
            }
            
            gemini_type = type_mapping.get(prop_type, types.Type.STRING)
            
            gemini_properties[prop_name] = types.Schema(
                type=gemini_type,
                description=prop_description
            )
        
        return types.Schema(
            type=types.Type.OBJECT,
            properties=gemini_properties,
            required=required
        )


class GeminiLiveSession:
    """
    Wrapper for a Gemini Live session that handles audio streaming and function calls
    """
    
    def __init__(self, session, function_executor: Optional[Callable[[str, Dict], Awaitable[str]]] = None):
        """
        Initialize session wrapper
        
        Args:
            session: Gemini Live session object
            function_executor: Async function to execute function calls
        """
        self.session = session
        self.function_executor = function_executor
        self.audio_in_queue = asyncio.Queue()
        self.audio_out_queue = asyncio.Queue(maxsize=5)
        self.running = True
        
    async def send_audio(self, audio_data: bytes):
        """
        Send audio data to Gemini
        
        Args:
            audio_data: PCM audio bytes (16kHz, 16-bit, mono)
        """
        payload = {
            "data": audio_data,
            "mime_type": "audio/pcm"
        }
        
        # To reduce latency, drop oldest item if queue is full
        try:
            self.audio_out_queue.put_nowait(payload)
        except asyncio.QueueFull:
            _ = self.audio_out_queue.get_nowait()
            self.audio_out_queue.put_nowait(payload)
    
    async def receive_audio(self) -> bytes:
        """
        Receive audio data from Gemini
        
        Returns:
            PCM audio bytes (24kHz, 16-bit, mono)
        """
        return await self.audio_in_queue.get()
    
    async def send_realtime_loop(self):
        """Background task to send audio to Gemini"""
        try:
            while self.running:
                msg = await self.audio_out_queue.get()
                if msg["mime_type"].startswith("audio/"):
                    await self.session.send_realtime_input(audio=msg)
        except asyncio.CancelledError:
            pass
    
    async def receive_realtime_loop(self, websocket=None):
        """
        Background task to receive audio and handle function calls from Gemini
        
        Args:
            websocket: Optional WebSocket to forward audio directly
        """
        try:
            while self.running:
                try:
                    turn = self.session.receive()
                    print(f"[RECEIVE] Waiting for turn...", flush=True)
                except Exception as receive_err:
                    # Normal disconnect when user closes connection - don't log as error
                    if "disconnect" in str(receive_err).lower() or "closed" in str(receive_err).lower():
                        break
                    
                    # Check for "Operation is not implemented" error (1008)
                    # This means the model doesn't support function calling
                    error_str = str(receive_err).lower()
                    if "operation is not implemented" in error_str or "1008" in error_str:
                        print(f"\n[ERROR] ⚠️ Model does not support function calling (error 1008)")
                        print(f"[ERROR] The preview model 'gemini-2.5-flash-native-audio-preview-12-2025' does not support tools/function calling")
                        print(f"[ERROR] This is a limitation of the preview model.")
                        print(f"[ERROR] Stopping to prevent infinite errors...")
                        self.running = False
                        break
                    
                    raise
                
                try:
                    async for response in turn:
                        try:
                            # Debug: Check response structure
                            response_has_parts = hasattr(response, 'parts') and response.parts
                            response_has_text = hasattr(response, 'text') and response.text
                            response_has_tool_call = hasattr(response, 'tool_call') and response.tool_call
                            
                            # Only log when there's something interesting (parts, text, or tool_call)
                            if response_has_parts or response_has_text or response_has_tool_call:
                                print(f"[RECEIVE] Got response - has_parts: {response_has_parts}, has_text: {response_has_text}, has_tool_call: {response_has_tool_call}", flush=True)
                            
                            # If response has parts or text, log the structure for debugging
                            if response_has_parts or (response_has_text and any(keyword in response.text.lower() for keyword in ['search', 'query', 'function', 'call'])):
                                print(f"[DEBUG] Response type: {type(response).__name__}", flush=True)
                                print(f"[DEBUG] Response attributes: {[a for a in dir(response) if not a.startswith('_') and not callable(getattr(response, a, None))]}", flush=True)
                                if response_has_parts:
                                    print(f"[DEBUG] Response has {len(response.parts)} parts", flush=True)
                                    for i, part in enumerate(response.parts):
                                        part_attrs = [a for a in dir(part) if not a.startswith('_') and not callable(getattr(part, a, None))]
                                        print(f"[DEBUG] Part {i} type: {type(part).__name__}, attributes: {part_attrs}", flush=True)
                            
                            # Check for function calls - Live API uses response.tool_call
                            # According to Live API docs: https://ai.google.dev/gemini-api/docs/live-tools
                            # Function calls come as response.tool_call with function_calls list
                            function_calls = None
                            
                            # PRIMARY: Check for tool_call (Live API format)
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
                                                print(f"[DEBUG] Function call {i}: name={fc.name}, id={getattr(fc, 'id', None)}, args={getattr(fc, 'args', {})}", flush=True)
                                except Exception as e:
                                    print(f"[DEBUG] Error accessing tool_call: {e}", flush=True)
                                    import traceback
                                    traceback.print_exc()
                            
                            # Fallback: Check response.parts for function_call (standard API format)
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
                                            if hasattr(part.tool_call, 'function_calls'):
                                                function_calls.extend(part.tool_call.function_calls)
                                            else:
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
                            
                            # Fallback: Check for function_calls (plural) attribute
                            if not function_calls and hasattr(response, 'function_calls') and response.function_calls:
                                try:
                                    fc = response.function_calls
                                    function_calls = fc if isinstance(fc, list) else [fc]
                                    print(f"\n[DEBUG] ✅ Found function_calls attribute: {len(function_calls)} call(s)", flush=True)
                                except Exception as e:
                                    print(f"[DEBUG] Error accessing function_calls: {e}", flush=True)
                            
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
                            
                            # IMPORTANT: Check for function calls FIRST, before audio/text
                            # Function calls might come in the same response as audio
                            if function_calls:
                                print(f"\n[FUNCTION CALL] ✅ Detected {len(function_calls)} function call(s)", flush=True)
                                await self._handle_function_calls(function_calls)
                                print(f"[FUNCTION CALL] ✅ Function call handling completed", flush=True)
                                # Continue to receive Gemini's follow-up response
                                print(f"[FUNCTION CALL] Waiting for Gemini's follow-up response...", flush=True)
                            else:
                                # Debug: If we have parts but no function calls, log it
                                if response_has_parts:
                                    print(f"[DEBUG] Response has parts but no function_call detected", flush=True)
                            
                            # Handle audio response (may come with or after function calls)
                            if data := response.data:
                                self.audio_in_queue.put_nowait(data)
                                # Forward to websocket if provided
                                if websocket:
                                    try:
                                        await websocket.send_bytes(data)
                                    except Exception as e:
                                        print(f"[Gemini] Error forwarding audio to websocket: {e}", flush=True)
                            
                            # Handle text response (for debugging/logging)
                            if text := response.text:
                                print(text, end="", flush=True)
                                # Check if text mentions inability to use functions
                                if any(phrase in text.lower() for phrase in ["can't", "cannot", "unable", "don't have access", "no access", "نمی‌توانم", "دسترسی ندارم"]):
                                    print(f"\n[WARNING] Gemini says it can't do something - checking if functions are available...", flush=True)
                                    print(f"[DEBUG] Response has parts: {response_has_parts}", flush=True)
                                    if response_has_parts:
                                        print(f"[DEBUG] Checking all parts for function_call availability...", flush=True)
                                        for i, part in enumerate(response.parts):
                                            print(f"[DEBUG] Part {i}: type={type(part).__name__}, has function_call={hasattr(part, 'function_call')}", flush=True)
                                            if hasattr(part, 'function_call'):
                                                print(f"[DEBUG] Part {i} function_call: {part.function_call}", flush=True)
                            
                        except Exception as response_err:
                            error_str = str(response_err).lower()
                            error_code = None
                            if "1008" in error_str or "operation is not implemented" in error_str:
                                error_code = 1008
                            elif "1011" in error_str or "internal error" in error_str:
                                error_code = 1011
                            
                            if error_code == 1008:
                                print(f"\n[ERROR] ⚠️ Model does not support function calling (error 1008)", flush=True)
                                print(f"[ERROR] This might be due to incorrect function declaration format", flush=True)
                                print(f"[ERROR] Stopping receive loop to prevent infinite errors...", flush=True)
                                self.running = False
                                break
                            elif error_code == 1011:
                                print(f"\n[ERROR] ⚠️ Internal server error (error 1011)", flush=True)
                                print(f"[ERROR] This might be due to invalid function declaration format", flush=True)
                                print(f"[ERROR] Stopping receive loop to prevent infinite errors...", flush=True)
                                self.running = False
                                break
                            
                            print(f"[RECEIVE] ❌ Error processing response: {response_err}", flush=True)
                            import traceback
                            traceback.print_exc()
                            # Continue to next response instead of breaking
                            
                except Exception as turn_err:
                    # Normal disconnect when user closes connection - don't log as error
                    if "disconnect" in str(turn_err).lower() or "closed" in str(turn_err).lower():
                        print(f"[RECEIVE] Connection closed/disconnected", flush=True)
                        break
                    
                    # Check for specific API errors
                    error_str = str(turn_err).lower()
                    error_code = None
                    if "1008" in error_str or "operation is not implemented" in error_str:
                        error_code = 1008
                    elif "1011" in error_str or "internal error" in error_str:
                        error_code = 1011
                    
                    if error_code == 1008:
                        print(f"\n[ERROR] ⚠️ Model does not support function calling (error 1008)", flush=True)
                        print(f"[ERROR] The preview model does not support tools/function calling", flush=True)
                        print(f"[ERROR] Stopping receive loop to prevent infinite errors...", flush=True)
                        self.running = False
                        break
                    elif error_code == 1011:
                        print(f"\n[ERROR] ⚠️ Internal server error (error 1011)", flush=True)
                        print(f"[ERROR] This might be due to invalid function declaration format", flush=True)
                        print(f"[ERROR] Stopping receive loop to prevent infinite errors...", flush=True)
                        self.running = False
                        break
                    
                    print(f"[RECEIVE] ❌ Error in turn: {turn_err}", flush=True)
                    import traceback
                    traceback.print_exc()
                    # Continue to next turn instead of breaking
                
                # If turn is complete (e.g., user interrupted), clear audio queue
                while not self.audio_in_queue.empty():
                    try:
                        self.audio_in_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[Gemini] Error in receive_realtime_loop: {e}")
            import traceback
            traceback.print_exc()
    
    async def _handle_function_calls(self, function_calls: List):
        """
        Handle function calls from Gemini
        
        Args:
            function_calls: List of function call objects (from tool_call.function_calls)
        """
        # Function executor must be provided
        if not self.function_executor:
            print("[ERROR] No function executor provided! Cannot execute function calls.", flush=True)
            return
        
        executor = self.function_executor
        
        # Build list of function responses to send back
        function_responses = []
        
        for func_call in function_calls:
            # According to Live API docs: https://ai.google.dev/gemini-api/docs/live-tools
            # FunctionCall objects have: id, name, and args
            function_name = None
            function_call_id = None
            arguments = {}
            
            # Handle different function call structures
            if hasattr(func_call, 'name'):
                # Direct function_call object (from tool_call.function_calls)
                function_name = func_call.name
                function_call_id = getattr(func_call, 'id', None)
                if hasattr(func_call, 'args'):
                    args = func_call.args
                    if isinstance(args, str):
                        try:
                            arguments = json.loads(args)
                        except json.JSONDecodeError:
                            arguments = {}
                    elif isinstance(args, dict):
                        arguments = args
                    else:
                        arguments = {}
                else:
                    arguments = {}
            elif hasattr(func_call, 'function'):
                # Nested structure: func_call.function.name (fallback for standard API)
                function_name = func_call.function.name
                function_call_id = getattr(func_call, 'id', None)
                if hasattr(func_call.function, 'args'):
                    args = func_call.function.args
                    if isinstance(args, str):
                        try:
                            arguments = json.loads(args)
                        except json.JSONDecodeError:
                            arguments = {}
                    elif isinstance(args, dict):
                        arguments = args
                    else:
                        arguments = {}
                else:
                    arguments = {}
            else:
                print(f"[Function Call] ❌ Unknown function call structure: {func_call}", flush=True)
                print(f"[Function Call] Attributes: {[attr for attr in dir(func_call) if not attr.startswith('_')]}", flush=True)
                continue
            
            print(f"[Function Call] ✅ Executing: {function_name}", flush=True)
            print(f"[Function Call] ID: {function_call_id}", flush=True)
            print(f"[Function Call] Arguments: {arguments}", flush=True)
            
            try:
                # Execute the function (returns JSON string)
                result_json = await executor(function_name, arguments)
                
                # Parse the JSON result to send as dict to Gemini
                try:
                    result_dict = json.loads(result_json)
                except json.JSONDecodeError:
                    # If not valid JSON, wrap it
                    result_dict = {"result": result_json}
                
                # FunctionResponse.response MUST be a dict, not a list
                # If result is a list, wrap it in a dict
                if isinstance(result_dict, list):
                    result_dict = {"results": result_dict}
                elif not isinstance(result_dict, dict):
                    # If it's not a dict or list, wrap it
                    result_dict = {"result": result_dict}
                
                # Create FunctionResponse with id, name, and response
                # According to Live API docs, FunctionResponse MUST include id
                function_response = types.FunctionResponse(
                    id=function_call_id,  # REQUIRED for Live API
                    name=function_name,
                    response=result_dict  # Must be a dict
                )
                function_responses.append(function_response)
                
                print(f"[Function Call] ✅ Function executed: {function_name}", flush=True)
                print(f"[Function Call] Result: {result_json[:200]}...", flush=True)
                
            except Exception as e:
                error_msg = f"Error executing function {function_name}: {str(e)}"
                print(f"[Function Call] ❌ Error: {error_msg}", flush=True)
                import traceback
                traceback.print_exc()
                
                # Create error response
                error_response = types.FunctionResponse(
                    id=function_call_id,
                    name=function_name,
                    response={"error": error_msg}
                )
                function_responses.append(error_response)
        
        # Send all function responses back to Gemini using send_tool_response
        # According to Live API docs: https://ai.google.dev/gemini-api/docs/live-tools
        # Use send_tool_response(function_responses=[...]) for Live API
        if function_responses:
            try:
                await self.session.send_tool_response(
                    function_responses=function_responses
                )
                print(f"[Function Call] ✅ Sent {len(function_responses)} function response(s) back to Gemini", flush=True)
                print(f"[Function Call] Waiting for Gemini's follow-up response...", flush=True)
            except Exception as send_err:
                print(f"[Function Call] ❌ Error sending function responses: {send_err}", flush=True)
                import traceback
                traceback.print_exc()
    
    async def send_text(self, text: str):
        """
        Send text message to Gemini (for testing/debugging)
        
        Args:
            text: Text message to send
        """
        await self.session.send_client_content(
            turns=types.Content(parts=[types.Part(text=text)]),
            turn_complete=True
        )
    
    async def close(self):
        """Close the session"""
        self.running = False
        if hasattr(self.session, 'close'):
            await self.session.close()
