import os, sys, re, time, requests, traceback, threading, hashlib, json, logging
from flask import Flask, request, Response, stream_with_context, session, redirect, jsonify, Blueprint
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
import psycopg2
from cachetools import TTLCache
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from model import load_prompt_config
from data.get_history import get_latest_history, get_long_term_context, get_full_history
from data.import_data import insert_message, get_conn
from data.embed_messages import embedder
from datetime import datetime

# ---------------- ENV ----------------
load_dotenv()
LOCAL_DB_URL = os.getenv("POSTGRES_URL")
PROMPT_API_URL = "https://prompt.whoisme.ai/api/public/prompt/chatgpt_prompt_chatbot"
WHOISME_API_URL = "https://api.whoisme.ai/api/archetype/code/{}"
WHOISME_API_NO_LOGIN_PROMPT = "https://prompt.whoisme.ai/api/public/prompt/prompt_no_login"

# ---------------- LOGGER ----------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def log_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    print("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)), flush=True)
sys.excepthook = log_exception

# ---------------- FLASK ----------------
app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = os.getenv("FLASK_SECRET", "super-secret-key")
whoisme_bp = Blueprint("whoisme", __name__)

# ---------------- CACHE ----------------
SHORT_TERM_CACHE = TTLCache(maxsize=5000, ttl=1800)
LONG_TERM_CACHE = TTLCache(maxsize=5000, ttl=900)
PROMPT_CACHE = {"systemPrompt": "", "userPromptFormat": "", "updatedAt": None, "timestamp": 0}
PERSIONALITY_CACHE = {"data": {}, "updatedAt": None, "lock": threading.Lock()}

EXECUTOR = ThreadPoolExecutor(max_workers=8)

# ---------------- RESPONSE CACHE ----------------
class ResponseCache:
    def __init__(self, ttl=120, max_hits=1):
        self.cache = TTLCache(maxsize=5000, ttl=ttl)
        self.hits = defaultdict(int)
        self.max_hits = max_hits
    def get(self, user_id, session_id, message):
        key = f"{user_id}_{session_id or 'global'}_{hash(message)}"
        if key in self.cache and self.hits[key] < self.max_hits:
            self.hits[key] += 1
            return self.cache[key]
        return None
    def set(self, user_id, session_id, message, response):
        key = f"{user_id}_{session_id or 'global'}_{hash(message)}"
        self.cache[key] = response
        self.hits[key] = 0
RESPONSE_CACHE = ResponseCache(ttl=120, max_hits=1)

# ---------------- JWT ----------------
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
            logger.error(f"[verify_whoisme_token fallback error]: {e}")
            return None

# ---------------- UTILS ----------------
def to_serializable(obj):
    if obj is None or isinstance(obj, (str,int,float,bool)):
        return obj
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k,v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_serializable(v) for v in obj]
    if hasattr(obj,"model_name"): return getattr(obj,"model_name")
    if hasattr(obj,"model"):
        m = getattr(obj,"model")
        return m if isinstance(m,(str,int,float,bool)) or m is None else str(m)
    try:
        return str(obj)
    except Exception:
        return f"<unserializable:{type(obj).__name__}>"

# ---------------- PROMPT ----------------
def fetch_prompt_from_api():
    try:
        resp = requests.get(PROMPT_API_URL, timeout=5)
        data = resp.json().get("data",{})
        return {
            "systemPrompt": data.get("systemPrompt",""),
            "userPromptFormat": data.get("userPromptFormat",""),
            "updatedAt": data.get("updatedAt")
        }
    except Exception as e:
        logger.error(f"[Prompt Fetch Error]: {e}")
        return PROMPT_CACHE

def background_prompt_updater(interval=300):
    while True:
        try:
            new_data = fetch_prompt_from_api()
            if new_data.get("updatedAt") != PROMPT_CACHE.get("updatedAt"):
                PROMPT_CACHE.update(new_data)
                PROMPT_CACHE["timestamp"] = time.time()
                logger.info(f"[Prompt Updated] at {new_data.get('updatedAt')}")
        except Exception as e:
            logger.error(f"[Prompt Updater Error]: {e}")
        time.sleep(interval)
threading.Thread(target=background_prompt_updater, daemon=True).start()

def get_cached_prompt():
    if PROMPT_CACHE["systemPrompt"]:
        return PROMPT_CACHE["systemPrompt"], PROMPT_CACHE["userPromptFormat"]
    data = fetch_prompt_from_api()
    PROMPT_CACHE.update(data)
    PROMPT_CACHE["timestamp"] = time.time()
    return data.get("systemPrompt",""), data.get("userPromptFormat","User said: {{content}}")

