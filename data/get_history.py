import psycopg2
import os
from dotenv import load_dotenv
from data.embed_messages import embedder
import numpy as np
import ast

load_dotenv()
LOCAL_DB_URL = os.getenv("POSTGRES_URL")


def get_conn():
    """Tạo kết nối mới mỗi lần gọi"""
    return psycopg2.connect(LOCAL_DB_URL)


def get_latest_messages(user_id, session_id=None, limit=10):
    """Lấy n tin nhắn gần nhất"""
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
            colnames = [desc[0] for desc in cur.description]
            rows = [dict(zip(colnames, r)) for r in cur.fetchall()]
            return rows
    except Exception as e:
        print("❌ Lỗi khi lấy lịch sử chat:", e)
        return []


def get_all_messages(user_id, session_id=None):
    """Lấy toàn bộ lịch sử chat theo user + session"""
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
                    (str(user_id)),
                )
            colnames = [desc[0] for desc in cur.description]
            rows = [dict(zip(colnames, r)) for r in cur.fetchall()]
            return rows
    except Exception as e:
        print("❌ Lỗi khi lấy tất cả tin nhắn:", e)
        return []


def to_float_array(raw):
    """Chuyển chuỗi/array thành numpy array float"""
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
    """Tìm các message cũ có embedding gần nhất với query"""
    q_vec = embedder.embed(query)
    q_vec = to_float_array(q_vec)
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
                    (str(user_id)),
                )
            colnames = [desc[0] for desc in cur.description]
            rows = [dict(zip(colnames, r)) for r in cur.fetchall()]
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

    long_context_text = "\n".join(
        [f"User: {r['message']}\nBot: {r['reply']}" for sim, r in sims]
    )
    return long_context_text


# --- Test ---
if __name__ == "__main__":
    uid = "1000000405"
    sess = "test-session-001"

    print (get_all_messages(uid, session_id=sess))

    print("\n=== Short-term context (latest 5) ===")
    for row in get_latest_messages(uid, session_id=sess, limit=5):
        print(row)

    print("\n=== Long-term context ===")
    print(get_long_term_context(uid, "Đồ ăn healthy là gì", session_id=sess, top_k=5, debug=True))
