import re
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from app.speech_service import transcribe_audio
from app.core.llm_service import llm
from app.config import get_active_module
from tts import PersianTTS

app = FastAPI()
connections = []
tts_engine = PersianTTS()

# بارگذاری ماژول فعال
active_module = get_active_module()

# Store conversation history per WebSocket connection
conversation_history: dict = {}


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
                "content": active_module.system_prompt
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
                    
                    # ترکیب توابع مشترک با توابع اختصاصی ماژول
                    all_functions = active_module.get_common_functions() + active_module.functions
                    
                    # Get LLM response (may include function calls)
                    llm_response = await llm.chat(
                        messages=conversation_history[connection_id],
                        reasoning=False,
                        tools=all_functions  # استفاده از توابع مشترک + توابع ماژول فعال
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
                        
                        # Execute each function call using the active module
                        for tool_call in llm_response['tool_calls']:
                            function_name = tool_call['function']['name']
                            print(f"[Function Call] Executing: {function_name}")
                            try:
                                arguments_str = tool_call['function'].get('arguments', '{}')
                                print(f"[Function Call] Arguments: {arguments_str}")
                                arguments = json.loads(arguments_str)
                            except json.JSONDecodeError as e:
                                print(f"[Function Call] JSON decode error: {e}")
                                arguments = {}
                            
                            # Execute the function using active module
                            print(f"[Function Call] Calling {active_module.name}.execute_function({function_name}, {arguments})")
                            function_result = await active_module.execute_function(function_name, arguments)
                            print(f"[Function Call] Result length: {len(function_result)} characters")
                            print(f"[Function Call] Result preview: {function_result[:200]}...")
                            
                            # Add function result to conversation history
                            conversation_history[connection_id].append({
                                "role": "tool",
                                "tool_call_id": tool_call['id'],
                                "name": function_name,
                                "content": function_result
                            })
                        
                        # Get final response from LLM after function execution
                        # ترکیب توابع مشترک با توابع اختصاصی ماژول
                        all_functions = active_module.get_common_functions() + active_module.functions
                        llm_response = await llm.chat(
                            messages=conversation_history[connection_id],
                            reasoning=False,
                            tools=all_functions
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
