import asyncio
import json
from app.llm_service import llm, FUNCTIONS

async def test_tool_calling():
    """Test if the model supports function calling/tools."""
    
    print("=" * 60)
    print("Testing Tool/Function Calling Support")
    print("=" * 60)
    print(f"Model: {llm.model}")
    print(f"Functions defined: {len(FUNCTIONS)}")
    print()
    
    # Test 1: Ask a question that should trigger the function
    print("Test 1: Asking about creator/designer")
    print("-" * 60)
    
    messages = [
        {
            "role": "system",
            "content": "شما یک دستیار صوتی فارسی هستید."
        },
        {
            "role": "user",
            "content": "سازنده این سیستم کیه؟"
        }
    ]
    
    try:
        response = await llm.chat(messages=messages, reasoning=False)
        
        print("Response type:", type(response))
        print("Response keys:", response.keys() if isinstance(response, dict) else "Not a dict")
        print()
        
        if isinstance(response, dict):
            if 'tool_calls' in response:
                print("✅ TOOL CALLING SUPPORTED!")
                print("Tool calls found:", len(response['tool_calls']))
                for i, tool_call in enumerate(response['tool_calls']):
                    print(f"  Tool call {i+1}:")
                    print(f"    Function: {tool_call.get('function', {}).get('name', 'N/A')}")
                    print(f"    Arguments: {tool_call.get('function', {}).get('arguments', 'N/A')}")
            else:
                print("❌ No tool_calls in response")
                print("Response content:", response.get('content', 'N/A')[:200])
                print()
                print("⚠️  Model may not support function calling, or didn't trigger it")
        else:
            print("❌ Unexpected response format")
            print("Response:", response)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    print("Test 2: Checking raw API response")
    print("-" * 60)
    
    # Test 2: Check what the API actually returns
    try:
        import httpx
        payload = {
            "model": llm.model,
            "messages": messages,
            "tools": FUNCTIONS,
            "tool_choice": "auto"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {llm.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload
            )
            
            result = response.json()
            print("API Response keys:", result.keys())
            print()
            
            if 'choices' in result:
                message = result['choices'][0]['message']
                print("Message keys:", message.keys())
                print()
                
                if 'tool_calls' in message:
                    print("✅ API returned tool_calls!")
                    print("Tool calls:", json.dumps(message['tool_calls'], indent=2, ensure_ascii=False))
                else:
                    print("❌ API did not return tool_calls")
                    print("Content:", message.get('content', 'N/A')[:200])
                    print()
                    print("Full message:", json.dumps(message, indent=2, ensure_ascii=False))
            else:
                print("Unexpected API response structure")
                print(json.dumps(result, indent=2, ensure_ascii=False))
                
    except Exception as e:
        print(f"❌ Error in API test: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    print("Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_tool_calling())
