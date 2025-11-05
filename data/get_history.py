import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import numpy as np
import ast
from data.embed_messages import embedder

load_dotenv()
LOCAL_DB_URL = os.getenv("POSTGRES_URL")


def get_conn():
    return psycopg2.connect(LOCAL_DB_URL, cursor_factory=RealDictCursor)


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
        print("Lỗi khi lấy lịch sử chat:", e)
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
        print("Lỗi khi lấy tất cả tin nhắn:", e)
        return []


def to_float_array(raw):
    if raw is None:
        return None
    if isinstance(raw, (np.ndarray, list, tuple)):
        return np.asarray(raw, dtype=float)
    if isinstance(raw, str):
        try:
            parsed = ast.literal_eval(raw)
            return np.asarray(parsed, dtype=float)
        except Exception:
            return None
    return None


def get_long_term_context(user_id: str, query: str, session_id=None, top_k: int = 5, debug: bool = False):
    q_vec = to_float_array(embedder.embed(query))
    if q_vec is None:
        raise ValueError("Không thể tạo vector cho query")

    try:
        with get_conn() as conn, conn.cursor() as cur:
            if session_id:
                cur.execute(
                    """
                    SELECT id, message, reply, embedding_vector
                    FROM whoisme.messages
                    WHERE user_id = %s AND session_id = %s
                    AND embedding_vector IS NOT NULL;
                    """,
                    (str(user_id), str(session_id)),
                )
            else:
                cur.execute(
                    """
                    SELECT id, message, reply, embedding_vector
                    FROM whoisme.messages
                    WHERE user_id = %s
                    AND embedding_vector IS NOT NULL;
                    """,
                    (str(user_id),),
                )
            rows = cur.fetchall()
    except Exception as e:
        print("Lỗi khi truy vấn PostgreSQL:", e)
        return ""

    if not rows:
        return ""

    sims = []
    for row in rows:
        vec = to_float_array(row.get("embedding_vector"))
        if vec is None or vec.shape != q_vec.shape:
            continue
        sim = np.dot(q_vec, vec) / (np.linalg.norm(q_vec) * np.linalg.norm(vec))
        sims.append((float(sim), row))

    sims = sorted(sims, key=lambda x: x[0], reverse=True)[:top_k]

    if debug:
        for sim, row in sims:
            print(f"🔹 {row['id']} → sim={sim:.3f}")

    return "\n".join([f"User: {r['message']}\nBot: {r['reply']}" for sim, r in sims])

# --- Test ---
if __name__ == "__main__":
    uid = "1000000405"
    sess = "test-session-001"

    print(get_all_messages(uid, sess))
    print("\n=== Short-term context ===")
    for row in get_latest_messages(uid, sess, 5):
        print(row)

    print("\n=== Long-term context ===")
    print(get_long_term_context(uid, "Đồ ăn healthy là gì", sess, 5, True))
