import os, sys, re, time, threading, requests
from flask import Flask, request, Response, stream_with_context, session, redirect, jsonify, Blueprint
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
import psycopg2
from cachetools import TTLCache
from model import load_prompt_config
from data.get_history import get_latest_messages, get_long_term_context
from data.import_data import insert_message
from data.embed_messages import embedder

try:
    from utils.jwt_helper import verify_whoisme_token
except Exception:
    import jwt
    def verify_whoisme_token(token: str):
        if not token: return None
        try:
            secret = os.getenv("JWT_SECRET", "jwt_secret_ABC123")
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            return {"userId": payload.get("userId") or payload.get("user_id"), "email": payload.get("email")}
        except Exception as e:
            print(f"[verify_whoisme_token fallback error]: {e}")
            return None

# ---------------- CONFIG ----------------
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
load_dotenv()
LOCAL_DB_URL = os.getenv("POSTGRES_URL")
PROMPT_API_URL = "https://prompt.whoisme.ai/api/public/prompt/chatgpt_prompt_chatbot"

# ---------------- FLASK ----------------
app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = os.getenv("FLASK_SECRET", "super-secret-key")

# ---------------- CACHE ----------------
SHORT_TERM_CACHE = TTLCache(maxsize=5000, ttl=300)
LONG_TERM_CACHE = TTLCache(maxsize=5000, ttl=300)
PROMPT_CACHE = {"systemPrompt": "", "userPromptFormat": "", "updatedAt": None, "timestamp": 0}

# ========== BLUEPRINT LOGIN ==========
from login.register import register_bp
from login.login import login_bp
app.register_blueprint(register_bp)
app.register_blueprint(login_bp)

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

    try:
        data = get_long_term_context(user_id)
        # đảm bảo luôn là list of dict
        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            data = []
        # optional: filter dict only
        data = [d for d in data if isinstance(d, dict)]
    except Exception as e:
        print(f"[ERROR history]: {e}")
        data = []

    return jsonify(data)

# ---------------- PROMPT CACHE ----------------
def fetch_prompt_from_api():
    try:
        resp = requests.get(PROMPT_API_URL, timeout=5)
        data = resp.json().get("data", {})
        return {
            "systemPrompt": data.get("systemPrompt", ""),
            "userPromptFormat": data.get("userPromptFormat", ""),
            "updatedAt": data.get("updatedAt"),
        }
    except Exception as e:
        print(f"[Prompt Fetch Error]: {e}")
        return PROMPT_CACHE

def background_prompt_updater(interval=300):
    while True:
        try:
            new_data = fetch_prompt_from_api()
            if new_data["updatedAt"] != PROMPT_CACHE.get("updatedAt"):
                PROMPT_CACHE.update(new_data)
                PROMPT_CACHE["timestamp"] = time.time()
                print(f"[Prompt Updated] at {new_data['updatedAt']}")
        except Exception as e:
            print(f"[Prompt Updater Error]: {e}")
        time.sleep(interval)

threading.Thread(target=background_prompt_updater, daemon=True).start()

def get_cached_prompt():
    if PROMPT_CACHE["systemPrompt"]:
        return PROMPT_CACHE["systemPrompt"], PROMPT_CACHE["userPromptFormat"]
    data = fetch_prompt_from_api()
    PROMPT_CACHE.update(data)
    PROMPT_CACHE["timestamp"] = time.time()
    return data.get("systemPrompt", ""), data.get("userPromptFormat", "User said: {{content}}")


# ---------------- CONTEXT HELPERS ----------------
def get_short_term(user_id, session_id=None, limit=5):
    key = f"{user_id}_{session_id or 'global'}"
    if key in SHORT_TERM_CACHE:
        print(f"[CACHE HIT] short_term: {key}")
        return SHORT_TERM_CACHE[key]
    print(f"[CACHE MISS] short_term: {key}")
    messages = get_latest_messages(user_id, session_id, limit)
    SHORT_TERM_CACHE[key] = messages
    return messages


def get_long_term(user_id, query, session_id=None, top_k=3):
    key = f"{user_id}_{session_id or 'global'}_{query}"
    if key in LONG_TERM_CACHE:
        print(f"[CACHE HIT] long_term: {key}")
        return LONG_TERM_CACHE[key]
    print(f"[CACHE MISS] long_term: {key}")
    context = get_long_term_context(user_id, query, session_id=session_id, top_k=top_k)
    LONG_TERM_CACHE[key] = context
    return context

