from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.speech_service import transcribe_audio
from app.llm_service import llm, execute_function
from tts import PersianTTS
import json

app = FastAPI()
connections = []
tts_engine = PersianTTS()

# Store conversation history per WebSocket connection
conversation_history: dict = {}


@app.websocket("/audio")
async def audio_stream(websocket: WebSocket):
    await websocket.accept()
    connections.append(websocket)
    
    # Initialize conversation history for this connection
    connection_id = id(websocket)
    if connection_id not in conversation_history:
        conversation_history[connection_id] = [
            {
                "role": "system",
                "content": "شما یک دستیار صوتی فارسی هستید. پاسخ‌های خود را کوتاه (حداکثر 2-3 جمله)، فقط به فارسی و بدون ایموجی بنویسید."
            }
        ]

    try:
        while True:
            try:
                # دریافت داده صوتی از کلاینت
                audio_chunk = await websocket.receive_bytes()

                # 1. تبدیل گفتار به متن (Speech Recognition)
                user_text = transcribe_audio(audio_chunk)
                await websocket.send_text(f"شما گفتید: {user_text}")

                # 2. ارسال متن به LLM و دریافت پاسخ
                try:
                    # Add user message to history
                    conversation_history[connection_id].append({
                        "role": "user",
                        "content": user_text
                    })
                    
                    # Get LLM response (may include function calls)
                    llm_response = await llm.chat(
                        messages=conversation_history[connection_id],
                        reasoning=False
                    )
                    
                    # Handle function calls if present
                    if isinstance(llm_response, dict) and 'tool_calls' in llm_response:
                        # Add assistant message with tool calls to history
                        assistant_message = {
                            "role": "assistant",
                            "content": llm_response.get('content', ''),
                            "tool_calls": llm_response['tool_calls']
                        }
                        if 'reasoning_details' in llm_response:
                            assistant_message['reasoning_details'] = llm_response['reasoning_details']
                        conversation_history[connection_id].append(assistant_message)
                        
                        # Execute each function call
                        for tool_call in llm_response['tool_calls']:
                            function_name = tool_call['function']['name']
                            try:
                                arguments = json.loads(tool_call['function'].get('arguments', '{}'))
                            except json.JSONDecodeError:
                                arguments = {}
                            
                            # Execute the function
                            function_result = await execute_function(function_name, arguments)
                            
                            # Add function result to conversation history
                            conversation_history[connection_id].append({
                                "role": "tool",
                                "tool_call_id": tool_call['id'],
                                "name": function_name,
                                "content": function_result
                            })
                        
                        # Get final response from LLM after function execution
                        llm_response = await llm.chat(
                            messages=conversation_history[connection_id],
                            reasoning=False
                        )
                    
                    # Handle final response
                    if isinstance(llm_response, dict):
                        assistant_content = llm_response.get('content', '')
                        # Preserve reasoning_details in history if present
                        conversation_history[connection_id].append({
                            "role": "assistant",
                            "content": assistant_content,
                            "reasoning_details": llm_response.get('reasoning_details')
                        })
                    else:
                        assistant_content = llm_response
                        conversation_history[connection_id].append({
                            "role": "assistant",
                            "content": assistant_content
                        })
                    
                    await websocket.send_text(f"ربات: {assistant_content}")
                    
                except Exception as llm_err:
                    error_msg = f"خطا در ارتباط با LLM: {llm_err}"
                    try:
                        await websocket.send_text(error_msg)
                    except (WebSocketDisconnect, RuntimeError):
                        break  # Break out of loop if connection closed
                    continue

                # 3. تبدیل پاسخ LLM به گفتار و ارسال صوت
                try:
                    # Clean text: remove emojis and special characters
                    import re
                    # Remove English text (keep only Persian/Arabic)
                    cleaned_content = re.sub(r'[A-Za-z]+', '', assistant_content)
                    # Remove emojis and special unicode
                    cleaned_content = re.sub(r'[^\w\s\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF.,!?;:()\-]', '', cleaned_content)
                    cleaned_content = cleaned_content.replace('\n', ' ').replace('\r', ' ')
                    cleaned_content = ' '.join(cleaned_content.split())
                    
                    # Limit text length for TTS (edge-tts has limits)
                    if len(cleaned_content) > 300:
                        cleaned_content = cleaned_content[:300]
                    
                    if cleaned_content.strip():
                        print(f"TTS Input: {cleaned_content[:100]}...")  # Debug log
                        tts_audio = await tts_engine.synthesize_to_bytes(cleaned_content)
                        print(f"TTS Success: {len(tts_audio)} bytes")  # Debug log
                        
                        # Check if connection is still open before sending
                        try:
                            await websocket.send_bytes(tts_audio)
                        except (WebSocketDisconnect, RuntimeError) as send_err:
                            print(f"Client disconnected before audio could be sent: {send_err}")
                            break  # Break out of loop if connection closed
                    else:
                        try:
                            await websocket.send_text("خطا: متن خالی برای تبدیل به گفتار")
                        except (WebSocketDisconnect, RuntimeError):
                            break  # Break out of loop if connection closed
                except Exception as tts_err:
                    error_detail = str(tts_err)
                    # Only log if it's not a connection error
                    if "disconnect" not in error_detail.lower() and "close" not in error_detail.lower():
                        print(f"TTS Error: {error_detail}")
                        print(f"Original text: {assistant_content[:200]}")
                        import traceback
                        traceback.print_exc()
                        try:
                            await websocket.send_text(f"خطا در تبدیل متن به گفتار: {error_detail}")
                        except (WebSocketDisconnect, RuntimeError):
                            break  # Break out of loop if connection closed

            except WebSocketDisconnect:
                # Client disconnected, break out of loop
                break
            except Exception as e:
                # جلوگیری از قطع ناگهانی اتصال در صورت خطا
                try:
                    await websocket.send_text(f"خطا در پردازش صدا: {e}")
                except (WebSocketDisconnect, RuntimeError):
                    # Client already disconnected, break out of loop
                    break
    except WebSocketDisconnect:
        # Connection closed normally
        pass
    finally:
        # Always clean up, regardless of how the connection ended
        if websocket in connections:
            connections.remove(websocket)
        if connection_id in conversation_history:
            del conversation_history[connection_id]
        print(f"Connection {connection_id} cleaned up. Active connections: {len(connections)}")