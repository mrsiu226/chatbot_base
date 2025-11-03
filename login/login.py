from flask import Blueprint, request, jsonify, session
from supabase import create_client
import os
import bcrypt
import sys
import requests
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.jwt_helper import generate_jwt_token

login_bp = Blueprint("login", __name__)
verify_bp = Blueprint("verify", __name__)

# ================== Kết nối Supabase ==================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================== LOGIN THƯỜNG ==================
@login_bp.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Thiếu email hoặc password"}), 400

    result = (
        supabase.table("users_aibot")
        .select("*")
        .eq("email", email)
        .limit(1)
        .execute()
    )

    if not result.data:
        return jsonify({"error": "Sai tài khoản hoặc mật khẩu"}), 401

    user = result.data[0]
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

    result = (
        supabase.table("users_aibot")
        .select("*")
        .eq("email", email)
        .limit(1)
        .execute()
    )

    if not result.data:
        return jsonify({"error": "Sai tài khoản hoặc mật khẩu"}), 401

    user = result.data[0]
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
