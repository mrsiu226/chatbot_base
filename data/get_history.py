from supabase import create_client
# from psycopg2.extras import RealDictCursor
# import psycopg2
import os
from dotenv import load_dotenv
from data.embed_messages import embedder
import numpy as np
import ast

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# POSTGRES_URL = os.getenv("DATABASE_URL")
# def get_postgres_conn():
#     return psycopg2.connect(POSTGRES_URL, cursor_factory=RealDictCursor)

def get_latest_messages(user_id, limit=10): #RAG - prompt cho chatbot
    """
    Lấy `limit` records lịch sử chat gần nhất từ bảng messages_test.
    Trả về list các dict, mỗi dict là một bản ghi.
    """
    try:
        response = (
            supabase.table("messages_test")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data if hasattr(response, "data") else []
    except Exception as e:
        print("Lỗi khi lấy lịch sử chat:", e)
        return []  
    
def get_all_messages(user_id): #Hiển thị dữ liệu chat của mối user
    """
    Lấy tất cả records từ bảng messages_test.
    Trả về list các dict, mỗi dict là một bản ghi.
    """
    try:
        response = (
            supabase.table("messages_test")
            .select("message", "reply")
            .eq("user_id", user_id)
            .order("id", desc=False)
            .execute()
        )
        return response.data if hasattr(response, "data") else []
    except Exception as e:
        print("Lỗi khi lấy tất cả tin nhắn:", e)
        return []
    
def to_float_array(raw):
    """
    Chuyển các dạng raw embedding (list, numpy array, string JSON '[..]', Postgres '{..}',
    hoặc list-of-strings) thành numpy.array(dtype=float).
    Trả về None nếu không parse được.
    """
    if raw is None:
        return None

    # Nếu đã là numpy array or list/tuple
    if isinstance(raw, (np.ndarray, list, tuple)):
        try:
            return np.asarray(raw, dtype=float)
        except Exception:
            # cố parse từng phần tử (loại bỏ dấu " nếu cần)
            out = []
            for e in raw:
                try:
                    s = str(e).strip().strip('"').strip("'")
                    out.append(float(s))
                except Exception:
                    return None
            return np.asarray(out, dtype=float)

    # Nếu raw là chuỗi: JSON array '[...]' hoặc Postgres '{...}' hoặc CSV-like
    if isinstance(raw, str):
        s = raw.strip()
        # JSON-like list e.g. '["0","0.1", ...]' or [0, 0.1]
        if s.startswith('[') and s.endswith(']'):
            try:
                parsed = ast.literal_eval(s)  # an toàn hơn json.loads cho nhiều trường hợp
                return np.asarray([float(x) for x in parsed], dtype=float)
            except Exception:
                pass
        # Postgres array: {0,0.1, ...}
        if s.startswith('{') and s.endswith('}'):
            inner = s[1:-1]
            parts = [p.strip().strip('"').strip("'") for p in inner.split(',') if p.strip() != '']
            try:
                return np.asarray([float(p) for p in parts], dtype=float)
            except Exception:
                return None
        # fallback: comma separated string
        parts = [p.strip().strip('"').strip("'") for p in s.split(',') if p.strip() != '']
        try:
            return np.asarray([float(p) for p in parts], dtype=float)
        except Exception:
            return None

    # không thể xử lý
    return None


def get_long_term_context(user_id: str, query: str, top_k: int = 5, debug: bool = False):
    """
    Trả về text long-term context (top_k most similar messages của user_id).
    Safe với nhiều format embedding trong DB.
    """
    # 1) embed query; đảm bảo là numpy float array
    q_vec = embedder.embed(query)
    q_vec = to_float_array(q_vec)
    if q_vec is None:
        raise ValueError("Không thể tạo vector cho query")

    # 2) query DB (chỉ lấy những hàng có embedding không null)
    resp = (
        supabase.table("messages_test")
        .select("id, message, reply, embedding_vector")
        .eq("user_id", user_id)
        .not_.is_("embedding_vector", None)
        .order("id", desc=False)
        .execute()
    )

    rows = resp.data or []
    if not rows:
        return ""

    sims = []
    skipped = 0
    for row in rows:
        raw = row.get("embedding_vector")
        vec = to_float_array(raw)
        if vec is None:
            skipped += 1
            if debug:
                print(f"[SKIP] id={row.get('id')} - cannot parse embedding")
            continue

        # nếu chiều khác nhau thì bỏ qua (hoặc bạn có thể trim/pad tuỳ ý)
        if vec.shape != q_vec.shape:
            skipped += 1
            if debug:
                print(f"[SKIP] id={row.get('id')} - shape mismatch q:{q_vec.shape} vs v:{vec.shape}")
            continue

        # tính cosine similarity an toàn
        norm_q = np.linalg.norm(q_vec)
        norm_v = np.linalg.norm(vec)
        if norm_q == 0 or norm_v == 0:
            skipped += 1
            if debug:
                print(f"[SKIP] id={row.get('id')} - zero norm")
            continue

        sim = float(np.dot(q_vec, vec) / (norm_q * norm_v))
        sims.append((sim, row))

    # sắp xếp và lấy top_k
    sims = sorted(sims, key=lambda x: x[0], reverse=True)[:top_k]

    # build text context
    long_context_text = ""
    for sim, row in sims:
        long_context_text += f"User: {row.get('message')}\n{row.get('reply')}\n"

    if debug:
        print(f"Total rows: {len(rows)}, used: {len(sims)}, skipped: {skipped}")

    return long_context_text

if __name__ == "__main__":
    uid = "d3f893c7-2751-40f3-9bb4-b201ac8987a0"

    print("\n=== Short-term context (latest 5) ===")
    short_ctx = get_latest_messages(uid, 5)
    for row in short_ctx:
        print(row)

    print("\n=== Long-term context (related to 'Tối ăn gì nhỉ') ===")
    long_ctx = get_long_term_context(uid, "Đồ ăn healthy là một lựa chọn không tồi", 5, debug=True)
    print(long_ctx)
