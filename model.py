from langchain_openai import ChatOpenAI
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

# ======================
# Load API keys
# ======================
google_api_key = os.getenv("GOOGLE_API_KEY")
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
grok_api_key = os.getenv("GROK_API_KEY")
openai_api_key = os.getenv("OPEN_API_KEY")

# ======================
# Base wrapper classes
# ======================
class ModelWrapper:
    def __init__(self, model, name, system_prompt=None):
        self.model = model
        self.name = name
        self.system_prompt = system_prompt

    def stream(self, prompt):
        try:
            for chunk in self.model.stream(prompt):
                yield chunk
        except Exception as e:
            yield type('obj', (object,), {'content': f"Error with {self.name}: {str(e)}"})

    def invoke(self, prompt):
        try:
            if self.system_prompt:
                if isinstance(prompt, list):
                    prompt = [{"role": "system", "content": self.system_prompt}] + prompt
                else:
                    prompt = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": str(prompt)}]
            return self.model.invoke(prompt)
        except Exception as e:
            return type('obj', (object,), {'content': f"Error with {self.name}: {str(e)}"})

# ======================
# Dummy fallback class
# ======================
class DummyModel:
    def __init__(self, msg="API key chưa được cấu hình"):
        self.msg = msg
    def stream(self, prompt):
        yield type('obj', (object,), {'content': self.msg})
    def invoke(self, prompt):
        return type('obj', (object,), {'content': self.msg})

# ======================
# Gemini wrapper
# ======================
class GeminiAPIWrapper:
    def __init__(self, model_name, api_key, temperature=0.7, max_output_tokens=2048):
        self.model_name = model_name
        self.api_key = api_key
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}"

    def _prepare_prompt(self, prompt):
        if isinstance(prompt, list):
            return "\n".join([msg.get("content", str(msg)) for msg in prompt])
        return str(prompt)

    def invoke(self, prompt):
        try:
            prompt_text = self._prepare_prompt(prompt)
            payload = {
                "contents": [{"parts": [{"text": prompt_text}]}],
                "generationConfig": {
                    "temperature": self.temperature,
                    "maxOutputTokens": self.max_output_tokens
                }
            }
            response = requests.post(
                f"{self.base_url}:generateContent?key={self.api_key}",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "Không có phản hồi từ Gemini")
                )
                return type('obj', (object,), {'content': text})
            return type('obj', (object,), {'content': f"Gemini API error {response.status_code}: {response.text[:80]}"})
        except Exception as e:
            return type('obj', (object,), {'content': f"Gemini error: {str(e)}"})

# ======================
# Các nhóm model
# ======================
def init_deepseek_models():
    if deepseek_api_key:
        return {
            "deepseek-chat": ModelWrapper(
                ChatOpenAI(
                    model="deepseek-chat", 
                    temperature=0.7,
                    api_key=deepseek_api_key, 
                    base_url="https://api.deepseek.com", 
                    timeout=30
                    ),
                "DeepSeek Chat"),
            "deepseek-reasoner": ModelWrapper(
                ChatOpenAI(
                    model="deepseek-reasoner", 
                    temperature=0.7,
                    api_key=deepseek_api_key, 
                    base_url="https://api.deepseek.com", 
                    timeout=30
                    ),
                "DeepSeek Reasoner")
        }
    return {
        "deepseek-chat": DummyModel("DeepSeek API key chưa được cấu hình"),
        "deepseek-reasoner": DummyModel("DeepSeek API key chưa được cấu hình")
    }

def init_grok_models():
    if grok_api_key:
        base = "https://api.x.ai/v1"
        return {
            "grok-2": ModelWrapper(
                ChatOpenAI(
                    model="grok-2-latest", 
                    temperature=0.7,
                    api_key=grok_api_key, 
                    base_url=base, 
                    timeout=30), 
                    "Grok 2"
                    ),
            "grok-3": ModelWrapper(
                ChatOpenAI(
                    model="grok-3-latest", 
                    temperature=0.7,
                    api_key=grok_api_key, 
                    base_url=base, 
                    timeout=30), 
                    "Grok 3"),
            "grok-4": ModelWrapper(
                ChatOpenAI(
                    model="grok-4-latest", 
                    temperature=0.7,
                    api_key=grok_api_key, 
                    base_url=base, 
                    timeout=30), 
                    "Grok 4"),
        }
    return {f"grok-{i}": DummyModel("Grok API key chưa được cấu hình") for i in [2, 3, 4]}

