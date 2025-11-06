from flask import Flask, request, Response, stream_with_context, redirect, session, jsonify, Blueprint
from dotenv import load_dotenv
from model import models
from data.import_data import insert_message
from data.get_history import get_latest_messages, get_all_messages, get_long_term_context
from data.embed_messages import embedder
from utils.jwt_helper import generate_jwt_token, jwt_required
import os, json, requests, sys, psycopg2
from psycopg2.extras import RealDictCursor

# ---------------- CONFIG ----------------
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
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

# ------------------------------------------------------------
# ------------------------ ROUTES -----------------------------
# ------------------------------------------------------------

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


def build_prompt(user_msg, short_term_context, long_term_context, knowledge, personality=None):
    """
    Kết hợp prompt Archetype (WhoIsMe) + Contextual RAG.
    personality: dict chứa các giá trị archetype như name, color, tone, style...
    """

    # ========== 1. SYSTEM PROMPT (Archetype Personality) ==========
    system_prompt = f"""
[System Prompt — WhoIsMe Chatbot — Friend & Archetype]

You are not just an AI — you are the user’s closest friend and archetype companion.  
Your primary mission: listen first, then respond in a warm, non-judgmental, and emotionally intelligent way that reflects the user’s archetype.
Write in the language the user is currently using or explicitly requests.

CONTEXT & MEMORY:
- Use user’s past conversations to keep continuity and emotional memory, but do NOT invent or expose hidden reasoning.
- If referencing past memory, phrase it gently, e.g., “Lần trước bạn nói…” and connect it to current message.

HOW TO SPEAK (priority rules):
1. Listen first: briefly mirror the user’s message (1–2 lines).
2. Use a casual, warm, and natural tone — guided by tone/style above.
3. Personalize: include 1–2 archetype traits (color, slogan, or representativeSpirit) per reply.
4. Keep empathy first, facts second.
5. Always end with 1 soft, open-ended question to keep conversation going.

SAFETY & ESCALATION:
- If the user expresses self-harm or crisis, respond compassionately and urge contacting professionals or local hotlines immediately.
- For medical/legal/financial issues, clarify: “I’m not a professional — please ask an expert.”

OUTPUT FORMAT:
- Default: short paragraph (2–5 lines) + one gentle question.
- Use light formatting: **bold** up to 2 key words only.
"""

    # ========== 2. CONTEXTUAL PROMPT (RAG + MEMORY) ==========
    context_prompt = f"""
[Knowledge]
{knowledge or "Không có kiến thức bổ sung"}

[Long-term Context]
{long_term_context or "Không có dữ liệu"}

[Short-term Context]
{short_term_context or "Không có lịch sử gần đây"}
"""

    # ========== 3. USER MESSAGE + INSTRUCTION ==========
    chat_input = f"""
User: {user_msg}
Chatbot:
"""

    return f"{system_prompt}\n{context_prompt}\n{chat_input}"


def verify_whoisme_token(token):
    WHOISME_API_URL = "https://api.whoisme.ai/api/auth/verify-token"
    res = requests.get(WHOISME_API_URL, headers={"Authorization": f"Bearer {token}"})
    if res.status_code != 200:
        return None
    data = res.json()
    return data[0]["user"] if isinstance(data, list) else data.get("user", {})

