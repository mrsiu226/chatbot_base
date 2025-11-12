import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import numpy as np
from cachetools import TTLCache
from functools import lru_cache
import time
from data.embed_messages import embedder

load_dotenv()
LOCAL_DB_URL = os.getenv("POSTGRES_URL")

# -----------------------------
# Kết nối DB
# -----------------------------
def get_conn():
    return psycopg2.connect(LOCAL_DB_URL, cursor_factory=RealDictCursor)

# -----------------------------
# Short-term context cache
# -----------------------------
short_term_cache = TTLCache(maxsize=5000, ttl=300)  # 5 phút

def get_latest_messages(user_id, session_id=None, limit=10):
    cache_key = f"{user_id}_{session_id or 'global'}"
    if cache_key in short_term_cache:
        return short_term_cache[cache_key]

    try:
        with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            if session_id:
                cur.execute("""
                    SELECT id, message, reply, created_at, session_id
                    FROM whoisme.messages
                    WHERE user_id = %s AND session_id = %s AND is_deleted = FALSE
                    ORDER BY created_at DESC
                    LIMIT %s;
                """, (str(user_id), str(session_id), limit))
            else:
                cur.execute("""
                    SELECT id, message, reply, created_at, session_id
                    FROM whoisme.messages
                    WHERE user_id = %s AND is_deleted = FALSE
                    ORDER BY created_at DESC
                    LIMIT %s;
                """, (str(user_id), limit))
            rows = cur.fetchall()
            short_term_cache[cache_key] = rows
            return rows
    except Exception as e:
        print(f"[get_latest_messages] Lỗi: {e}")
        return []

# -----------------------------
# Long-term context cache (RAG)
# -----------------------------
rag_cache = TTLCache(maxsize=2000, ttl=300)

def to_float_array(vec):
    if vec is None:
        return None
    if isinstance(vec, (list, tuple, np.ndarray)):
        return np.asarray(vec, dtype=float)
    if isinstance(vec, str):
        try:
            return np.asarray(eval(vec), dtype=float)
        except Exception:
            return None
    return None

@lru_cache(maxsize=2000)
def cached_embed_query(text: str):
    return embedder.embed(text)

def get_long_term_context(user_id: str, query: str, session_id=None, top_k: int = 5, debug: bool = False):
    cache_key = f"{user_id}_{session_id or 'global'}_{query}_{top_k}"
    if cache_key in rag_cache:
        if debug:
            print(f"[RAG Cache Hit] {cache_key}")
        return rag_cache[cache_key]

    start_total = time.time()

    t0 = time.time()
    q_vec = to_float_array(cached_embed_query(query))
    embed_time = time.time() - t0

    if q_vec is None:
        if debug:
            print("[get_long_term_context] ⚠️ Không tạo được vector query")
        return ""

    try:
        with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            t1 = time.time()
            if session_id:
                cur.execute("""
                    SELECT id, message, reply,
                        1 - (embedding_vector <=> %s::vector) AS similarity
                    FROM whoisme.messages
                    WHERE user_id=%s AND session_id=%s
                        AND embedding_vector IS NOT NULL
                    ORDER BY embedding_vector <=> %s::vector
                    LIMIT %s;
                """, (q_vec.tolist(), str(user_id), str(session_id), q_vec.tolist(), top_k))
            else:
                cur.execute("""
                    SELECT id, message, reply,
                        1 - (embedding_vector <=> %s::vector) AS similarity
                    FROM whoisme.messages
                    WHERE user_id=%s AND embedding_vector IS NOT NULL
                    ORDER BY embedding_vector <=> %s::vector
                    LIMIT %s;
                """, (q_vec.tolist(), str(user_id), q_vec.tolist(), top_k))

            rows = cur.fetchall()
            query_time = time.time() - t1
            total_time = time.time() - start_total

            if debug:
                print(f"[⏱Embed time] {embed_time:.3f}s")
                print(f"[⏱Query time] {query_time:.3f}s")
                print(f"[Total RAG time] {total_time:.3f}s")
                for r in rows:
                    print(f"   🔹 {r['id']} → sim={r['similarity']:.3f}")

            if not rows:
                return ""

            context_text = "\n".join([
                f"User: {r['message']}\nBot: {r['reply']}"
                for r in rows
            ])

            rag_cache[cache_key] = context_text
            return context_text

    except Exception as e:
        print(f"[get_long_term_context] Lỗi PostgreSQL: {e}")
        return ""

def get_full_history(user_id: str, session_id: str):
    try:
        with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, message, reply, created_at
                FROM whoisme.messages
                WHERE user_id = %s 
                    AND session_id = %s
                    AND is_deleted = FALSE
                ORDER BY created_at ASC;
            """, (str(user_id), str(session_id)))
            rows = cur.fetchall()

            messages = [
                {
                    "id": r["id"],
                    "message": r["message"],
                    "reply": r["reply"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None
                }
                for r in rows
            ]

            return messages
    except Exception as e:
        print(f"[get_full_history] Lỗi PostgreSQL: {e}")
        return []

# -----------------------------
# Test nhanh
# -----------------------------
if __name__ == "__main__":
    uid = "1000000405"
    sess = "test-session-001"

    print("=== Short-term context ===")
    short_ctx = get_latest_messages(uid, sess, 5)
    for row in reversed(short_ctx):
        print(f"User: {row['message']}\nBot: {row['reply']}")

    print("\n=== Long-term context ===")
    long_ctx = get_long_term_context(uid, "Đồ ăn healthy là gì", sess, top_k=5, debug=True)
    print(long_ctx)
