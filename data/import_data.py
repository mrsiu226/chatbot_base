import psycopg2
import os
from dotenv import load_dotenv
from data.embed_messages import embedder

load_dotenv()

LOCAL_DB_URL = os.getenv("POSTGRES_URL")

# --- Kết nối PostgreSQL local ---
conn = psycopg2.connect(LOCAL_DB_URL)
cursor = conn.cursor()

print("✅ Đã kết nối tới PostgreSQL local thành công.")


def insert_message(user_id, user_message, bot_reply, session_id=None):
    """Chèn message mới + embedding vector + session_id vào local PostgreSQL"""
    try:
        embedding = None
        if user_message:
            embedding = embedder.embed(user_message).tolist()

        # Nếu bảng có schema whoisme thì ghi rõ
        cursor.execute("""
            INSERT INTO whoisme.messages (user_id, message, reply, embedding_vector, session_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, user_message, bot_reply, str(embedding), session_id))

        conn.commit()
        print(f"💬 Tin nhắn đã được chèn thành công (session_id={session_id})")

    except Exception as e:
        print("❌ Lỗi khi chèn tin nhắn:", e)
        conn.rollback()


def insert_user(email: str, password_hash: str):
    """Chèn user mới vào bảng users, nếu email đã tồn tại thì bỏ qua"""
    try:
        # Kiểm tra user đã tồn tại chưa
        cursor.execute("""
            SELECT id FROM whoisme.users WHERE email = %s
        """, (email,))
        existing = cursor.fetchone()

        if existing:
            print(f"⚠️ User {email} đã tồn tại, bỏ qua.")
            return

        cursor.execute("""
            INSERT INTO whoisme.users (email, password_hash)
            VALUES (%s, %s)
        """, (email, password_hash))
        conn.commit()
        print(f"👤 User {email} đã được tạo thành công!")

    except Exception as e:
        print("❌ Lỗi khi chèn user:", e)
        conn.rollback()


if __name__ == "__main__":
    insert_message(
        user_id="d3f893c7-2751-40f3-9bb4-b201ac8987a0",
        user_message="Tôi nên làm AI Engineer hay Data Engineer?",
        bot_reply="Tùy vào sở thích và kỹ năng của bạn mà lựa chọn phù hợp nhé!",
        session_id="test-session-001"
    )
