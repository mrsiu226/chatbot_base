from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# Lấy API key
google_api_key = os.getenv("GOOGLE_API_KEY")
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
grok_api_key = os.getenv("GROK_API_KEY")

# Google Gemini
gemini_flash = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.7,
    google_api_key=google_api_key,
)

gemini_pro = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    temperature=0.7,
    google_api_key=google_api_key,
)

gemini_flash_lite = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    temperature=0.7,
    google_api_key=google_api_key,
)

# DeepSeek
deepseek_chat = ChatOpenAI(
    model="deepseek-v3.2-exp",
    temperature=0.7,
    api_key=deepseek_api_key,
    base_url="https://api.deepseek.com/v1",
)

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

models = {
    "gemini-flash": {"provider": "google", "model": gemini_flash},
    "gemini-pro": {"provider": "google", "model": gemini_pro},
    "gemini-flash-lite": {"provider": "google", "model": gemini_flash_lite},
    "deepseek-chat": {"provider": "deepseek", "model": deepseek_chat},
    "grok-2": {"provider": "grok", "model": grok_chat},
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