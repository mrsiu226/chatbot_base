import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from cachetools import LRUCache, TTLCache
from contextlib import contextmanager
import numpy as np
from data.embed_messages import embedder

load_dotenv()
class PostgresPool:
    def __init__(self, dsn: str, maxconn: int = 10):
        self.dsn = dsn
        self.maxconn = maxconn
        self.pool = []
        self.used = set()

    def _create_conn(self):
        return psycopg2.connect(self.dsn, cursor_factory=RealDictCursor)

    @contextmanager
    def get_conn(self):
        conn = None
        try:
            if self.pool:
                conn = self.pool.pop()
            else:
                conn = self._create_conn()
            self.used.add(conn)
            yield conn
        finally:
            if conn:
                self.used.discard(conn)
                self.pool.append(conn)


DB_URL = os.getenv("POSTGRES_URL")
pg_pool = PostgresPool(DB_URL, maxconn=15)


short_cache = TTLCache(maxsize=1000, ttl=10)
embedding_cache = LRUCache(maxsize=5000)


SQL_LATEST_HISTORY = """
SELECT message, reply, created_at
FROM whoisme.messages
WHERE user_id = %s
    AND session_id = %s
    AND is_deleted = FALSE
ORDER BY created_at DESC
LIMIT %s
"""

SQL_VECTOR_SEARCH = """
SELECT id, message, reply, embedding_vector <=> %s::vector AS distance
FROM whoisme.messages
WHERE user_id = %s
    AND session_id = %s
    AND is_deleted = FALSE
ORDER BY distance ASC
LIMIT %s
"""

SQL_SESSION_HISTORY = """
SELECT id, message, reply, created_at
FROM whoisme.messages
WHERE user_id = %s 
    AND session_id = %s
    AND is_deleted = FALSE
ORDER BY created_at ASC
"""

def get_embedding(text: str):
    if text in embedding_cache:
        return embedding_cache[text]

    vec = embedder.embed_cached(text)
    embedding_cache[text] = vec
    return vec


def get_latest_history(user_id: str, session_id: str, limit: int = 20):
    cache_key = f"{user_id}:{session_id}:{limit}"

    if cache_key in short_cache:
        return short_cache[cache_key]

    with pg_pool.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(SQL_LATEST_HISTORY, (user_id, session_id, limit))
            rows = cur.fetchall()

    short_cache[cache_key] = rows
    return rows


def _vec_to_pgvector(v):
    try:
        if hasattr(v, "tolist"):
            v = v.tolist()
        return "[" + ",".join(str(float(x)) for x in v) + "]"
    except Exception:
        return "[]"

def rag_search(user_id: str, session_id: str, query: str, limit: int = 5):
    query_vec = get_embedding(query)
    vec_str = _vec_to_pgvector(query_vec)

    with pg_pool.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(SQL_VECTOR_SEARCH, (vec_str, user_id, session_id, limit))
            rows = cur.fetchall()

    if not rows or (rows and rows[0].get("distance", 1.0) > 0.40):
        return get_latest_history(user_id, session_id, limit)

    return rows

def format_messages(rows):
    formatted = []
    for r in rows:
        formatted.append({
            "user": r.get("message", ""),
            "bot": r.get("reply", ""),
            "time": r.get("created_at")
        })
    return formatted


def get_context_messages(user_id: str, session_id: str, query: str = "", limit: int = 20):
    if query and query.strip():
        rag_rows = rag_search(user_id, session_id, query, limit=limit)
        return format_messages(rag_rows)

    latest = get_latest_history(user_id, session_id, limit=limit)
    return format_messages(latest)

def get_full_history(user_id: str, session_id: str):
    try:
        with pg_pool.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(SQL_SESSION_HISTORY, (str(user_id), str(session_id)))
                rows = cur.fetchall()

        messages = [
            {
                "id": r["id"],
                "message": r["message"],
                "reply": r["reply"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None
            } for r in rows
        ]
        return messages
    except Exception as e:
        print(f"[get_full_history] Lỗi PostgreSQL: {e}")
        return []

def get_latest_messages(user_id, session_id, limit=20):
    full = get_full_history(user_id, session_id)
    return full[-limit:]


def get_long_term_context(user_id, query, session_id, top_k=5, debug=False):
    vec = get_embedding(query)
    vec_str = _vec_to_pgvector(vec)

    with pg_pool.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(SQL_VECTOR_SEARCH, (vec_str, user_id, session_id, top_k))
            rows = cur.fetchall()

    if debug:
        print("→ Query vec:", (vec.tolist() if hasattr(vec, "tolist") else vec)[:5], "…")
        print("→ Rows:", rows)

    return rows

if __name__ == "__main__":
    uid = "1000008808"
    sess = "42540164-a3ba-448f-9257-108656bf294e"

    print("Short-term context")
    short_ctx = get_latest_messages(uid, sess, 5)
    for row in reversed(short_ctx):
        print(f"User: {row['message']}\nBot: {row['reply']}")

    print("\nLong-term context")
    long_ctx = get_long_term_context(uid, "Mình là Hương", sess, top_k=5, debug=True)
    print(long_ctx)