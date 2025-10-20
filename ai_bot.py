from flask import Flask, request, Response, stream_with_context, redirect, session, jsonify
from dotenv import load_dotenv
from model import models
from data.import_data import insert_message
from data.get_history import get_latest_messages, get_all_messages
from data.embed_messages import embedder
from supabase import create_client
import os, json

# ---------------- CONFIG ----------------
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = "super-secret-key"

# ========== BLUEPRINT LOGIN ==========
from login.register import register_bp
from login.login import login_bp  
app.register_blueprint(register_bp)
app.register_blueprint(login_bp)

# ========== ROUTES ==========

@app.route("/")
def index():
    if not session.get("user"):
        return redirect("/login-ui")
    return redirect("/chatbot")

@app.route("/chatbot")
def chatbot():
    if not session.get("user"):
        return redirect("/login-ui")
    return app.send_static_file("chatbot_ui.html")

@app.route("/register-ui")
def register_ui():
    return app.send_static_file("register.html")

@app.route("/login-ui")
def login_ui():
    return app.send_static_file("login.html")

@app.route("/history", methods=["POST"])
def history():
    if not session.get("user"):
        return jsonify([]), 401
    user_id = session["user"]["id"]
    history = get_all_messages(user_id)
    return jsonify(history)

# ========== HELPER FUNCTIONS ==========

def match_embeddings(query_vector, top_k=5):
    """Gọi RPC match_embeddings trong Supabase để tìm các đoạn văn gần nhất."""
    try:
        response = supabase.rpc("match_embeddings", {
            "query_embedding": query_vector,
            "match_count": top_k
        }).execute()

        results = response.data or []
        if not results:
            return "Không tìm thấy ngữ cảnh liên quan."

        context_text = "\n".join([
            f"- {r['text']} (sheet: {r['sheet_name']}, col: {r['column_name']})"
            for r in results
        ])
        return context_text

    except Exception as e:
        print(f"Lỗi khi gọi match_embeddings: {e}")
        return "Không thể truy xuất ngữ cảnh."

def build_prompt(user_msg, short_term_context, long_term_context):
    """Ghép prompt với short-term + long-term context."""
    system_prompt = """Bạn là chatbot tư vấn cá nhân hóa.
- Dùng short-term context để giữ mạch hội thoại.
- Dùng long-term context để bổ sung kiến thức nền.
- Nếu có mâu thuẫn, ưu tiên short-term context.
"""
    context_prompt = f"""
[Long-term context]
{long_term_context or "Không có dữ liệu"}

[Short-term context]
{short_term_context or "Không có lịch sử gần đây"}
"""
    return f"{system_prompt}\n{context_prompt}\nUser: {user_msg}\nChatbot:"

# ========== MAIN CHAT ENDPOINT ==========

@app.route("/chat", methods=["POST"])
def chat():
    if not session.get("user"):
        return Response("Bạn chưa đăng nhập", status=401)

    data = request.json or {}
    user_msg = data.get("message", "").strip()
    model_key = data.get("model", "gemini-flash")  # mặc định model chính

    if not user_msg:
        return Response("Message không được để trống", status=400)

    # --- Lấy model từ danh sách ---
    model_entry = models.get(model_key)
    if not model_entry:
        return Response(f"Model '{model_key}' không hợp lệ", status=400)

    llm = model_entry["model"]
    user_id = session["user"]["id"]

    # --- Sinh embedding cho câu hỏi ---
    query_vector = embedder.embed(user_msg).tolist()

    # --- Lấy short-term context ---
    short_history = get_latest_messages(user_id, 8)
    short_term_context = "\n".join([
        f"User: {h['message']}\nBot: {h['reply']}"
        for h in reversed(short_history)
    ])

    # --- Lấy long-term context ---
    long_term_context = match_embeddings(query_vector, top_k=5)

    # --- Xây prompt hoàn chỉnh ---
    prompt = build_prompt(user_msg, short_term_context, long_term_context)

    # --- Stream phản hồi ---
    @stream_with_context
    def generate():
        buffer = ""
        try:
            for chunk in llm.stream(prompt):
                content = getattr(chunk, "content", "")
                if content:
                    buffer += content
                    yield content
            insert_message(user_id, user_msg, buffer)
        except Exception as e:
            yield f"\n[ERROR]: {str(e)}"

    return Response(generate(), mimetype="text/plain")

# ========== MAIN ==========
if __name__ == "__main__":
    app.run(debug=True)
