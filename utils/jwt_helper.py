"""
JWT Authentication Helper
Provides functions to generate and verify JWT tokens for API authentication
"""
import jwt
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from dotenv import load_dotenv

load_dotenv()

# JWT Secret Key - should be kept secret in production
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24  # Token expires after 24 hours

def generate_jwt_token(user_id: str, email: str) -> str:
    """
    Generate JWT token for authenticated user
    
    Args:
        user_id (str): User ID from database
        email (str): User email address
        
    Returns:
        str: JWT token string
    """
    payload = {
        "user_id": user_id,
        "email": email,
        "iat": datetime.utcnow(),  # Issued at
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)  # Expiration
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token

def verify_jwt_token(token: str) -> dict:
    """
    Verify and decode JWT token
    
    Args:
        token (str): JWT token string
        
    Returns:
        dict: Decoded payload if token is valid
        
    Raises:
        jwt.ExpiredSignatureError: Token has expired
        jwt.InvalidTokenError: Token is invalid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise jwt.ExpiredSignatureError("Token has expired")
    except jwt.InvalidTokenError:
        raise jwt.InvalidTokenError("Invalid token")

def jwt_required(f):
    """
    Decorator to require JWT authentication for API endpoints
    
    Usage:
        @app.route("/protected-route")
        @jwt_required
        def protected_function():
            # Access current user via g.current_user
            return jsonify({"user": g.current_user})
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header:
            return jsonify({"error": "Missing Authorization header"}), 401
            
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Invalid Authorization header format. Use 'Bearer <token>'"}), 401
            
        token = auth_header.split(" ")[1]
        
        try:
            payload = verify_jwt_token(token)
            # Make user data available to the route function
            request.current_user = {
                "user_id": payload["user_id"],
                "email": payload["email"]
            }
            return f(*args, **kwargs)
            
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        except Exception as e:
            return jsonify({"error": f"Token verification failed: {str(e)}"}), 401
    
    return decorated

def extract_user_from_token() -> dict:
    """
    Extract current user information from JWT token in request
    
    Returns:
        dict: User information {"user_id": str, "email": str}
        None: If no valid token found
    """
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        return None
        
    token = auth_header.split(" ")[1]
    
    try:
        payload = verify_jwt_token(token)
        return {
            "user_id": payload["user_id"],
            "email": payload["email"]
        }
    except:
        return None