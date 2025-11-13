import os, sys, re, time, threading, requests, traceback
from flask import Flask, request, Response, stream_with_context, session, redirect, jsonify, Blueprint
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
import psycopg2
from cachetools import TTLCache
from model import load_prompt_config
from data.get_history import get_latest_messages, get_long_term_context, get_full_history
from data.import_data import insert_message, get_conn
from data.embed_messages import embedder
from collections import defaultdict
import json
import threading
import hashlib
import numpy as np


def log_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    print("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)), flush=True)

sys.excepthook = log_exception

def to_serializable(obj):
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_serializable(v) for v in obj]
    if hasattr(obj, "model_name"):
        return getattr(obj, "model_name")
    if hasattr(obj, "model"):
        m = getattr(obj, "model")
        if isinstance(m, (str, int, float, bool)) or m is None:
            return m
        return str(m)
    # fallback to string
    try:
        return str(obj)
    except Exception:
        return f"<unserializable:{type(obj).__name__}>"
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
SHORT_TERM_CACHE = TTLCache(maxsize=5000, ttl=1800)  
LONG_TERM_CACHE = TTLCache(maxsize=5000, ttl=900)   
PROMPT_CACHE = {"systemPrompt": "", "userPromptFormat": "", "updatedAt": None, "timestamp": 0}

#-----------------RESPONSE CACHE----------------
# Response cache (tránh lặp câu quá nhanh)
class ResponseCache:
    def __init__(self, ttl=120, max_hits=1):
        self.cache = TTLCache(maxsize=5000, ttl=ttl)
        self.hits = defaultdict(int)
        self.max_hits = max_hits

    def get(self, user_id, session_id, message):
        key = f"{user_id}_{session_id or 'global'}_{hash(message)}"
        if key in self.cache and self.hits[key] < self.max_hits:
            self.hits[key] += 1
            print(f"[RESPONSE_CACHE HIT] {key} (hits={self.hits[key]})")
            return self.cache[key]
        return None

    def set(self, user_id, session_id, message, response):
        key = f"{user_id}_{session_id or 'global'}_{hash(message)}"
        self.cache[key] = response
        self.hits[key] = 0
        print(f"[RESPONSE_CACHE SET] {key}")

RESPONSE_CACHE = ResponseCache(ttl=120, max_hits=1)

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

@app.route("/health")
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Test database connection
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "healthy",
            "service": "chatbot_base",
            "database": "connected",
            "timestamp": None
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy", 
            "service": "chatbot_base",
            "database": "disconnected",
            "error": str(e),
            "timestamp": None
        }), 500

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
    data = get_long_term_context(user_id)

    if not isinstance(data, list):
        if data:  
            data = [data]
        else:
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
def get_short_term(user_id, session_id=None, limit=5, new_message=None, new_reply=None):
    key = f"{user_id}_{session_id or 'global'}"
    if key in SHORT_TERM_CACHE:
        messages = SHORT_TERM_CACHE[key]
        print(f"[CACHE HIT] short_term: {key}")
    else:
        print(f"[CACHE MISS] short_term: {key}")
        messages = get_latest_messages(user_id, session_id, limit)
        SHORT_TERM_CACHE[key] = messages
    if new_message is not None and new_reply is not None:
        messages.append({"message": new_message, "reply": new_reply})
        if len(messages) > limit:
            messages = messages[-limit:]
        SHORT_TERM_CACHE[key] = messages
        print(f"[SHORT_TERM_CACHE UPDATED] {key} (total={len(messages)})")
    return messages

def get_long_term(user_id, query, session_id=None, top_k=3):
    query_hash = hashlib.md5(query.encode('utf-8')).hexdigest()[:12]
    key = f"{user_id}_{session_id or 'global'}_{query_hash}"

    if key in LONG_TERM_CACHE:
        print(f"[CACHE HIT] long_term: {key}")
        return LONG_TERM_CACHE[key]

    print(f"[CACHE MISS] long_term: {key}")

    candidates = get_long_term_context(user_id, query, session_id=session_id, top_k=top_k)
    ranked = sorted(
        candidates,
        key=lambda x: 0.7 * x["similarity"] + 0.3 * x["recency"],
        reverse=True
    )
    top_contexts = [c["text"] for c in ranked[:top_k]]
    LONG_TERM_CACHE[key] = top_contexts

    return top_contexts

def get_context_parallel(user_id, user_msg, session_id=None, short_limit=5, long_top_k=3):
    results = {"short": None, "long": None}

    def fetch_short():
        results["short"] = get_short_term(user_id, session_id, limit=short_limit)

    def fetch_long():
        results["long"] = get_long_term(user_id, user_msg, session_id, top_k=long_top_k)

    # Tạo 2 thread song song
    t1 = threading.Thread(target=fetch_short)
    t2 = threading.Thread(target=fetch_long)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    return results["short"], results["long"]


