import psycopg2
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# --- Load biến môi trường ---
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
LOCAL_DB_URL = os.getenv("POSTGRES_URL")

# --- Kết nối Supabase & local PostgreSQL ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
local_conn = psycopg2.connect(LOCAL_DB_URL)
local_cursor = local_conn.cursor()

print("✅ Supabase and local PostgreSQL connections established.")

# --- Lấy dữ liệu từ Supabase ---
users = supabase.table("users_aibot").select("*").execute().data
messages = supabase.table("messages_test").select("*").execute().data
whoisme = supabase.table("embeddings").select("*").execute().data

print(f"📦 Found {len(users)} users, {len(messages)} messages, {len(whoisme)} whoisme records.")

# ===============================
# 🔹 Helper function: check tồn tại ID
# ===============================
def record_exists(table: str, record_id):
    local_cursor.execute(f"SELECT 1 FROM {table} WHERE id = %s LIMIT 1;", (record_id,))
    return local_cursor.fetchone() is not None


# ===============================
# 🔹 Insert Users
# ===============================
for u in users:
    if record_exists("whoisme.users", u["id"]):
        print(f"⏩ User {u['id']} already exists, skipping.")
        continue

    local_cursor.execute("""
        INSERT INTO whoisme.users (id, email, password_hash, source)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """, (u["id"], u["email"], u["password_hash"], u.get("source")))

print("✅ Users migrated.")


# ===============================
# 🔹 Insert Messages
# ===============================
for m in messages:
    if record_exists("whoisme.messages", m["id"]):
        print(f"⏩ Message {m['id']} already exists, skipping.")
        continue

    local_cursor.execute("""
        INSERT INTO whoisme.messages 
        (id, message, reply, created_at, user_id, embedding_vector, session_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """, (
        m["id"], m["message"], m["reply"], m["created_at"],
        m["user_id"], str(m.get("embedding_vector")), m.get("session_id")
    ))

print("✅ Messages migrated.")


# ===============================
# 🔹 Insert Whoisme data
# ===============================
for w in whoisme:
    if record_exists("whoisme.embeddings", w["id"]):
        print(f"⏩ Whoisme record {w['id']} already exists, skipping.")
        continue

    local_cursor.execute("""
        INSERT INTO whoisme.embeddings (id, name, embedding, text, column_name, row_index, data_hash, updated_at, level)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """, (
        w["id"], w.get("name"), str(w.get("embedding")),
        w.get("text"), w.get("column_name"), w.get("row_index"),
        w.get("data_hash"), w.get("updated_at"), w.get("level")
    ))

print("✅ Whoisme embeddings migrated.")


# ===============================
# 🔹 Commit & Close
# ===============================
local_conn.commit()
local_cursor.close()
local_conn.close()

print("🎉 Data migration completed successfully!")
