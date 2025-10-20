# models.py
try:
    import google.generativeai as genai
except ImportError:
    genai = None
    
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# Lấy API key
google_api_key = os.getenv("GOOGLE_API_KEY")
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
grok_api_key = os.getenv("GROK_API_KEY")

# Configure Google Gemini nếu có
if genai and google_api_key:
    genai.configure(api_key=google_api_key)

# Wrapper class cho Google Gemini để tương thích với LangChain interface
class GoogleGenerativeAIWrapper:
    def __init__(self, model_name, temperature=0.7):
        self.model_name = model_name
        self.temperature = temperature
        self.available = genai is not None and google_api_key is not None

    def stream(self, prompt):
        """Stream response from Gemini"""
        if not self.available:
            yield "Google Gemini API không khả dụng. Vui lòng kiểm tra cấu hình."
            return
            
        try:
            response = genai.generate_text(
                model=f"models/{self.model_name}",
                prompt=prompt,
                temperature=self.temperature
            )
            # Tạo chunk với content attribute để tương thích
            chunk_obj = type('obj', (object,), {'content': response.result if hasattr(response, 'result') else str(response)})
            yield chunk_obj
        except Exception as e:
            yield f"Lỗi khi gọi Gemini API: {str(e)}"

    def invoke(self, prompt):
        """Single response from Gemini"""
        if not self.available:
            return type('obj', (object,), {'content': "Google Gemini API không khả dụng"})
            
        try:
            response = genai.generate_text(
                model=f"models/{self.model_name}",
                prompt=prompt,
                temperature=self.temperature
            )
            return type('obj', (object,), {'content': response.result if hasattr(response, 'result') else str(response)})
        except Exception as e:
            return type('obj', (object,), {'content': f"Lỗi: {str(e)}"})

# Google Gemini models (nếu có API key)
if genai and google_api_key:
    gemini_pro = GoogleGenerativeAIWrapper("text-bison-001", temperature=0.7)  # Dùng model legacy
    gemini_flash_lite = GoogleGenerativeAIWrapper("text-bison-001", temperature=0.7)
else:
    # Fallback models
    class DummyModel:
        def stream(self, prompt):
            yield type('obj', (object,), {'content': "Google API key chưa được cấu hình"})
        def invoke(self, prompt):
            return type('obj', (object,), {'content': "Google API key chưa được cấu hình"})
    
    gemini_pro = DummyModel()
    gemini_flash_lite = DummyModel()

# DeepSeek
if deepseek_api_key:
    deepseek_chat = ChatOpenAI(
        model="deepseek-chat",          
        temperature=0.7,
        api_key=deepseek_api_key,
        base_url="https://api.deepseek.com/v1",
    )

    deepseek_reasoner = ChatOpenAI(
        model="deepseek-reasoner",         
        temperature=0.7,
        api_key=deepseek_api_key,
        base_url="https://api.deepseek.com/v1",
    )
else:
    # Fallback models
    class DummyModel:
        def stream(self, prompt):
            yield type('obj', (object,), {'content': "DeepSeek API key chưa được cấu hình"})
        def invoke(self, prompt):
            return type('obj', (object,), {'content': "DeepSeek API key chưa được cấu hình"})
    
    deepseek_chat = DummyModel()
    deepseek_reasoner = DummyModel()

# Grok (xAI)
if grok_api_key:
    grok_chat = ChatOpenAI(
        model="grok-2-latest",
        temperature=0.7,
        api_key=grok_api_key,
        base_url="https://api.x.ai/v1",
    )
else:
    # Fallback model
    class DummyModel:
        def stream(self, prompt):
            yield type('obj', (object,), {'content': "Grok API key chưa được cấu hình"})
        def invoke(self, prompt):
            return type('obj', (object,), {'content': "Grok API key chưa được cấu hình"})
    
    grok_chat = DummyModel()

# Dictionary để chọn model theo tên
models = {
    "google": gemini_pro,
    "gemini-pro": gemini_pro,
    "gemini-flash": gemini_flash_lite,
    "deepseek-chat": deepseek_chat,
    "deepseek-reasoner": deepseek_reasoner,
    "grok-2": grok_chat,
}

# # ✅ Test code
# if __name__ == "__main__":
#     print("Danh sách models khả dụng:", list(models.keys()))

#     try:
#         print("\n--- Test Gemini 2.5 Flash Lite ---")
#         res = models["gemini-flash-lite"].invoke("Xin chào, bạn có hoạt động không?")
#         print("Kết quả:", res.content if hasattr(res, "content") else res)
#     except Exception as e:
#         print("❌ Lỗi khi gọi gemini-2.5-flash-lite:", e)
