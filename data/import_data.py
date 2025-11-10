import psycopg2
import os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from data.embed_messages import embedder

load_dotenv()
LOCAL_DB_URL = os.getenv("POSTGRES_URL")


def get_conn():
    return psycopg2.connect(LOCAL_DB_URL, cursor_factory=RealDictCursor)

def insert_message(user_id, message, reply=None, session_id=None, time_spent=None):
    try:
        embedding_vector = embedder.embed(message).tolist()
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO whoisme.messages (user_id, session_id, message, reply, embedding_vector, time)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (str(user_id), session_id, message, reply, embedding_vector, time_spent or 0),
                )
            conn.commit()
            print(f"Tin nhắn đã được chèn thành công (session_id={session_id})")
    except Exception as e:
        print(f"[ERROR insert_message]: {e}")


def insert_user(email: str, password_hash: str):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM whoisme.users WHERE email = %s",
                    (email,),
                )
                existing = cur.fetchone()
                if existing:
                    print(f"⚠️ User {email} đã tồn tại, bỏ qua.")
                    return
                cur.execute(
                    """
                    INSERT INTO whoisme.users (email, password_hash)
                    VALUES (%s, %s)
                    """,
                    (email, password_hash),
                )
            conn.commit()
            print(f"User {email} đã được tạo thành công!")

    except Exception as e:
        print("Lỗi khi chèn user:", e)

# --- Test ---
if __name__ == "__main__":
    insert_message(
        user_id="d3f893c7-2751-40f3-9bb4-b201ac8987a0",
        message="Tôi nên làm AI Engineer hay Data Engineer?",
        reply="Tùy vào sở thích và kỹ năng của bạn mà lựa chọn phù hợp nhé!",
        session_id="test-session-001",
    )