# ---------------- PERSONALITY ----------------
def fetch_personality_source(archetype_code: str) -> dict:
    if not archetype_code:
        return {}

    try:
        resp = requests.get(WHOISME_API_URL.format(archetype_code), timeout=5)
        resp.raise_for_status()
        data = resp.json().get("data") or resp.json()
        translation = data.get("translation") or {}
        updated_at = data.get("updatedAt") or data.get("updated_at")

        with PERSIONALITY_CACHE["lock"]:
            if PERSIONALITY_CACHE.get("updatedAt") != updated_at:
                keys_map = {
                    "style": "style",
                    "tone": "tone",
                    "spirit": "representativeSpirit",
                    "name": "name",
                    "color": "color",
                    "slogan": "slogan",
                    "suggestedJobs": "suggestedJobs",
                    "strengths": "strengths",
                    "weaknesses": "weaknesses",
                    "note": "note",
                }
                persionality = {k: translation.get(v, "") for k, v in keys_map.items()}
                PERSIONALITY_CACHE["data"] = persionality
                PERSIONALITY_CACHE["updatedAt"] = updated_at
            else:
                persionality = PERSIONALITY_CACHE["data"]

        return persionality

    except Exception as e:
        logger.error(f"[fetch_personality_source] {e}")
        return PERSIONALITY_CACHE.get("data") or {}
    
# ---------------- CONTEXT ----------------
def _normalize_id(x):
    return str(x) if x is not None else "global"

SHORT_TERM_LOCK = threading.Lock()

SHORT_TERM_CACHE = {}
CACHE_TTL = 30 * 60
MAX_CACHE_LENGTH = 50

def get_short_term(
    user_id, session_id=None, limit=5,
    new_message=None, new_reply=None,
    force_refresh=False
):
    user_id_s = str(user_id)
    sess_s = str(session_id) if session_id else "global"
    key = f"{user_id_s}_{sess_s}"
    now = time.time()

    with SHORT_TERM_LOCK:
        if key in SHORT_TERM_CACHE:
            if now - SHORT_TERM_CACHE[key]["timestamp"] > CACHE_TTL:
                del SHORT_TERM_CACHE[key]
        if force_refresh or key not in SHORT_TERM_CACHE:
            rows = get_latest_history(user_id_s, session_id, limit) or []
            normalized = deque(maxlen=limit)
            for m in rows:
                normalized.append({
                    "message": m["message"] or "",
                    "reply": m["reply"] or ""
                })
            SHORT_TERM_CACHE[key] = {
                "messages": normalized,
                "timestamp": now
            }
        if new_message and new_reply:
            SHORT_TERM_CACHE[key]["messages"].appendleft({
                "message": new_message,
                "reply": new_reply
            })
            SHORT_TERM_CACHE[key]["timestamp"] = now
        return list(SHORT_TERM_CACHE[key]["messages"])
    
LONG_TERM_LOCK = threading.Lock()

def get_long_term(user_id, query, session_id=None, top_k=5, max_chars=300):
    user_id_s = str(user_id)
    sess_s = str(session_id) if session_id else "global"

    query_hash = hashlib.md5(query.encode("utf-8")).hexdigest()
    key = f"{user_id_s}_{sess_s}_{query_hash}"

    with LONG_TERM_LOCK:
        if key in LONG_TERM_CACHE:
            return LONG_TERM_CACHE[key]
    rows = get_long_term_context(user_id_s, query, session_id, top_k=top_k) or []
    now_ts = datetime.utcnow().timestamp()
    results = []
    for r in rows:
        msg = r.get("message") or ""
        reply = r.get("reply") or ""

        score = r.get("score")
        dist  = r.get("distance")

        if dist is not None:
            similarity = 1 - dist
        elif score is not None:
            similarity = score
        else:
            similarity = 0
        created = r.get("created_at")
        if hasattr(created, "timestamp"):
            created_ts = created.timestamp()
        else:
            created_ts = now_ts
        recency = 1 / (now_ts - created_ts + 1)
        results.append({
            "message": msg[:max_chars],
            "reply": reply[:max_chars],
            "similarity": similarity,
            "recency": recency,
        })
    ranked = sorted(
        results,
        key=lambda x: 0.7 * x["similarity"] + 0.3 * x["recency"],
        reverse=True
    )
    top = [
        {
            "message": r["message"],
            "reply": r["reply"],
        }
        for r in ranked[:top_k]
    ]
    with LONG_TERM_LOCK:
        LONG_TERM_CACHE[key] = top
    return top

def get_context_parallel(user_id, user_msg, session_id=None, short_limit=5, long_top_k=3, max_long_chars=300):
    short_msgs_local = []
    long_msgs_local = []

    def short_fn():
        nonlocal short_msgs_local
        short_msgs_local = get_short_term(user_id, session_id, limit=short_limit)

    def long_fn():
        nonlocal long_msgs_local
        long_msgs_local = [c[:max_long_chars] for c in get_long_term(user_id, user_msg, session_id=session_id, top_k=long_top_k)]

    t1 = threading.Thread(target=short_fn)
    t2 = threading.Thread(target=long_fn)
    t1.start(); t2.start(); t1.join(); t2.join()
    return short_msgs_local, long_msgs_local


