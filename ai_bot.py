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
    """
    Gọi RPC match_embeddings trong Supabase để tìm các đoạn văn gần nhất.
    """
    try:
        response = supabase.rpc("match_embeddings", {
            "query_embedding": query_vector,
            "match_count": top_k
        }).execute()

        results = response.data or []
        if not results:
            return "Không tìm thấy ngữ cảnh liên quan."
        
        # Ghép các đoạn text lại thành context
        context_text = "\n".join([
            f"- {r['text']} (sheet: {r['sheet_name']}, col: {r['column_name']})"
            for r in results
        ])
        return context_text

    except Exception as e:
        print(f"❌ Lỗi khi gọi match_embeddings: {e}")
        return "Không thể truy xuất ngữ cảnh."



def build_prompt(user_msg, short_term_context, long_term_context):
    """
    Xây dựng prompt đầy đủ với 3 lớp context:
    - short-term: hội thoại gần nhất
    - long-term: dữ liệu vector từ DB (qua RPC)
    - câu hỏi hiện tại
    """
    system_prompt = """Bạn là chatbot hỗ trợ tư vấn cá nhân hóa.
    - Dùng short-term context để giữ mạch hội thoại gần nhất.
    - Dùng long-term context để cung cấp thông tin nền từ dữ liệu vector.
    - Nếu có mâu thuẫn thì ưu tiên short-term context.
    """
    context_prompt = f"""
    [Long-term context]
    {long_term_context if long_term_context else "Không có dữ liệu"}

    [Short-term context]
    {short_term_context if short_term_context else "Không có lịch sử gần đây"}
    """
    return f"{system_prompt}\n{context_prompt}\nUser: {user_msg}\nChatbot:"


# ========== MAIN CHAT ENDPOINT ==========

@app.route("/chat", methods=["POST"])
def chat():
    if not session.get("user"):
        return Response("Bạn chưa đăng nhập", status=401)

    data = request.json or {}
    user_msg = data.get("message", "").strip()
    provider = data.get("provider", "google")

    if not user_msg:
        return Response("Message không được để trống", status=400)

    llm = models.get(provider)
    if not llm:
        return Response(f"Provider {provider} không hợp lệ", status=400)

    user_id = session["user"]["id"]

    # --- B1: Sinh embedding cho user message ---
    query_vector = embedder.embed(user_msg).tolist()

    # --- B2: Lấy short-term context ---
    short_history = get_latest_messages(user_id, 8)
    short_term_context = "\n".join([
        f"User: {h['message']}\nBot: {h['reply']}"
        for h in reversed(short_history)
    ])

    # --- B3: Gọi RPC match_embeddings để tìm context gần nhất ---
    long_term_context = match_embeddings(query_vector, top_k=5)

    # --- B4: Ghép context + prompt ---
    prompt = build_prompt(user_msg, short_term_context, long_term_context)

    # --- B5: Stream phản hồi từ LLM ---
    @stream_with_context
    def generate():
        buffer = ""
        try:
            for chunk in llm.stream(prompt):
                if hasattr(chunk, "content") and chunk.content:
                    buffer += chunk.content
                    yield chunk.content

            # Sau khi trả lời xong -> lưu vào DB
            insert_message(user_id, user_msg, buffer)

        except Exception as e:
            yield f"\n[ERROR]: {str(e)}"

    return Response(generate(), mimetype="text/plain")


# ========== MAIN ==========

if __name__ == "__main__":
    app.run(debug=True)
