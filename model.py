from langchain_openai import ChatOpenAI
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

# Lấy API key
google_api_key = os.getenv("GOOGLE_API_KEY")
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
grok_api_key = os.getenv("GROK_API_KEY")

# Simple wrapper for consistent interface
class ModelWrapper:
    def __init__(self, model, name):
        self.model = model
        self.name = name
    
    def stream(self, prompt):
        try:
            for chunk in self.model.stream(prompt):
                yield chunk
        except Exception as e:
            yield type('obj', (object,), {'content': f"Error with {self.name}: {str(e)}"})
    
    def invoke(self, prompt):
        try:
            return self.model.invoke(prompt)
        except Exception as e:
            return type('obj', (object,), {'content': f"Error with {self.name}: {str(e)}"})

# Google Gemini REST API Wrapper with streaming support
class GeminiAPIWrapper:
    def __init__(self, model_name, api_key, temperature=0.7):
        self.model_name = model_name
        self.api_key = api_key
        self.temperature = temperature
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}"
    
    def _prepare_prompt(self, prompt):
        """Convert prompt to string format"""
        if isinstance(prompt, list):
            return "\n".join([msg.get("content", str(msg)) for msg in prompt])
        return str(prompt)
    
    def invoke(self, prompt):
        """Call Gemini API directly (non-streaming)"""
        try:
            prompt_text = self._prepare_prompt(prompt)
            
            payload = {
                "contents": [{
                    "parts": [{"text": prompt_text}]
                }],
                "generationConfig": {
                    "temperature": self.temperature,
                    "maxOutputTokens": 2048,
                }
            }
            
            response = requests.post(
                f"{self.base_url}:generateContent?key={self.api_key}",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=15  # Giảm timeout xuống 15s
            )
            
            if response.status_code == 200:
                data = response.json()
                if "candidates" in data and len(data["candidates"]) > 0:
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return type('obj', (object,), {'content': text})
                else:
                    return type('obj', (object,), {'content': "No response from Gemini"})
            else:
                error_msg = f"Gemini API error {response.status_code}: {response.text[:100]}"
                print(f"[Gemini Error] {error_msg}")
                return type('obj', (object,), {'content': error_msg})
                
        except requests.exceptions.Timeout:
            return type('obj', (object,), {'content': "Gemini API timeout (>15s)"})
        except Exception as e:
            error_msg = f"Gemini error: {str(e)}"
            print(f"[Gemini Exception] {error_msg}")
            return type('obj', (object,), {'content': error_msg})
    
    def stream(self, prompt):
        """Stream response from Gemini API"""
        try:
            prompt_text = self._prepare_prompt(prompt)
            
            payload = {
                "contents": [{
                    "parts": [{"text": prompt_text}]
                }],
                "generationConfig": {
                    "temperature": self.temperature,
                    "maxOutputTokens": 2048,
                }
            }
            
            # Sử dụng streamGenerateContent endpoint
            response = requests.post(
                f"{self.base_url}:streamGenerateContent?key={self.api_key}&alt=sse",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30,
                stream=True  # Enable streaming
            )
            
            if response.status_code == 200:
                # Parse SSE (Server-Sent Events) stream
                accumulated_text = ""
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        # SSE format: "data: {...}"
                        if line_str.startswith('data: '):
                            json_str = line_str[6:]  # Remove "data: " prefix
                            try:
                                data = json.loads(json_str)
                                if "candidates" in data and len(data["candidates"]) > 0:
                                    parts = data["candidates"][0].get("content", {}).get("parts", [])
                                    if parts and "text" in parts[0]:
                                        chunk_text = parts[0]["text"]
                                        accumulated_text += chunk_text
                                        # Yield chunk
                                        yield type('obj', (object,), {'content': chunk_text})
                            except json.JSONDecodeError:
                                continue
                
                # If no streaming data, fallback to invoke
                if not accumulated_text:
                    result = self.invoke(prompt)
                    yield result
            else:
                error_msg = f"Gemini stream error {response.status_code}"
                yield type('obj', (object,), {'content': error_msg})
                
        except requests.exceptions.Timeout:
            yield type('obj', (object,), {'content': "Gemini stream timeout"})
        except Exception as e:
            error_msg = f"Gemini stream error: {str(e)}"
            print(f"[Gemini Stream Exception] {error_msg}")
            # Fallback to non-streaming
            result = self.invoke(prompt)
            yield result