def build_prompt(user_msg, short_term_context, long_term_context, personality=None):
    system_prompt, user_prompt_format = get_cached_prompt()

    if personality:
        for k, v in personality.items():
            system_prompt = system_prompt.replace(f"%{k}%", str(v))
            user_prompt_format = user_prompt_format.replace(f"%{k}%", str(v))
    else:
        system_prompt = re.sub(r"%\w+%", "", system_prompt)
        user_prompt_format = re.sub(r"%\w+%", "", user_prompt_format)

    user_prompt = user_prompt_format.replace("{{content}}", user_msg)

    context_prompt = f"""
[Short-term Context]
{short_term_context or 'Không có lịch sử gần đây'}

[Long-term Context]
{long_term_context or 'Không có dữ liệu'}
"""
    return f"{system_prompt}\n{context_prompt}\n\n{user_prompt}"


# ---------------- ASYNC DB ----------------
def async_embed_message(user_id, message, reply, session_id=None, time_spent=None):
    threading.Thread(target=lambda: insert_message(user_id, message, reply, session_id, time_spent), daemon=True).start()


# ---------------- BLUEPRINT ----------------
whoisme_bp = Blueprint("whoisme", __name__)

# ---------------- CHAT ----------------
@app.route("/chat", methods=["POST"])
def chat():
    if not session.get("user"):
        return Response("Bạn chưa đăng nhập", status=401)

    data = request.json or {}
    user_msg = data.get("message", "").strip()
    if not user_msg:
        return Response("Message không được để trống", status=400)

    user_id = session["user"]["id"]
    llm = load_prompt_config()
    if not llm:
        return Response("Model không hợp lệ", status=400)

    short_msgs = get_short_term(user_id, limit=5)
    short_ctx = "\n".join(f"User: {m['message']}\nBot: {m['reply']}" for m in reversed(short_msgs))
    long_ctx = get_long_term(user_id, user_msg, top_k=3)

    prompt = build_prompt(user_msg, short_ctx, long_ctx)

    @stream_with_context
    def generate():
        buf = ""
        start = time.perf_counter()
        try:
            for chunk in llm.stream(prompt):
                content = getattr(chunk, "content", "")
                if content:
                    buf += content
                    yield content
            elapsed = round(time.perf_counter() - start, 3)
            async_embed_message(user_id, user_msg, buf, time_spent=elapsed)
        except Exception as e:
            yield f"\n[ERROR]: {e}"

    return Response(generate(), mimetype="text/plain")


# ---------------- WHOISME /v1/chat ----------------
@whoisme_bp.route("/v1/chat", methods=["POST"])
def whoisme_chat():
    start_total = time.perf_counter()
    timing = {}
    def mark(label): timing[label] = round(time.perf_counter() - start_total, 3)

    try:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header.split(" ")[1]
        mark("got_header")

        user_info = verify_whoisme_token(token)
        if not user_info:
            return jsonify({"error": "Invalid WhoIsMe token"}), 401
        user_id = user_info["userId"]
        mark("verified_token")

        payload = request.json or {}
        user_msg = payload.get("message", "").strip()
        session_id = payload.get("session_id")
        if not user_msg:
            return jsonify({"error": "Message không được để trống"}), 400
        mark("parsed_payload")

        llm = load_prompt_config()
        if not llm:
            return jsonify({"error": "Model không hợp lệ"}), 400

        short_msgs = get_short_term(user_id, session_id=session_id, limit=5)
        short_ctx = "\n".join(f"User: {m['message']}\nBot: {m['reply']}" for m in reversed(short_msgs))
        long_ctx = get_long_term(user_id, user_msg, session_id=session_id, top_k=3)

        prompt = build_prompt(user_msg, short_ctx, long_ctx)
        mark("context_ready")

        start_llm = time.perf_counter()
        buffer = ""
        for chunk in llm.stream(prompt):
            content = getattr(chunk, "content", "")
            if content:
                buffer += content
        elapsed_llm = round(time.perf_counter() - start_llm, 3)
        mark("llm_done")

        async_embed_message(user_id, user_msg, buffer, session_id=session_id, time_spent=elapsed_llm)
        mark("db_inserted")
        total_elapsed = round(time.perf_counter() - start_total, 3)

        print(f"[TIMING /v1/chat] total={total_elapsed}s | detail={timing}", flush=True)

        return jsonify({
            "user_id": user_id,
            "session_id": session_id,
            "message": [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": buffer}
            ]
        })
    except Exception as e:
        print(f"[ERROR whoisme_chat]: {e}")
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
    
#=========API to get chat history==========
@whoisme_bp.route("/v1/history", methods=["POST"])
def whoisme_history():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ")[1]
    user_info = verify_whoisme_token(token)
    if not user_info:
        return jsonify({"error": "Invalid WhoIsMe token"}), 401

    user_id = user_info.get("userId")
    session_id = (request.args.get("session_id") or request.json.get("session_id")) if request.is_json else None
    if not session_id:
        return jsonify({"error": "Thiếu session_id"}), 400

    history = get_long_term_context(user_id, session_id=session_id)
    return jsonify({
        "user_id": user_id, 
        "session_id": session_id, 
        "messages": history
        })
    
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
