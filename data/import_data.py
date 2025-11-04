from supabase import create_client
import os
from dotenv import load_dotenv
from data.embed_messages import embedder

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def insert_message(user_id, user_message, bot_reply, session_id=None):
    """Chèn message mới + embedding vector + session_id"""
    try:
        embedding = None
        if user_message:
            embedding = embedder.embed(user_message).tolist()

        data = {
            "user_id": user_id,
            "message": user_message,
            "reply": bot_reply,
            "embedding_vector": embedding
        }

        # Nếu có session_id thì thêm vào bản ghi
        if session_id:
            data["session_id"] = session_id

        response = supabase.table("messages_test").insert(data).execute()

        print(f"💬 Tin nhắn đã được chèn thành công (session_id={session_id})")
        return response.data

    except Exception as e:
        print("❌ Lỗi khi chèn tin nhắn:", e)
        return None


def insert_user(email: str, password_hash: str):
    """Chèn user mới vào bảng users"""
    try:
        supabase.table("users_aibot").insert({
            "email": email,
            "password_hash": password_hash
        }).execute()
        print(f"👤 User {email} đã được tạo thành công!")
    except Exception as e:
        print("❌ Lỗi khi chèn user:", e)


if __name__ == "__main__":
    insert_message(
        user_id="d3f893c7-2751-40f3-9bb4-b201ac8987a0",
        user_message="Tôi nên làm AI Engineer hay Data Engineer?",
        bot_reply="Tùy vào sở thích và kỹ năng của bạn mà lựa chọn phù hợp nhé!",
        session_id="test-session-001"
    )