# DeepSeek models (primary - more reliable)
if deepseek_api_key:
    deepseek_chat = ModelWrapper(
        ChatOpenAI(
            model="deepseek-chat",
            temperature=0.7,
            api_key=deepseek_api_key,
            base_url="https://api.deepseek.com/v1",
            timeout=30,  # 30 second timeout
        ),
        "DeepSeek Chat"
    )
    
    deepseek_reasoner = ModelWrapper(
        ChatOpenAI(
            model="deepseek-reasoner",
            temperature=0.7,
            api_key=deepseek_api_key,
            base_url="https://api.deepseek.com/v1",
            timeout=30,
        ),
        "DeepSeek Reasoner"
    )
else:
    # Fallback
    class DummyModel:
        def stream(self, prompt):
            yield type('obj', (object,), {'content': "DeepSeek API key chưa được cấu hình"})
        def invoke(self, prompt):
            return type('obj', (object,), {'content': "DeepSeek API key chưa được cấu hình"})
    
    deepseek_chat = DummyModel()
    deepseek_reasoner = DummyModel()

# Grok models (secondary)
if grok_api_key:
    grok_chat = ModelWrapper(
        ChatOpenAI(
            model="grok-2-latest",
            temperature=0.7,
            api_key=grok_api_key,
            base_url="https://api.x.ai/v1",
            timeout=30,
        ),
        "Grok 2"
    )
else:
    class DummyModel:
        def stream(self, prompt):
            yield type('obj', (object,), {'content': "Grok API key chưa được cấu hình"})
        def invoke(self, prompt):
            return type('obj', (object,), {'content': "Grok API key chưa được cấu hình"})
    
    grok_chat = DummyModel()

# Google Gemini models using REST API
if google_api_key:
    # Sử dụng các models mới nhất từ Gemini 2.5 và 2.0
    gemini_flash = GeminiAPIWrapper("gemini-2.5-flash", google_api_key, temperature=0.7)
    gemini_pro = GeminiAPIWrapper("gemini-2.5-pro", google_api_key, temperature=0.7)
    gemini_flash_lite = GeminiAPIWrapper("gemini-2.5-flash-lite", google_api_key, temperature=0.7)
else:
    class DummyModelGoogle:
        def stream(self, prompt):
            yield type('obj', (object,), {'content': "Google API key chưa được cấu hình"})
        def invoke(self, prompt):
            return type('obj', (object,), {'content': "Google API key chưa được cấu hình"})
    
    gemini_flash = DummyModelGoogle()
    gemini_pro = DummyModelGoogle()
    gemini_flash_lite = DummyModelGoogle()

# Dictionary để chọn model theo tên
models = {
    "grok-2": grok_chat,
    "deepseek-chat": deepseek_chat,
    "deepseek-reasoner": deepseek_reasoner,
    "gemini-flash": gemini_flash,
    "gemini-pro": gemini_pro,
    "gemini-flash-lite": gemini_flash_lite,
    # Aliases
    "google": gemini_pro,
    "gemini": gemini_pro,
}

# ✅ Test code
if __name__ == "__main__":
    print("Danh sách models khả dụng:", list(models.keys()))

    try:
        print("\n--- Test Gemini Flash ---")
        res = models["gemini-flash"]["model"].invoke("Xin chào, bạn có hoạt động không?")
        print("Kết quả:", res.content if hasattr(res, "content") else res)
    except Exception as e:
        print("❌ Lỗi khi gọi gemini-flash:", e)