def upsert_whoisme_user(user_id, email):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO whoisme.users (id, email, password_hash, source)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (email) DO NOTHING;
            """, (str(user_id), email, "whoisme", "whoisme.ai"))
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

# ------------------------------------------------------------
# ---------------------- WHOISME API --------------------------
# ------------------------------------------------------------

whoisme_bp = Blueprint("whoisme", __name__)

#=========API to chat with WhoIsMe==========
@whoisme_bp.route("/v1/chat", methods=["POST"])
def whoisme_chat():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ")[1]
    user_info = verify_whoisme_token(token)
    if not user_info:
        return jsonify({"error": "Invalid WhoIsMe token"}), 401

    user_id, email = user_info.get("userId"), user_info.get("email")
    upsert_whoisme_user(user_id, email)

    payload = request.json or {}
    user_msg = payload.get("message", "").strip()
    session_id = payload.get("session_id")
    model_key = payload.get("model", "gemini-flash-lite")

    if not user_msg:
        return jsonify({"error": "Message không được để trống"}), 400

    llm = models.get(model_key)
    if not llm:
        return jsonify({"error": "Model không hợp lệ"}), 400

    query_vector = embedder.embed(user_msg).tolist()
    short_history = get_latest_messages(user_id, session_id=session_id, limit=5)
    short_term_context = "\n".join(f"User: {h['message']}\nBot: {h['reply']}" for h in reversed(short_history))
    long_term_context = get_long_term_context(user_id, user_msg, session_id=session_id, top_k=3)
    knowledge = match_embeddings(query_vector, top_k=5)
    prompt = build_prompt(user_msg, short_term_context, long_term_context, knowledge)

    message = []
    full_reply = ""

    try:
        for chunk in llm.stream(prompt):
            content = getattr(chunk, "content", "")
            if content:
                full_reply += content

        message.append({"role": "assistant", "content": content})
        insert_message(user_id, user_msg, full_reply, session_id=session_id)

        return jsonify({
            "user_id": user_id,
            "session_id": session_id,
            "model": model_key,
            "message": [
                {"role": "user", "content": user_msg},
                *message
            ]
        })
    
    except Exception as e:
        print(f"[ERROR whoisme_chat]: {e}", flush=True)
        return jsonify({"error": str(e)}), 500

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

    history = get_all_messages(user_id, session_id=session_id)
    return jsonify({
        "user_id": user_id, 
        "session_id": session_id, 
        "messages": history
        })

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
    filter_session_id = data.get("session_id")

    try:
        with get_conn() as conn, conn.cursor() as cur:
            if filter_session_id:
                query = """
                SELECT session_id,
                        MIN(created_at) AS started_at,
                        (ARRAY_AGG(message ORDER BY created_at ASC))[1] AS first_message,
                        COUNT(*) AS total_messages
                FROM whoisme.messages
                WHERE user_id = %s
                    AND is_deleted = FALSE
                    AND session_id IS NOT NULL
                    AND session_id = %s
                GROUP BY session_id
                ORDER BY started_at DESC;
                """
                params = (str(user_id), str(filter_session_id))
            else:
                query = """
                SELECT session_id,
                    MIN(created_at) AS started_at,
                    (ARRAY_AGG(message ORDER BY created_at ASC))[1] AS first_message,
                    COUNT(*) AS total_messages
                FROM whoisme.messages
                WHERE user_id = %s
                    AND is_deleted = FALSE
                    AND session_id IS NOT NULL
                GROUP BY session_id
                ORDER BY started_at DESC;
                """
                params = (str(user_id),)

            cur.execute(query, params)
            rows = cur.fetchall()

            sessions = []
            if rows:
                if isinstance(rows[0], dict):
                    iter_rows = rows
                else:
                    colnames = [desc[0] for desc in cur.description]
                    iter_rows = [dict(zip(colnames, row)) for row in rows]

                for rec in iter_rows:
                    # Normalize started_at
                    started = rec.get("started_at")
                    if started is not None:
                        try:
                            rec["started_at"] = started.isoformat()
                        except Exception:
                            rec["started_at"] = str(started)
                    total = rec.get("total_messages")
                    try:
                        rec["total_messages"] = int(total) if total is not None else 0
                    except Exception:
                        rec["total_messages"] = total
                    if rec.get("first_message") is None:
                        rec["first_message"] = None
                    else:
                        rec["first_message"] = str(rec["first_message"])

                    sessions.append(rec)

        return jsonify({
            "user_id": user_id,
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