# ---------------- PROMPT INJECTION ----------------
def inject_personality(system_prompt: str, personality: dict, userPromptFormat: dict=None):
    mapping = {f"%{k}%":v for k,v in (personality or {}).items()}
    if isinstance(userPromptFormat, dict):
        mapping.update({f"%{k}%":v for k,v in userPromptFormat.items()})
    for k,v in mapping.items(): 
        system_prompt = system_prompt.replace(k,v or "")
    return re.sub(r"%\w+%","",system_prompt)

def build_structured_prompt(user_msg, short_msgs, long_context, archetype_code=None, max_long_lines=5):
    system_prompt, user_prompt_format = get_cached_prompt()
    personality = fetch_personality_source(archetype_code) if archetype_code else {}
    final_system_prompt = inject_personality(system_prompt, personality)
    messages = [{"role":"system","content":final_system_prompt}]
    for m in short_msgs:
        if m.get("message"): messages.append({"role":"user","content":m.get("message")})
        if m.get("reply"): messages.append({"role":"assistant","content":m.get("reply")})
    if long_context:
        messages.append({"role":"system","content":"LONG-TERM CONTEXT:\n"+ "\n".join(long_context[:max_long_lines])})
    fmt = user_prompt_format
    if not isinstance(fmt, str) or not fmt.strip():
        fmt = "User: {{content}}"

    formatted_user_msg = fmt.replace("{{content}}", user_msg)
    formatted_user_msg = inject_personality(formatted_user_msg, personality)
    messages.append({"role":"user","content":formatted_user_msg})
    return messages

# ---------------- ASYNC DB ----------------
def async_embed_message(user_id, message, reply, session_id=None, time_spent=None):
    EXECUTOR.submit(insert_message, user_id, message, reply, session_id, time_spent)

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
    archetype_code = data.get("code")  

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
    
    short_msgs = get_short_term(user_id, session_id, limit=5)
    long_ctx = get_long_term(user_id, user_msg, session_id=session_id, top_k=5)
    messages = build_structured_prompt(user_msg, short_msgs, long_ctx, archetype_code=archetype_code)

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
            except Exception:
                pass
            async_embed_message(user_id, user_msg, buf, session_id=session_id, time_spent=elapsed)
            RESPONSE_CACHE.set(user_id, session_id, user_msg, buf)
        except Exception as e:
            yield f"\n[ERROR]: {e}"

    return Response(generate(), mimetype="text/plain")

