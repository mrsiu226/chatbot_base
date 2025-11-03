from flask import Flask, request, Response, stream_with_context, redirect, session, jsonify, Blueprint
from dotenv import load_dotenv
from model import models
from data.import_data import insert_message
from data.get_history import get_latest_messages, get_all_messages
from data.embed_messages import embedder
from supabase import create_client
from utils.jwt_helper import jwt_required
import os, json, requests, sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.jwt_helper import generate_jwt_token

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
Hãy trả lời theo phong cách của người dùng.
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
    model_key = data.get("model", "gemini-flash-lite")  # Default: nhanh nhất

    if not user_msg:
        return Response("Message không được để trống", status=400)

    # --- Lấy model từ danh sách ---
    model_entry = models.get(model_key)
    if not model_entry:
        return Response(f"Model '{model_key}' không hợp lệ", status=400)

    # model_entry đã là object model trực tiếp, không cần ["model"]
    llm = model_entry
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

# VERIFY TOKEN TỪ WHOISME.AI 
WHOISME_API_URL = "https://api.whoisme.ai/api/auth/verify-token"

verify_bp = Blueprint("verify", __name__)

@verify_bp.route("/api/verify-whoisme", methods=["POST"])
def verify_whoisme_token():
    """Xác thực token từ WhoIsMe, lưu user vào DB, và trả về JWT token của hệ thống"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ")[1]

    try:
        res = requests.get(WHOISME_API_URL, headers={"Authorization": f"Bearer {token}"})
        if res.status_code != 200:
            return jsonify({"valid": False, "error": "Invalid token"}), 401

        data = res.json()
        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        user = data.get("user", {})
        user_id = user.get("userId")
        email = user.get("email")

        if not user_id or not email:
            return jsonify({"error": "Thiếu thông tin user"}), 400

        existing = supabase.table("users_aibot").select("id").eq("id", user_id).execute()
        if not existing.data:
            supabase.table("users_aibot").insert({
                "id": user_id,
                "email": email,
                "password_hash": "whoisme",  # No password for WhoIsMe users   
                "source": "whoisme.ai"
            }).execute()

        jwt_token = generate_jwt_token(user_id, email)

        return jsonify({
            "success": True,
            "message": "Xác thực thành công",
            "user": {
                "id": user_id,
                "email": email
            },
            "access_token": jwt_token,
            "token_type": "bearer"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

#========= API ==========
API_KEY = os.getenv("CHATBOT_API_KEY")

@app.route("/v1/chat", methods=["POST"])
@jwt_required
def chat_api():
    current_user = request.current_user
    user_id = current_user["user_id"]
    data = request.json or {}
    user_msg = data.get("message", "").strip()
    model_key = data.get("model", "gemini-flash-lite")

    if not user_msg:
        return Response("Message không được để trống", status=400)

    llm = models.get(model_key)
    if not llm:
        return Response(f"Model '{model_key}' không hợp lệ", status=400)

    # --- Short-term context ---
    short_history = get_latest_messages(user_id, 8)
    short_term_context = "\n".join([
        f"User: {h['message']}\nBot: {h['reply']}"
        for h in reversed(short_history)
    ])

    # --- Long-term context ---
    query_vector = embedder.embed(user_msg).tolist()
    long_term_context = match_embeddings(query_vector, top_k=5)

    # --- Build prompt ---
    prompt = build_prompt(user_msg, short_term_context, long_term_context)

    # --- Stream plain text (giống /chat) ---
    @stream_with_context
    def generate():
        buffer = ""
        try:
            for chunk in llm.stream(prompt):
                content = getattr(chunk, "content", "")
                if content:
                    buffer += content
                    yield content
            # Lưu lịch sử chat
            insert_message(user_id, user_msg, buffer)
        except Exception as e:
            yield f"\n[ERROR]: {str(e)}"

    return Response(generate(), mimetype="text/plain")

# ========== MAIN ==========
if __name__ == "__main__":
    app.run(debug=True)