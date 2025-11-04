import psycopg2
import os
from dotenv import load_dotenv
from data.embed_messages import embedder
import numpy as np
import ast

load_dotenv()

LOCAL_DB_URL = os.getenv("POSTGRES_URL")

# --- Kết nối PostgreSQL local ---
local_conn = psycopg2.connect(LOCAL_DB_URL)
local_conn.autocommit = True


def get_latest_messages(user_id, session_id=None, limit=10):
    """
    Lấy `limit` tin nhắn gần nhất của user, có thể lọc theo session_id.
    """
    try:
        with local_conn.cursor() as cur:
            if session_id:
                cur.execute(
                    """
                    SELECT id, message, reply, created_at, session_id
                    FROM whoisme.messages
                    WHERE user_id = %s AND session_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (user_id, session_id, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, message, reply, created_at, session_id
                    FROM whoisme.messages
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (user_id, limit),
                )
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            return [dict(zip(colnames, r)) for r in rows]
    except Exception as e:
        print("❌ Lỗi khi lấy lịch sử chat:", e)
        return []


def get_all_messages(user_id, session_id=None):
    """
    Lấy toàn bộ tin nhắn của user, có thể lọc theo session_id.
    """
    try:
        with local_conn.cursor() as cur:
            if session_id:
                cur.execute(
                    """
                    SELECT message, reply, created_at
                    FROM whoisme.messages
                    WHERE user_id = %s AND session_id = %s
                    ORDER BY id ASC;
                    """,
                    (user_id, session_id),
                )
            else:
                cur.execute(
                    """
                    SELECT message, reply, created_at
                    FROM whoisme.messages
                    WHERE user_id = %s
                    ORDER BY id ASC;
                    """,
                    (user_id,),
                )
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            return [dict(zip(colnames, r)) for r in rows]
    except Exception as e:
        print("❌ Lỗi khi lấy tất cả tin nhắn:", e)
        return []


# --- Convert raw embedding text thành numpy array ---
def to_float_array(raw):
    if raw is None:
        return None
    if isinstance(raw, (np.ndarray, list, tuple)):
        try:
            return np.asarray(raw, dtype=float)
        except Exception:
            out = []
            for e in raw:
                try:
                    s = str(e).strip().strip('"').strip("'")
                    out.append(float(s))
                except Exception:
                    return None
            return np.asarray(out, dtype=float)
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = ast.literal_eval(s)
                return np.asarray([float(x) for x in parsed], dtype=float)
            except Exception:
                pass
        if s.startswith("{") and s.endswith("}"):
            inner = s[1:-1]
            parts = [p.strip().strip('"').strip("'") for p in inner.split(",") if p.strip()]
            try:
                return np.asarray([float(p) for p in parts], dtype=float)
            except Exception:
                return None
        parts = [p.strip().strip('"').strip("'") for p in s.split(",") if p.strip()]
        try:
            return np.asarray([float(p) for p in parts], dtype=float)
        except Exception:
            return None
    return None


def get_long_term_context(user_id: str, query: str, session_id=None, top_k: int = 5, debug: bool = False):
    """
    Lấy long-term context từ bảng whoisme.messages local PostgreSQL.
    """
    q_vec = embedder.embed(query)
    q_vec = to_float_array(q_vec)
    if q_vec is None:
        raise ValueError("Không thể tạo vector cho query")

    try:
        with local_conn.cursor() as cur:
            if session_id:
                cur.execute(
                    """
                    SELECT id, message, reply, embedding_vector
                    FROM whoisme.messages
                    WHERE user_id = %s AND session_id = %s AND embedding_vector IS NOT NULL;
                    """,
                    (user_id, session_id),
                )
            else:
                cur.execute(
                    """
                    SELECT id, message, reply, embedding_vector
                    FROM whoisme.messages
                    WHERE user_id = %s AND embedding_vector IS NOT NULL;
                    """,
                    (user_id,),
                )

            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            rows = [dict(zip(colnames, r)) for r in rows]
    except Exception as e:
        print("❌ Lỗi khi truy vấn PostgreSQL:", e)
        return ""

    if not rows:
        return ""

    sims = []
    for row in rows:
        vec = to_float_array(row.get("embedding_vector"))
        if vec is None or vec.shape != q_vec.shape:
            continue
        norm_q = np.linalg.norm(q_vec)
        norm_v = np.linalg.norm(vec)
        if norm_q == 0 or norm_v == 0:
            continue
        sim = float(np.dot(q_vec, vec) / (norm_q * norm_v))
        sims.append((sim, row))

    sims = sorted(sims, key=lambda x: x[0], reverse=True)[:top_k]

    long_context_text = ""
    for sim, row in sims:
        long_context_text += f"User: {row.get('message')}\nBot: {row.get('reply')}\n"

    if debug:
        for sim, row in sims:
            print(f"🔹 {row.get('id')} → sim={sim:.3f}")

    return long_context_text


# --- Test ---
if __name__ == "__main__":
    uid = "d3f893c7-2751-40f3-9bb4-b201ac8987a0"
    sess = "session_abc123"

    print("\n=== Short-term context (latest 5) ===")
    short_ctx = get_latest_messages(uid, session_id=sess, limit=5)
    for row in short_ctx:
        print(row)

    print("\n=== Long-term context ===")
    long_ctx = get_long_term_context(uid, "Đồ ăn healthy là gì", session_id=sess, top_k=5, debug=True)
    print(long_ctx)
