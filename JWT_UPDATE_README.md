# 🔐 JWT Authentication Update

## Tổng quan thay đổi

Route `/v1/chat` đã được cập nhật để sử dụng **JWT (JSON Web Token) authentication** thay vì API key authentication để tăng cường bảo mật và quản lý user tốt hơn.

## ✨ Các tính năng mới

### 1. JWT Authentication System
- ✅ JWT token-based authentication
- ✅ Token tự động hết hạn (24 giờ)
- ✅ User-specific authentication
- ✅ Secure token generation và verification

### 2. API Endpoints mới
- ✅ `POST /api/login` - Login để lấy JWT token
- ✅ `POST /v1/chat` - Chat API với JWT authentication

### 3. Tự động lưu lịch sử
- ✅ API tự động lưu tin nhắn của từng user
- ✅ Liên kết tin nhắn với user thông qua JWT token

## 📁 Files được thêm/sửa đổi

### Files mới:
- `utils/jwt_helper.py` - JWT utility functions
- `JWT_API_DOCS.md` - Tài liệu API chi tiết
- `test_jwt_auth.py` - Script test JWT authentication
- `.env.example` - Cập nhật với JWT_SECRET_KEY

### Files được sửa đổi:
- `requirements.txt` - Thêm PyJWT
- `ai_bot.py` - Cập nhật route `/v1/chat` với JWT auth
- `login/login.py` - Thêm endpoint `/api/login` cho JWT

## 🚀 Cách sử dụng

### 1. Cấu hình Environment
Thêm vào file `.env`:
```bash
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production
```

### 2. Cài đặt dependencies mới
```bash
pip install -r requirements.txt
```

### 3. Login để lấy JWT token
```bash
curl -X POST http://localhost:5000/api/login \\
  -H "Content-Type: application/json" \\
  -d '{"email": "your_email@example.com", "password": "your_password"}'
```

Response:
```json
{
  "success": true,
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "user_id_here",
    "email": "your_email@example.com"
  }
}
```

### 4. Sử dụng JWT token với Chat API
```bash
curl -X POST http://localhost:5000/v1/chat \\
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE" \\
  -H "Content-Type: application/json" \\
  -d '{"message": "Xin chào", "model": "gemini-flash-lite"}' \\
  --no-buffer
```

## 🔧 Testing

Chạy script test để kiểm tra JWT authentication:
```bash
python test_jwt_auth.py
```

**Lưu ý:** Trước khi chạy test, hãy:
1. Tạo user test trong database
2. Đảm bảo server đang chạy
3. Cấu hình đúng email/password trong script

## ⚡ So sánh với API Key Authentication

| Tính năng | API Key (Cũ) | JWT Token (Mới) |
|-----------|--------------|----------------|
| Bảo mật | ❌ Static key | ✅ Dynamic token |
| Hết hạn | ❌ Không | ✅ 24 giờ |
| User tracking | ❌ Không | ✅ Per-user |
| Lưu lịch sử | ❌ Không | ✅ Tự động |
| Scalability | ❌ Thấp | ✅ Cao |

## 🛡️ Bảo mật

### JWT Secret Key
- Sử dụng secret key mạnh trong production
- Không commit secret key vào git
- Định kỳ rotate secret key

### Token Security
- Token tự động hết hạn sau 24 giờ
- Stateless - không cần session storage
- Signed và verified với HS256 algorithm

## 📚 Tài liệu chi tiết

Xem `JWT_API_DOCS.md` để có hướng dẫn chi tiết về:
- Cách tích hợp với Python, JavaScript, cURL
- Xử lý lỗi
- Best practices
- Ví dụ code đầy đủ

## 🔄 Migration từ API Key

### Cho developers hiện tại:
1. Cập nhật code để login lấy JWT token trước
2. Thay thế API key bằng JWT token trong header
3. Xử lý token expiration (login lại khi hết hạn)

### Backward compatibility:
- Route `/chat` với session auth vẫn hoạt động bình thường
- Chỉ route `/v1/chat` chuyển sang JWT auth
- API key authentication đã bị remove khỏi `/v1/chat`

## 🤝 Support

Nếu gặp vấn đề với JWT authentication:
1. Kiểm tra JWT_SECRET_KEY trong `.env`
2. Đảm bảo PyJWT đã được cài đặt
3. Chạy test script để debug
4. Check server logs để xem lỗi chi tiết