from flask import Flask, request, Response, stream_with_context, redirect, session, jsonify, Blueprint
from dotenv import load_dotenv
from model import models
from data.import_data import insert_message
from data.get_history import get_latest_messages, get_all_messages, get_long_term_context
from data.embed_messages import embedder
from utils.jwt_helper import generate_jwt_token, jwt_required
import os, json, requests, sys, psycopg2, re, time, threading
from psycopg2.extras import RealDictCursor
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

# ---------------- CONFIG ----------------
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
load_dotenv()
LOCAL_DB_URL = os.getenv("POSTGRES_URL")

def get_conn():
    return psycopg2.connect(LOCAL_DB_URL, cursor_factory=RealDictCursor)

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = "super-secret-key"

PROMPT_CACHE = {
    "systemPrompt": "",
    "userPromptFormat": "",
    "updatedAt": None,
    "timestamp": 0,
}
PROMPT_API_URL = "https://prompt.whoisme.ai/api/public/prompt/prompt_chatbot"

# ========== BLUEPRINT LOGIN ==========
from login.register import register_bp
from login.login import login_bp
app.register_blueprint(register_bp)
app.register_blueprint(login_bp)

# ------------------------------------------------------------
# ------------------------ ROUTES -----------------------------
# ------------------------------------------------------------

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
    return jsonify(get_all_messages(user_id))

# ------------------------------------------------------------
# ---------------------- HELPER FUNCS -------------------------
# ------------------------------------------------------------

def match_embeddings(query_vector, top_k=5):
    """Truy vấn tương tự như Supabase RPC match_embeddings."""
    try:
        if isinstance(query_vector, (list, tuple)):
            vec_str = "[" + ",".join(str(float(x)) for x in query_vector) + "]"
        else:
            vec_str = str(query_vector)

        with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT text, sheet_name, column_name,
                        1 - (embedding <=> %s::vector) AS similarity
                FROM "whoisme"."embeddings"
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
                """,
                (vec_str, vec_str, int(top_k)),
            )
            rows = cur.fetchall()

        if not rows:
            return "Không tìm thấy ngữ cảnh liên quan."

        return "\n".join(
            f"- {r['text']} (sheet: {r['sheet_name']}, col: {r['column_name']})"
            for r in rows
        )

    except Exception as e:
        print(f"[ERROR match_embeddings]: {e}")
        return "Không thể truy xuất ngữ cảnh."

def fetch_prompt_from_api():
    """
    Gọi API lấy prompt mới nhất.
    """
    resp = requests.get(PROMPT_API_URL, timeout=5)
    resp.raise_for_status()
    data = resp.json().get("data", {})
    return {
        "systemPrompt": data.get("systemPrompt", ""),
        "userPromptFormat": data.get("userPromptFormat", ""),
        "updatedAt": data.get("updatedAt"),
    }

def background_prompt_updater(interval=300):
    """
    Thread nền — kiểm tra định kỳ xem prompt có thay đổi không.
    Nếu có, update lại cache.
    """
    while True:
        try:
            new_data = fetch_prompt_from_api()
            if new_data["updatedAt"] != PROMPT_CACHE.get("updatedAt"):
                PROMPT_CACHE.update(new_data)
                PROMPT_CACHE["timestamp"] = time.time()
                print(f"[Prompt Updated] at {new_data['updatedAt']}")
        except Exception as e:
            print(f"[Prompt Fetch Error]: {e}")
        time.sleep(interval)

threading.Thread(target=background_prompt_updater, daemon=True).start()

def get_cached_prompt():
    """
    Lấy prompt từ cache (đọc cực nhanh, không gọi API).
    """
    if PROMPT_CACHE["systemPrompt"]:
        return PROMPT_CACHE["systemPrompt"], PROMPT_CACHE["userPromptFormat"]
    # Nếu cache rỗng (lần đầu chạy app) → fetch ngay
    try:
        data = fetch_prompt_from_api()
        PROMPT_CACHE.update(data)
        PROMPT_CACHE["timestamp"] = time.time()
        return data["systemPrompt"], data["userPromptFormat"]
    except Exception as e:
        print(f"[Prompt Init Error]: {e}")
        return "[System Prompt fallback]", "User said: {{content}}"

def build_prompt(user_msg, short_term_context, long_term_context, knowledge, personality=None):
    """
    Build prompt động — đọc từ cache (đã auto reload).
    """
    system_prompt, user_prompt_format = get_cached_prompt()

    if personality:
        for key, val in personality.items():
            system_prompt = system_prompt.replace(f"%{key}%", str(val))
            user_prompt_format = user_prompt_format.replace(f"%{key}%", str(val))
    else:
        system_prompt = re.sub(r"%\w+%", "", system_prompt)
        user_prompt_format = re.sub(r"%\w+%", "", user_prompt_format)

    # Format user prompt
    user_prompt = user_prompt_format.replace("{{content}}", user_msg)

    # Ghép các context vào
    context_prompt = f"""

[Short-term Context]
{short_term_context or "Không có lịch sử gần đây"}