# ---------------- WHOISME /v1/chat ----------------
@whoisme_bp.route("/v1/chatbot", methods=["POST"])
def whoisme_chat_parallel():
    t0 = time.perf_counter()

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ")[1]
    user_info = verify_whoisme_token(token)
    if not user_info:
        return jsonify({"error": "Invalid WhoIsMe token"}), 401

    user_id = user_info["userId"]
    payload = request.get_json(force=True, silent=True) or {}

    user_msg = (payload.get("message") or "").strip()
    session_id = payload.get("session_id")

    code_raw = payload.get("code")
    archetype_code = code_raw.strip() if isinstance(code_raw, str) and code_raw.strip() else None

    if not user_msg:
        return jsonify({"error": "Message không được để trống"}), 400

    t1 = time.perf_counter()
    auth_elapsed = round(t1 - t0, 3)

    cache_start = time.perf_counter()
    cached_resp = RESPONSE_CACHE.get(user_id, session_id, user_msg)
    cache_elapsed = round(time.perf_counter() - cache_start, 3)

    if cached_resp:
        total_elapsed = round(time.perf_counter() - t0, 3)
        return jsonify({
            "user_id": user_id,
            "session_id": session_id,
            "model": "cache",
            "archetype_code": archetype_code,
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

    prompt_start = time.perf_counter()
    llm = load_prompt_config()
    if not llm:
        return jsonify({"error": "Model không hợp lệ"}), 400
    model_name = getattr(llm, "model", None) or getattr(llm, "model_name", "Unknown")
    prompt_elapsed = round(time.perf_counter() - prompt_start, 3)
    print(f"[MODEL USED] {model_name}", flush=True)

    prepare_start = time.perf_counter()
    short_msgs, long_ctx = get_context_parallel(user_id, user_msg, session_id, short_limit=5, long_top_k=5)
    messages = build_structured_prompt(user_msg, short_msgs, long_ctx, archetype_code=archetype_code)
    prepare_elapsed = round(time.perf_counter() - prepare_start, 3)

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

    update_start = time.perf_counter()
    try:
        get_short_term(user_id, session_id, limit=10, new_message=user_msg, new_reply=buffer)
    except Exception:
        pass
    async_embed_message(user_id, user_msg, buffer, session_id=session_id, time_spent=model_elapsed)
    RESPONSE_CACHE.set(user_id, session_id, user_msg, buffer)
    update_elapsed = round(time.perf_counter() - update_start, 3)

    total_elapsed = round(time.perf_counter() - t0, 3)
    print(
        f"[PROFILE] model={model_name} | total={total_elapsed}s | "
        f"auth={auth_elapsed}s | cache={cache_elapsed}s | prompt={prompt_elapsed}s | "
        f"prepare={prepare_elapsed}s | model={model_elapsed}s | update={update_elapsed}s",
        flush=True
    )

    payload_out = {
        "user_id": user_id,
        "session_id": session_id,
        "model": model_name,
        "archetype_code": archetype_code,
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
    return Response(json.dumps(to_serializable(payload_out)), mimetype="application/json")

#=========v2=================
@whoisme_bp.route("/v1/chat", methods=["POST"])
def whoisme_chat_parallell():
    t0 = time.perf_counter()

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401
    token = auth_header.split(" ")[1]
    user_info = verify_whoisme_token(token)
    if not user_info:
        return jsonify({"error": "Invalid WhoIsMe token"}), 401

    user_id = user_info["userId"]
    payload = request.get_json(force=True, silent=True) or {}
    user_msg = (payload.get("message") or "").strip()
    session_id = payload.get("session_id")
    code_raw = payload.get("code")
    archetype_code = code_raw.strip() if isinstance(code_raw, str) and code_raw.strip() else None

    if not user_msg:
        return jsonify({"error": "Message không được để trống"}), 400

    cached_resp = RESPONSE_CACHE.get(user_id, session_id, user_msg)
    if cached_resp:
        total_elapsed = round(time.perf_counter() - t0, 3)
        return jsonify({
            "user_id": user_id,
            "session_id": session_id,
            "model": "cache",
            "archetype_code": archetype_code,
            "elapsed": {
                "total": total_elapsed,
                "cached": True
            },
            "system_prompt": None,
            "message": [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": cached_resp}
            ]
        })

    llm = load_prompt_config()
    if not llm:
        return jsonify({"error": "Model không hợp lệ"}), 400
    model_name = getattr(llm, "model", None) or getattr(llm, "model_name", "Unknown")

    short_msgs, long_ctx = get_context_parallel(user_id, user_msg, session_id, short_limit=5, long_top_k=5)

    system_prompt, user_prompt_format = get_cached_prompt()
    personality = fetch_personality_source(archetype_code) if archetype_code else {}
    final_system_prompt = inject_personality(system_prompt, personality)

    messages = [{"role": "system", "content": final_system_prompt}]
    for m in short_msgs:
        if m.get("message"):
            messages.append({"role": "user", "content": m.get("message")})
        if m.get("reply"):
            messages.append({"role": "assistant", "content": m.get("reply")})
    if long_ctx:
        messages.append({"role": "system", "content": "LONG-TERM CONTEXT:\n" + "\n".join(long_ctx[:5])})
    formatted_user_msg = (user_prompt_format or "User said: {{content}}").replace("{{content}}", user_msg)
    messages.append({"role": "user", "content": formatted_user_msg})

    buffer = ""
    model_start = time.perf_counter()
    try:
        for chunk in llm.stream(messages):
            content = getattr(chunk, "content", "")
            if content:
                buffer += content
    except Exception as e:
        return jsonify({"error": f"Lỗi khi gọi model: {e}"}), 500
    model_elapsed = round(time.perf_counter() - model_start, 3)

    try:
        get_short_term(user_id, session_id, limit=5, new_message=user_msg, new_reply=buffer)
    except Exception:
        pass
    async_embed_message(user_id, user_msg, buffer, session_id=session_id, time_spent=model_elapsed)
    RESPONSE_CACHE.set(user_id, session_id, user_msg, buffer)

    total_elapsed = round(time.perf_counter() - t0, 3)
    payload_out = {
        "user_id": user_id,
        "session_id": session_id,
        "model": model_name,
        "archetype_code": archetype_code,
        "system_prompt": final_system_prompt,
        "formatted_user_message": formatted_user_msg,
        "long_term_context": long_ctx,
        "short_term_messages": short_msgs,
        "cached": False,
        "elapsed": {
            "total": total_elapsed,
            "model": model_elapsed
        },
        "message": [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": buffer}
        ]
    }

    return Response(json.dumps(to_serializable(payload_out)), mimetype="application/json")

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

    # Lấy session_id từ query string hoặc JSON body (an toàn)
    body = request.get_json(silent=True) or {}
    session_id = request.args.get("session_id") or body.get("session_id")
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
                rec["first_message"] = str(rec.get("first_message")) if rec.get("first_message") else None
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