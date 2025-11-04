from flask import Blueprint, request, jsonify
from flask_bcrypt import Bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

# ================== Cấu hình ==================
load_dotenv()
bcrypt = Bcrypt()
register_bp = Blueprint("register_bp", __name__)

LOCAL_DB_URL = os.getenv("POSTGRES_URL")

def get_connection():
    """Tạo kết nối PostgreSQL local"""
    return psycopg2.connect(LOCAL_DB_URL, cursor_factory=RealDictCursor)


# ================== API REGISTER ==================
@register_bp.route("/register", methods=["POST"])
def register():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Thiếu email hoặc mật khẩu"}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Kiểm tra xem email đã tồn tại chưa
        cur.execute("SELECT id FROM whoisme.users WHERE email = %s LIMIT 1;", (email,))
        existing_user = cur.fetchone()
        if existing_user:
            cur.close()
            conn.close()
            return jsonify({"error": "Email đã được đăng ký"}), 400

        # Hash mật khẩu
        pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")

        # Chèn user mới
        cur.execute("""
            INSERT INTO whoisme.users (email, password_hash, source)
            VALUES (%s, %s, %s)
            RETURNING id;
        """, (email, pw_hash, "local"))

        new_user = cur.fetchone()
        conn.commit()

        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Đăng ký thành công",
            "user_id": new_user["id"],
            "redirect": "/login-ui"
        }), 200

    except Exception as e:
        print("❌ Lỗi khi đăng ký:", e)
        return jsonify({"error": "Lỗi hệ thống hoặc cơ sở dữ liệu"}), 500
