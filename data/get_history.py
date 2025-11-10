import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import numpy as np
from data.embed_messages import embedder

load_dotenv()
LOCAL_DB_URL = os.getenv("POSTGRES_URL")

def get_conn():
    return psycopg2.connect(LOCAL_DB_URL, cursor_factory=RealDictCursor)

# ----------------- MESSAGE HISTORY -----------------

def get_latest_messages(user_id, session_id=None, limit=10):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            if session_id:
                cur.execute(
                    """
                    SELECT id, message, reply, created_at, session_id
                    FROM whoisme.messages
                    WHERE user_id = %s 
                        AND session_id = %s
                        AND is_deleted = FALSE
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (str(user_id), str(session_id), limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, message, reply, created_at, session_id
                    FROM whoisme.messages
                    WHERE user_id = %s
                        AND is_deleted = FALSE
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (str(user_id), limit),
                )
            return cur.fetchall()
    except Exception as e:
        print("[get_latest_messages] Lỗi:", e)
        return []

def get_all_messages(user_id, session_id=None):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            if session_id:
                cur.execute(
                    """
                    SELECT message, reply, created_at, session_id
                    FROM whoisme.messages
                    WHERE user_id = %s
                        AND session_id = %s
                        AND is_deleted = FALSE
                    ORDER BY id ASC;
                    """,
                    (str(user_id), str(session_id)),
                )
            else:
                cur.execute(
                    """
                    SELECT message, reply, created_at, session_id
                    FROM whoisme.messages
                    WHERE user_id = %s
                        AND is_deleted = FALSE
                    ORDER BY id ASC;
                    """,
                    (str(user_id),),
                )
            return cur.fetchall()
    except Exception as e:
        print("[get_all_messages] Lỗi:", e)
        return []

# ----------------- LONG-TERM CONTEXT -----------------

def to_float_array(vec):
    if vec is None:
        return None
    if isinstance(vec, (list, tuple, np.ndarray)):
        return np.asarray(vec, dtype=float)
    if isinstance(vec, str):
        try:
            return np.asarray(eval(vec), dtype=float)
        except:
            return None
    return None

def get_long_term_context(user_id: str, query: str, session_id=None, top_k: int = 5, debug: bool = False):
    q_vec = to_float_array(embedder.embed(query))
    if q_vec is None:
        print("[get_long_term_context] Không tạo được vector query")
        return ""

    try:
        with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            if session_id:
                cur.execute(
                    """
                    SELECT id, message, reply,
                        1 - (embedding_vector <=> %s::vector) AS similarity
                    FROM whoisme.messages
                    WHERE user_id = %s AND session_id = %s
                        AND embedding_vector IS NOT NULL
                    ORDER BY embedding_vector <=> %s::vector
                    LIMIT %s;
                    """,
                    (q_vec.tolist(), str(user_id), str(session_id), q_vec.tolist(), top_k),
                )
            else:
                cur.execute(
                    """
                    SELECT id, message, reply,
                        1 - (embedding_vector <=> %s::vector) AS similarity
                    FROM whoisme.messages
                    WHERE user_id = %s
                        AND embedding_vector IS NOT NULL
                    ORDER BY embedding_vector <=> %s::vector
                    LIMIT %s;
                    """,
                    (q_vec.tolist(), str(user_id), q_vec.tolist(), top_k),
                )
            rows = cur.fetchall()

            if not rows:
                return ""

            if debug:
                for r in rows:
                    print(f"🔹 {r['id']} → sim={r['similarity']:.3f}")
            return "\n".join([f"User: {r['message']}\nBot: {r['reply']}" for r in rows])

    except Exception as e:
        print("[get_long_term_context] Lỗi PostgreSQL:", e)
        return ""

# ----------------- TEST -----------------

if __name__ == "__main__":
    uid = "1000000405"
    sess = "test-session-001"

    print("=== All messages ===")
    print(get_all_messages(uid, sess))

    print("\n=== Short-term context ===")
    for row in get_latest_messages(uid, sess, 5):
        print(row)

    print("\n=== Long-term context ===")
    print(get_long_term_context(uid, "Đồ ăn healthy là gì", sess, 5, True))
