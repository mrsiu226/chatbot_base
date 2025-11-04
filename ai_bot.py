from flask import Flask, request, Response, stream_with_context, redirect, session, jsonify, Blueprint
from dotenv import load_dotenv
from model import models
from data.import_data import insert_message
from data.get_history import get_latest_messages, get_all_messages
from data.embed_messages import embedder
from utils.jwt_helper import jwt_required
import os, json, requests, sys, psycopg2
from psycopg2.extras import RealDictCursor



sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.jwt_helper import generate_jwt_token

# ---------------- CONFIG ----------------
load_dotenv()
LOCAL_DB_URL = os.getenv("POSTGRES_URL")

def get_conn():
    return psycopg2.connect(LOCAL_DB_URL, cursor_factory=RealDictCursor)
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
    """Truy vấn tương tự như Supabase RPC match_embeddings"""
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        sql = """
        SELECT text, sheet_name, column_name,
                1 - (embedding <=> %s::vector) AS similarity
        FROM "whoisme"."embeddings"
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """
        cur.execute(sql, (query_vector, query_vector, top_k))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            return "Không tìm thấy ngữ cảnh liên quan."

        context_text = "\n".join([
            f"- {r['text']} (sheet: {r['sheet_name']}, col: {r['column_name']})"
            for r in rows
        ])
        return context_text

    except Exception as e:
        print(f"Lỗi khi truy vấn embeddings: {e}")
        return "Không thể truy xuất ngữ cảnh."


def build_prompt(user_msg, short_term_context, long_term_context):
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
    model_key = data.get("model", "gemini-flash-lite")

    if not user_msg:
        return Response("Message không được để trống", status=400)

    llm = models.get(model_key)
    if not llm:
        return Response(f"Model '{model_key}' không hợp lệ", status=400)

    user_id = session["user"]["id"]

    query_vector = embedder.embed(user_msg).tolist()
    short_history = get_latest_messages(user_id, 8)
    short_term_context = "\n".join([
        f"User: {h['message']}\nBot: {h['reply']}"
        for h in reversed(short_history)
    ])

    long_term_context = match_embeddings(query_vector, top_k=5)
    prompt = build_prompt(user_msg, short_term_context, long_term_context)

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

# ---------------- VERIFY WHOISME TOKEN + CHAT ----------------
WHOISME_API_URL = "https://api.whoisme.ai/api/auth/verify-token"
whoisme_bp = Blueprint("whoisme", __name__)

@whoisme_bp.route("/v1/chat", methods=["POST"])
def whoisme_chat():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    whoisme_token = auth_header.split(" ")[1]
    try:
        res = requests.get(WHOISME_API_URL, headers={"Authorization": f"Bearer {whoisme_token}"})
        if res.status_code != 200:
            return jsonify({"error": "Invalid WhoIsMe token"}), 401
        data = res.json()
        user_info = data[0]["user"] if isinstance(data, list) else data.get("user", {})
        user_id = user_info.get("userId")
        email = user_info.get("email")

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM whoisme.users WHERE id = %s;", (str(user_id),))
        exists = cur.fetchone()
        if not exists:
            cur.execute(
                """
                INSERT INTO whoisme.users (id, email, password_hash, source)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (email) DO NOTHING;
                """,
                (str(user_id), email, "whoisme", "whoisme.ai")
            )
            conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        return jsonify({"error": f"WhoIsMe token verification failed: {str(e)}"}), 500

    payload = request.json or {}
    user_msg = payload.get("message", "").strip()
    session_id = payload.get("session_id", None)
    model_key = payload.get("model", "gemini-flash-lite")

    if not user_msg:
        return jsonify({"error": "Message không được để trống"}), 400

    llm = models.get(model_key)
    if not llm:
        return jsonify({"error": "Model không hợp lệ"}), 400

    short_history = get_latest_messages(user_id, session_id=session_id, limit=8)
    short_term_context = "\n".join([f"User: {h['message']}\nBot: {h['reply']}" for h in reversed(short_history)])
    query_vector = embedder.embed(user_msg).tolist()
    long_term_context = match_embeddings(query_vector, top_k=5)
    prompt = build_prompt(user_msg, short_term_context, long_term_context)

    @stream_with_context
    def generate():
        buffer = ""
        try:
            for chunk in llm.stream(prompt):
                content = getattr(chunk, "content", "")
                if content:
                    buffer += content
                    yield content
            insert_message(user_id, user_msg, buffer, session_id=session_id)
        except Exception as e:
            yield f"\n[ERROR]: {str(e)}"

    return Response(generate(), mimetype="text/plain")


#=======GET HISTORY API FOR WHOISME =======
@whoisme_bp.route("/v1/history", methods=["POST"])
def whoisme_history():
    """Trả về lịch sử chat của user theo session_id (bắt buộc)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    whoisme_token = auth_header.split(" ")[1]

    try:
        res = requests.get(WHOISME_API_URL, headers={"Authorization": f"Bearer {whoisme_token}"})
        if res.status_code != 200:
            return jsonify({"error": "Invalid WhoIsMe token"}), 401

        data = res.json()
        user_info = data[0]["user"] if isinstance(data, list) else data.get("user", {})
        user_id = user_info.get("userId")
        if not user_id:
            return jsonify({"error": "Thiếu userId trong token"}), 400

        # --- Lấy session_id bắt buộc ---
        session_id = request.args.get("session_id") or request.json.get("session_id") if request.is_json else None
        if not session_id:
            return jsonify({"error": "Thiếu session_id"}), 400

        # --- Lọc tin nhắn theo session_id ---
        history = get_all_messages(user_id, session_id=session_id)
        return jsonify({
            "user_id": user_id,
            "session_id": session_id,
            "messages": history
        })

    except Exception as e:
        print(f"Lỗi khi lấy lịch sử: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
    
app.register_blueprint(whoisme_bp)

# ========== MAIN ==========
if __name__ == "__main__":
    app.run(debug=True)