def build_structured_prompt(user_msg, short_msgs, long_context, personality=None):
    system_prompt, user_prompt_format = get_cached_prompt()
    if personality:
        for k, v in personality.items():
            system_prompt = system_prompt.replace(f"%{k}%", str(v))
            user_prompt_format = user_prompt_format.replace(f"%{k}%", str(v))
    else:
        system_prompt = re.sub(r"%\w+%", "", system_prompt)
        user_prompt_format = re.sub(r"%\w+%", "", user_prompt_format)

    # Structured messages
    messages = [{"role": "system", "content": system_prompt}]
    # Short-term history
    for m in short_msgs:
        messages.append({"role": "user", "content": m["message"]})
        messages.append({"role": "assistant", "content": m["reply"]})
    # Long-term context
    if long_context:
        messages.append({"role": "system", "content": long_context})
    # Current message
    messages.append({"role": "user", "content": user_msg})
    return messages


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
    session_id = data.get("session_id")

    # Response cache
    cached_resp = RESPONSE_CACHE.get(user_id, session_id, user_msg)
    if cached_resp:
        return jsonify({
            "user_id": user_id,
            "session_id": session_id,
            "message": [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": cached_resp}
            ]
        })

    llm = load_prompt_config()
    if not llm:
        return Response("Model không hợp lệ", status=400)
    
    short_msgs = get_short_term(user_id, session_id, limit=10)
    long_ctx = get_long_term(user_id, user_msg, session_id=session_id, top_k=5)
    messages = build_structured_prompt(user_msg, short_msgs, long_ctx)

    @stream_with_context
    def generate():
        buf = ""
        start = time.perf_counter()
        try:
            for chunk in llm.stream(messages):
                content = getattr(chunk, "content", "")
                if content:
                    buf += content
                    yield content
            elapsed = round(time.perf_counter() - start, 3)
            try:
                get_short_term(user_id, session_id, limit=10, new_message=user_msg, new_reply=buf)
            except Exception as _:
                pass
            async_embed_message(user_id, user_msg, buf, session_id=session_id, time_spent=elapsed)
            RESPONSE_CACHE.set(user_id, session_id, user_msg, buf)
        except Exception as e:
            yield f"\n[ERROR]: {e}"

    return Response(generate(), mimetype="text/plain")

# ---------------- WHOISME /v1/chat ----------------
@whoisme_bp.route("/v1/chat", methods=["POST"])
def whoisme_chat_parallel():
    t0 = time.perf_counter()

    # --- Auth ---
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ")[1]
    user_info = verify_whoisme_token(token)
    if not user_info:
        return jsonify({"error": "Invalid WhoIsMe token"}), 401

    user_id = user_info["userId"]
    payload = request.json or {}
    user_msg = payload.get("message", "").strip()
    session_id = payload.get("session_id")

    if not user_msg:
        return jsonify({"error": "Message không được để trống"}), 400

    t1 = time.perf_counter()
    auth_elapsed = round(t1 - t0, 3)

    # --- Check response cache ---
    cache_start = time.perf_counter()
    cached_resp = RESPONSE_CACHE.get(user_id, session_id, user_msg)
    cache_elapsed = round(time.perf_counter() - cache_start, 3)

    if cached_resp:
        total_elapsed = round(time.perf_counter() - t0, 3)
        return jsonify({
            "user_id": user_id,
            "session_id": session_id,
            "model": "cache",
            "elapsed": {
                "total": total_elapsed,
                "auth": auth_elapsed,
                "cache": cache_elapsed,
                "cached": True
            },
            "message": [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": cached_resp}
            ]
        })

    # --- Load model ---
    prompt_start = time.perf_counter()
    llm = load_prompt_config()
    if not llm:
        return jsonify({"error": "Model không hợp lệ"}), 400
    model_name = getattr(llm, "model", None) or getattr(llm, "model_name", "Unknown")
    prompt_elapsed = round(time.perf_counter() - prompt_start, 3)
    print(f"[MODEL USED] {model_name}", flush=True)

    # --- Prepare short-term + long-term song song ---
    prepare_start = time.perf_counter()
    short_msgs, long_ctx = get_context_parallel(user_id, user_msg, session_id, short_limit=10, long_top_k=5)
    messages = build_structured_prompt(user_msg, short_msgs, long_ctx)
    prepare_elapsed = round(time.perf_counter() - prepare_start, 3)

    # --- Generate response ---
    model_start = time.perf_counter()
    buffer = ""
    try:
        for chunk in llm.stream(messages):
            content = getattr(chunk, "content", "")
            if content:
                buffer += content
    except Exception as e:
        print(f"[MODEL ERROR] {e}", flush=True)
        return jsonify({"error": f"Lỗi khi gọi model: {e}"}), 500
    model_elapsed = round(time.perf_counter() - model_start, 3)

    # --- Update caches + async DB ---
    update_start = time.perf_counter()
    try:
        get_short_term(user_id, session_id, limit=10, new_message=user_msg, new_reply=buffer)
    except Exception:
        pass
    async_embed_message(user_id, user_msg, buffer, session_id=session_id, time_spent=model_elapsed)
    RESPONSE_CACHE.set(user_id, session_id, user_msg, buffer)
    update_elapsed = round(time.perf_counter() - update_start, 3)

    # --- Total elapsed ---
    total_elapsed = round(time.perf_counter() - t0, 3)
    print(
        f"[PROFILE] model={model_name} | total={total_elapsed}s | "
        f"auth={auth_elapsed}s | cache={cache_elapsed}s | prompt={prompt_elapsed}s | "
        f"prepare={prepare_elapsed}s | model={model_elapsed}s | update={update_elapsed}s",
        flush=True
    )

    payload = {
        "user_id": user_id,
        "session_id": session_id,
        "model": model_name,
        "elapsed": {
            "total": total_elapsed,
            "auth": auth_elapsed,
            "cache": cache_elapsed,
            "prompt": prompt_elapsed,
            "prepare": prepare_elapsed,
            "model": model_elapsed,
            "update": update_elapsed,
            "cached": False
        },
        "message": [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": buffer}
        ]
    }
    return Response(json.dumps(to_serializable(payload)), mimetype="application/json")




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

    history = get_full_history(user_id, session_id)
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