from supabase import create_client
from dotenv import load_dotenv
import os

# --- 1️⃣ Load config ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# --- 2️⃣ Kết nối Supabase ---
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
print("✅ Đã kết nối Supabase")

# --- 3️⃣ Định nghĩa SQL function ---
rpc_sql = """
CREATE OR REPLACE FUNCTION public.match_embeddings(
    query_embedding vector(384),
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id bigint,
    sheet_name text,
    column_name text,
    row_index int,
    level text,
    text text,
    data_hash text,
    updated_at timestamp,
    similarity float
)
LANGUAGE sql STABLE
AS $$
    SELECT
        e.id,
        e.sheet_name,
        e.column_name,
        e.row_index,
        e.level,
        e.text,
        e.data_hash,
        e.updated_at,
        1 - (e.embedding <=> query_embedding) AS similarity  -- cosine similarity
    FROM embeddings e
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
$$;
"""

try:
    res = supabase.postgrest.rpc("sql", {"query": rpc_sql})
except Exception as e:
    # supabase client chưa có lệnh "execute SQL", nên ta dùng API RESTful trực tiếp
    from supabase.lib.client_options import ClientOptions
    import requests

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    sql_api_url = f"{SUPABASE_URL}/rest/v1/rpc"
    # PostgREST không hỗ trợ query SQL trực tiếp qua RPC nên ta cần gọi endpoint query riêng:
    # Supabase SQL API: https://supabase.com/docs/guides/api/sql
    sql_exec_url = f"{SUPABASE_URL}/sql/v1"
    resp = requests.post(
        f"{sql_exec_url}/query",
        headers=headers,
        json={"query": rpc_sql},
    )
    if resp.status_code == 200:
        print("✅ RPC function 'match_embeddings' đã được tạo thành công.")
    else:
        print(f"❌ Lỗi khi tạo RPC: {resp.text}")