[Long-term Context]
{long_term_context or "Không có dữ liệu"}

[Knowledge]
{knowledge or "Không có kiến thức bổ sung"}
"""

    return f"{system_prompt}\n{context_prompt}\n\n{user_prompt}"

JWT_SECRET = os.getenv("JWT_SECRET", "jwt_secret_ABC123")
JWT_ALGORITHM = "HS256"

# def verify_whoisme_token(token):
#     WHOISME_API_URL = "https://api.whoisme.ai/api/auth/verify-token"
#     res = requests.get(WHOISME_API_URL, headers={"Authorization": f"Bearer {token}"})
#     if res.status_code != 200:
#         return None
#     data = res.json()
#     return data[0]["user"] if isinstance(data, list) else data.get("user", {})

# def upsert_whoisme_user(user_id, email):
#     try:
#         with get_conn() as conn, conn.cursor() as cur:
#             cur.execute("""
#                 INSERT INTO whoisme.users (id, email, password_hash, source)
#                 VALUES (%s, %s, %s, %s)
#                 ON CONFLICT (email) DO NOTHING;
#             """, (str(user_id), email, "whoisme", "whoisme.ai"))
#             conn.commit()
#     except Exception as e:
#         print(f"[ERROR upsert_whoisme_user]: {e}")

def verify_whoisme_token(token):
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_info = {
            "userId": decoded.get("userId") or decoded.get("id"),
            "email": decoded.get("email"),
            "tokenVersion": decoded.get("tokenVersion"),
        }
        if not user_info["userId"] or not user_info["email"]:
            raise ValueError("Thiếu thông tin userId hoặc email trong token")
        return user_info
    except ExpiredSignatureError:
        print("[verify_whoisme_token] Token đã hết hạn")
        return None
    except InvalidTokenError as e:
        print(f"[verify_whoisme_token] Token không hợp lệ: {e}")
        return None
    except Exception as e:
        print(f"[verify_whoisme_token] Lỗi khác: {e}")
        return None
    
