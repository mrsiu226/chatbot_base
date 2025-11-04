from flask import Blueprint, request, jsonify, session
import os
import sys
import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.jwt_helper import generate_jwt_token

login_bp = Blueprint("login", __name__)

# ================== Kết nối PostgreSQL local ==================
LOCAL_DB_URL = os.getenv("POSTGRES_URL")

def get_connection():
    """Tạo kết nối đến PostgreSQL local"""
    return psycopg2.connect(LOCAL_DB_URL, cursor_factory=RealDictCursor)


# ================== LOGIN THƯỜNG ==================
@login_bp.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Thiếu email hoặc password"}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM whoisme.users WHERE email = %s LIMIT 1;", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        print("❌ Lỗi kết nối PostgreSQL:", e)
        return jsonify({"error": "Lỗi máy chủ"}), 500

    if not user:
        return jsonify({"error": "Sai tài khoản hoặc mật khẩu"}), 401

    stored_hash = user.get("password_hash")
    if not stored_hash:
        return jsonify({"error": "User chưa có password"}), 401

    if bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
        session["user"] = {"id": user["id"], "email": user["email"]}
        return jsonify({"success": True, "redirect": "/chatbot"}), 200
    else:
        return jsonify({"error": "Sai tài khoản hoặc mật khẩu"}), 401


# ================== API LOGIN (JWT TOKEN) ==================
@login_bp.route("/api/login", methods=["POST"])
def api_login():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Thiếu email hoặc password"}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM whoisme.users WHERE email = %s LIMIT 1;", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        print("❌ Lỗi kết nối PostgreSQL:", e)
        return jsonify({"error": "Lỗi máy chủ"}), 500

    if not user:
        return jsonify({"error": "Sai tài khoản hoặc mật khẩu"}), 401

    stored_hash = user.get("password_hash")
    if not stored_hash:
        return jsonify({"error": "User chưa có password"}), 401

    if bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
        jwt_token = generate_jwt_token(user["id"], user["email"])
        return jsonify({
            "success": True,
            "access_token": jwt_token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"]
            }
        }), 200
    else:
        return jsonify({"error": "Sai tài khoản hoặc mật khẩu"}), 401
