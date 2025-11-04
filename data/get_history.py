from supabase import create_client
import os
from dotenv import load_dotenv
from data.embed_messages import embedder
import numpy as np
import ast

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Lấy tin nhắn theo session_id
def get_latest_messages(user_id, session_id=None, limit=10):
    """
    Lấy `limit` tin nhắn gần nhất của user, có thể lọc theo session_id.
    """
    try:
        query = (
            supabase.table("messages_test")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if session_id:
            query = query.eq("session_id", session_id)

        response = query.execute()
        return response.data if hasattr(response, "data") else []
    except Exception as e:
        print("❌ Lỗi khi lấy lịch sử chat:", e)
        return []


def get_all_messages(user_id, session_id=None):
    """
    Lấy toàn bộ tin nhắn của user, có thể lọc theo session_id.
    """
    try:
        query = (
            supabase.table("messages_test")
            .select("message, reply, created_at")
            .eq("user_id", user_id)
            .order("id", desc=False)
        )
        if session_id:
            query = query.eq("session_id", session_id)

        response = query.execute()
        return response.data if hasattr(response, "data") else []
    except Exception as e:
        print("❌ Lỗi khi lấy tất cả tin nhắn:", e)
        return []


# Convert + embedding context
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
        if s.startswith('[') and s.endswith(']'):
            try:
                parsed = ast.literal_eval(s)
                return np.asarray([float(x) for x in parsed], dtype=float)
            except Exception:
                pass
        if s.startswith('{') and s.endswith('}'):
            inner = s[1:-1]
            parts = [p.strip().strip('"').strip("'") for p in inner.split(',') if p.strip()]
            try:
                return np.asarray([float(p) for p in parts], dtype=float)
            except Exception:
                return None
        parts = [p.strip().strip('"').strip("'") for p in s.split(',') if p.strip()]
        try:
            return np.asarray([float(p) for p in parts], dtype=float)
        except Exception:
            return None
    return None


def get_long_term_context(user_id: str, query: str, session_id=None, top_k: int = 5, debug: bool = False):
    """
    Lấy long-term context theo user_id (và session_id nếu có).
    """
    q_vec = embedder.embed(query)
    q_vec = to_float_array(q_vec)
    if q_vec is None:
        raise ValueError("Không thể tạo vector cho query")

    query_builder = (
        supabase.table("messages_test")
        .select("id, message, reply, embedding_vector")
        .eq("user_id", user_id)
        .not_.is_("embedding_vector", None)
    )
    if session_id:
        query_builder = query_builder.eq("session_id", session_id)

    resp = query_builder.execute()
    rows = resp.data or []
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

    return long_context_text


# Test
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