def upsert_whoisme_user(user_id, email):
    if not user_id or not email:
        return
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO whoisme.users (id, email, password_hash, source)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email;
                """,
                (str(user_id), email, "whoisme", "whoisme.ai"),
            )
            conn.commit()
    except Exception as e:
        print(f"[ERROR upsert_whoisme_user]: {e}")

# ------------------------------------------------------------
# ---------------------- LOCAL CHAT ---------------------------
# ------------------------------------------------------------

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
    short_history = get_latest_messages(user_id, 5)
    short_term_context = "\n".join(f"User: {h['message']}\nBot: {h['reply']}" for h in reversed(short_history))
    long_term_context = get_long_term_context(user_id, user_msg, top_k=3)
    knowledge = match_embeddings(query_vector, top_k=5)
    prompt = build_prompt(user_msg, short_term_context, long_term_context, knowledge)

    @stream_with_context
    def generate():
        buffer = ""
        start_time = time.perf_counter()
        try:
            for chunk in llm.stream(prompt):
                content = getattr(chunk, "content", "")
                if content:
                    buffer += content
                    yield content
            end_time = time.perf_counter()
            elapsed = round(end_time - start_time, 3)  # thời gian chạy model (giây)
            insert_message(user_id, user_msg, buffer, time_spent=elapsed)
        except Exception as e:
            yield f"\n[ERROR]: {str(e)}"

    return Response(generate(), mimetype="text/plain")

# ------------------------------------------------------------
# ---------------------- WHOISME API --------------------------
# ------------------------------------------------------------

whoisme_bp = Blueprint("whoisme", __name__)

#=========API to chat with WhoIsMe==========

@whoisme_bp.route("/v1/chat", methods=["POST"])
def whoisme_chat():
    start_total = time.perf_counter()
    timing = {}

    def mark(label):
        timing[label] = round(time.perf_counter() - start_total, 3)

    try:
        # ==== AUTH ====
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header.split(" ")[1]
        mark("got_header")

        user_info = verify_whoisme_token(token)
        if not user_info:
            return jsonify({"error": "Invalid WhoIsMe token"}), 401
        user_id, email = user_info.get("userId"), user_info.get("email")
        upsert_whoisme_user(user_id, email)
        mark("verified_token")

        # ==== PAYLOAD ====
        payload = request.json or {}
        user_msg = payload.get("message", "").strip()
        session_id = payload.get("session_id")
        model_key = payload.get("model", "gemini-flash-lite")

        if not user_msg:
            return jsonify({"error": "Message không được để trống"}), 400
        llm = models.get(model_key)
        if not llm:
            return jsonify({"error": "Model không hợp lệ"}), 400
        mark("parsed_payload")

        # ==== BUILD CONTEXT ====
        query_vector = embedder.embed(user_msg).tolist()
        short_history = get_latest_messages(user_id, session_id=session_id, limit=5)
        short_term_context = "\n".join(
            f"User: {h['message']}\nBot: {h['reply']}" for h in reversed(short_history)
        )
        long_term_context = get_long_term_context(user_id, user_msg, session_id=session_id, top_k=3)
        knowledge = match_embeddings(query_vector, top_k=5)
        prompt = build_prompt(user_msg, short_term_context, long_term_context, knowledge)
        mark("context_ready")

        # ==== CALL LLM ====
        start_llm = time.perf_counter()
        response = llm.invoke(prompt)
        end_llm = time.perf_counter()
        elapsed_llm = round(end_llm - start_llm, 3)
        mark("llm_done")

        full_reply = getattr(response, "content", "") if response else ""

        # ==== SAVE TO DB ====
        insert_message(user_id, user_msg, full_reply, session_id=session_id, time_spent=elapsed_llm)
        mark("db_inserted")

        total_elapsed = round(time.perf_counter() - start_total, 3)

        print(
            f"[TIMING /v1/chat] total={total_elapsed}s "
            f"| token={timing.get('verified_token', 0)}s "
            f"| context={timing.get('context_ready', 0)}s "
            f"| llm={elapsed_llm}s "
            f"| db={round(time.perf_counter() - end_llm, 3)}s "
            f"| detail={timing}",
            flush=True
        )

        return jsonify({
            "user_id": user_id,
            "session_id": session_id,
            "model": model_key,
            "elapsed_total": total_elapsed,
            "elapsed_llm": elapsed_llm,
            "timing": timing,
            "message": [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": full_reply}
            ]
        })

    except Exception as e:
        print(f"[ERROR whoisme_chat]: {e}", flush=True)
        return jsonify({"error": str(e)}), 500

#=========API to hide chat history (soft delete)==========
@whoisme_bp.route("/v1/hidden", methods=["POST"])
def whoisme_hidden_history():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ")[1]
    user_info = verify_whoisme_token(token)
    if not user_info:
        return jsonify({"error": "Invalid WhoIsMe token"}), 401

    user_id = user_info.get("userId")
    session_id = (request.json or {}).get("session_id")
    if not session_id:
        return jsonify({"error": "Thiếu session_id"}), 400

    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                UPDATE whoisme.messages
                SET is_deleted = TRUE
                WHERE user_id = %s AND session_id = %s;
            """, (str(user_id), str(session_id)))
            conn.commit()
        return jsonify({
            "session_id": session_id, 
            "user_id": user_id
            })
    except Exception as e:
        print(f"[ERROR hidden_history]: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
    

#==========Get API to get list of sessions==========  

@whoisme_bp.route("/v1/sessions", methods=["POST"])
def whoisme_sessions():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ")[1]
    user_info = verify_whoisme_token(token)
    if not user_info:
        return jsonify({"error": "Invalid WhoIsMe token"}), 401

    user_id = user_info.get("userId") or user_info.get("user_id")
    if not user_id:
        return jsonify({"error": "Cannot determine user id from token"}), 401

    data = request.get_json(silent=True) or {}
    limit = int(data.get("limit", 8))
    offset = int(data.get("offset", 0))

    try:
        with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                WITH latest_sessions AS (
                    SELECT 
                        session_id,
                        MAX(created_at) AS last_time
                    FROM whoisme.messages
                    WHERE user_id = %s
                        AND is_deleted = FALSE
                        AND session_id IS NOT NULL
                    GROUP BY session_id
                    ORDER BY MAX(created_at) DESC
                    LIMIT %s OFFSET %s
                )
                SELECT 
                    m.session_id,
                    MIN(m.created_at) AS started_at,
                    (ARRAY_AGG(m.message ORDER BY m.created_at ASC))[1] AS first_message,
                    COUNT(*) AS total_messages,
                    MAX(m.created_at) AS last_time
                FROM whoisme.messages m
                JOIN latest_sessions ls ON m.session_id = ls.session_id
                WHERE m.user_id = %s
                    AND m.is_deleted = FALSE
                GROUP BY m.session_id
                ORDER BY last_time DESC;
            """

            cur.execute(query, (str(user_id), limit, offset, str(user_id)))
            rows = cur.fetchall()

            sessions = []
            for rec in rows:
                started = rec.get("started_at")
                if started is not None:
                    rec["started_at"] = (
                        started.isoformat() if hasattr(started, "isoformat") else str(started)
                    )

                rec["last_time"] = (
                    rec["last_time"].isoformat() if hasattr(rec["last_time"], "isoformat") else str(rec["last_time"])
                )
                rec["total_messages"] = int(rec.get("total_messages") or 0)
                rec["first_message"] = str(rec["first_message"]) if rec.get("first_message") else None
                sessions.append(rec)

        return jsonify({
            "user_id": user_id,
            "limit": limit,
            "offset": offset,
            "count": len(sessions),
            "sessions": sessions
        })

    except Exception as e:
        print(f"[ERROR whoisme_sessions]: {e}", flush=True)
        return jsonify({"error": "Internal server error"}), 500

app.register_blueprint(whoisme_bp)

# ------------------------------------------------------------
# -------------------------- MAIN -----------------------------
# ------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
