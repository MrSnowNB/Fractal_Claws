import requests
import json

url = "http://localhost:8000/api/v1/chat/completions"
payload = {
    "model": "Qwen3.5-4B-GGUF",
    "messages": [
        {"role": "user", "content": "Output a simple JSON object: {\"hello\": \"world\"}"}
    ],
    "temperature": 0.2,
    "max_tokens": 2048
}

try:
    response = requests.post(url, json=payload, timeout=120)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Choices: {data.get('choices', [])}")
        if data.get('choices'):
            print(f"Content: {data['choices'][0].get('message', {}).get('content', 'EMPTY')}")
except Exception as e:
    print(f"Error: {e}")