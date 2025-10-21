from langchain_openai import ChatOpenAI
import os
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

# Google models (tertiary - disabled for now due to timeout issues)
class DummyModel:
    def stream(self, prompt):
        yield type('obj', (object,), {'content': "Google models tạm thời disabled do timeout issues"})
    def invoke(self, prompt):
        return type('obj', (object,), {'content': "Google models tạm thời disabled do timeout issues"})

gemini_flash = DummyModel()
gemini_pro = DummyModel()
gemini_flash_lite = DummyModel()

# Dictionary để chọn model theo tên - ưu tiên Grok (vì DeepSeek hết credit)
models = {
    "grok-2": grok_chat,
    "deepseek-chat": deepseek_chat,
    "deepseek-reasoner": deepseek_reasoner,
    "gemini-flash": grok_chat,  # Fallback to Grok
    "gemini-pro": grok_chat,    # Fallback to Grok 
    "gemini-flash-lite": grok_chat,  # Fallback to Grok
    # Aliases
    "google": grok_chat,   # Fallback to Grok
    "gemini": grok_chat,   # Fallback to Grok
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