def init_gemini_models():
    if google_api_key:
        return {
            "gemini-flash": GeminiAPIWrapper(
                "gemini-2.5-flash", 
                google_api_key, 
                0.7
                ),

            "gemini-pro": GeminiAPIWrapper(
                "gemini-2.5-pro", 
                google_api_key, 
                0.7
                ),

            "gemini-flash-lite": GeminiAPIWrapper(
                "gemini-2.5-flash-lite",
                google_api_key, 
                0.7
                ),
        }
    return {k: DummyModel("Google API key chưa được cấu hình") for k in ["gemini-flash", "gemini-pro", "gemini-flash-lite"]}

def init_openai_models():
    if openai_api_key:
        gpt_configs = {
            "gpt-4o": dict(temperature=0.7, max_tokens=2048),
            "gpt-4o-mini": dict(temperature=0.6, max_tokens=1500),
            "gpt-5-mini": dict(temperature=0.7, max_tokens=2048),
            "gpt-5-nano": dict(temperature=0.8, max_tokens=1024)
        }
        wrappers = {}
        for name, cfg in gpt_configs.items():
            wrappers[name] = ModelWrapper(
                ChatOpenAI(
                    model=name,
                    temperature=cfg["temperature"],
                    max_tokens=cfg["max_tokens"],
                    api_key=openai_api_key,
                    timeout=30
                ),
                name
            )
        return wrappers
    return {k: DummyModel("OpenAI API key chưa được cấu hình") for k in ["gpt-4o", "gpt-4o-mini", "gpt-5-mini", "gpt-5-nano"]}

# ======================
# Combine all
# ======================
models = {
    **init_grok_models(),
    **init_deepseek_models(),
    **init_gemini_models(),
    **init_openai_models(),
}
models.update({
    "google": models.get("gemini-pro"),
    "gemini": models.get("gemini-pro"),
    "deepseek": models.get("deepseek-chat"),
    "gpt": models.get("gpt-4o"),
})

# ======================
# API CONFIG LOADER
# ======================
def load_prompt_config():

    url = "https://prompt.whoisme.ai/api/public/prompt/chatgpt_prompt_chatbot"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json().get("data", {})
        model_key = data.get("model", "gpt-4o")
        temperature = data.get("temperature", 0.7)
        max_tokens = data.get("maxTokens", 2001)
        top_p = data.get("topP", 1)
        freq_penalty = data.get("frequencyPenalty", 0)
        pres_penalty = data.get("presencePenalty", 0)

        model = models.get(model_key) or models.get("gpt-4o")
        print(f"🔧 Loaded prompt config: {model_key} ({temperature}, max={max_tokens})")

        # Nếu là OpenAI ChatOpenAI → tạo lại instance với config mới
        if isinstance(model, ModelWrapper) and isinstance(model.model, ChatOpenAI):
            model.model = ChatOpenAI(
                model=model_key,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=freq_penalty,
                presence_penalty=pres_penalty,
                api_key=openai_api_key,
                timeout=30
            )
        return model
    except Exception as e:
        print(f"Lỗi khi tải prompt config: {e}")
        return models.get("gpt-4o")

# ======================
# Test usage
# ======================
if __name__ == "__main__":
    print("Danh sách models khả dụng:")
    for k in models.keys():
        print("-", k)

    print("\n--- Load prompt_chatbot config ---")
    model = load_prompt_config()
    res = model.invoke("Xin chào! Bạn có thể giới thiệu về mình được không?")
    print("Phản hồi:", getattr(res, "content", res))
