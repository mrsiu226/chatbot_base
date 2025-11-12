import re
import json
from pathlib import Path
from typing import Dict, Optional
from model import load_prompt_config

# ---------------- Load prompt JSON ----------------
PROMPT_CACHE = {}
INTENT_OPTIONS = [
    "greeting",
    "emotional_share",
    "knowledge_question",
    "decision_reflection",
    "casual_chat"
]

def load_prompt_file(file_path: str = "whoisme_layered_advanced_v1.json") -> dict:
    global PROMPT_CACHE
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f).get("data", {})
        PROMPT_CACHE = {
            "layers": data.get("layers", {}),
            "userPromptFormat": data.get("userPromptFormat", "User said: {{content}}")
        }
        return PROMPT_CACHE


# ---------------- 1️⃣ Classification ----------------
def classify_user_message(user_msg: str) -> str:
    """
    Robust intent classifier: try multiple model interfaces, fallback to simple heuristic.
    """
    prompt = f"""
Bạn là một hệ thống phân loại ý định của người dùng cho chatbot.
Chỉ trả về 1 trong các giá trị sau, không thêm gì khác:
{', '.join(INTENT_OPTIONS)}

User message:
\"\"\"{user_msg}\"\"\"

Intent:
"""
    try:
        model = load_prompt_config()
        # try common interfaces safely
        if hasattr(model, "ChatCompletion") and hasattr(model.ChatCompletion, "create"):
            response = model.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": "Bạn là bộ phân loại intent chính xác."},
                        {"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=10,
            )
            intent = getattr(response.choices[0].message, "content", "").strip()
        elif hasattr(model, "chat") or hasattr(model, "Chat"):
            # example fallback - adapt to your model API
            resp = getattr(model, "chat", None) or getattr(model, "Chat", None)
            r = resp(prompt) if callable(resp) else None
            intent = (r or "").strip()
        else:
            raise AttributeError("Unsupported model interface for intent classification")
        if intent not in INTENT_OPTIONS:
            return "casual_chat"
        return intent
    except Exception as e:
        print(f"[Intent Classification Error]: {e}")
        # basic heuristic fallback
        low = user_msg.lower()
        if any(w in low for w in ["xin chào", "hello", "hi"]):
            return "greeting"
        if any(w in low for w in ["buồn", "mệt", "khó khăn", "mất động lực"]):
            return "emotional_share"
        return "casual_chat"


# ---------------- 2️⃣ Build layered prompt ----------------
def build_layered_prompt(
    user_msg: str,
    short_context: Optional[str] = "",
    long_context: Optional[str] = "",
    archetype: Optional[Dict[str, str]] = None
) -> str:
    """
    Combine layers from prompt.json into a full prompt.
    Skip archetype_layer if archetype is None.
    """
    if not PROMPT_CACHE:
        load_prompt_file()  

    prompt_parts = []

    for key, layer in PROMPT_CACHE.get("layers", {}).items():
        if key.lower().startswith("archetype") and not archetype:
            continue

        content = layer.get("content", "")
        if archetype:
            for k, v in archetype.items():
                content = content.replace(f"%{k}%", v)
        else:
            content = re.sub(r"%\w+%", "", content)
        prompt_parts.append(content)

    # Add context
    context_summary = f"[Short-term Context]\n{short_context or 'Không có lịch sử gần đây'}\n"
    context_summary += f"[Long-term Context]\n{long_context or 'Không có dữ liệu'}"

    # User prompt
    intent = classify_user_message(user_msg)
    user_prompt = PROMPT_CACHE["userPromptFormat"].replace("{{content}}", user_msg)
    user_prompt = user_prompt.replace("{{intent}}", intent)
    user_prompt = user_prompt.replace("{{context_summary}}", context_summary)

    prompt_parts.append(user_prompt)

    return "\n\n".join(prompt_parts)
