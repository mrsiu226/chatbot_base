# JWT Authentication API Documentation

## Tổng quan

Hệ thống API chatbot đã được cập nhật để sử dụng JWT (JSON Web Token) authentication thay vì API key cho route `/v1/chat`. Điều này cung cấp bảo mật tốt hơn và khả năng quản lý user riêng biệt.

## Cách thức hoạt động

1. **Login để lấy JWT token** qua endpoint `/api/login`
2. **Sử dụng JWT token** trong header `Authorization` khi gọi API `/v1/chat`
3. **Token tự động hết hạn** sau 24 giờ (có thể cấu hình)

## Endpoints

### 1. Login để lấy JWT Token

**POST** `/api/login`

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "your_password"
}
```

**Response thành công (200):**
```json
{
  "success": true,
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "user_id_here",
    "email": "user@example.com"
  }
}
```

**Response lỗi (401):**
```json
{
  "error": "Sai tài khoản hoặc mật khẩu"
}
```

### 2. Chat API với JWT Authentication

**POST** `/v1/chat`

**Headers:**
```
Authorization: Bearer <your_jwt_token_here>
Content-Type: application/json
```

**Request Body:**
```json
{
  "message": "Xin chào, tôi cần hỗ trợ",
  "model": "gemini-flash-lite"
}
```

**Response:**
Server-Sent Events (SSE) stream với định dạng:
```
data: {"content": "Xin chào! Tôi có thể giúp gì cho bạn?"}

data: [DONE]
```

## Cách sử dụng

### 1. Với Python requests

```python
import requests
import json

# Bước 1: Login để lấy token
login_data = {
    "email": "your_email@example.com",
    "password": "your_password"
}

response = requests.post("http://localhost:5000/api/login", json=login_data)
token_data = response.json()

if token_data.get("success"):
    access_token = token_data["access_token"]
    
    # Bước 2: Sử dụng token để gọi chat API
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    chat_data = {
        "message": "Tôi muốn tư vấn về AI",
        "model": "gemini-flash-lite"
    }
    
    response = requests.post(
        "http://localhost:5000/v1/chat", 
        json=chat_data, 
        headers=headers,
        stream=True
    )
    
    # Đọc SSE stream
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data: '):
                data = decoded_line[6:]  # Bỏ prefix 'data: '
                if data != '[DONE]':
                    content = json.loads(data)
                    print(content.get('content', ''), end='')
```

### 2. Với cURL

```bash
# Bước 1: Login
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"email": "your_email@example.com", "password": "your_password"}'

# Response sẽ chứa access_token, copy token đó

# Bước 2: Sử dụng token
curl -X POST http://localhost:5000/v1/chat \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"message": "Xin chào", "model": "gemini-flash-lite"}' \
  --no-buffer
```

### 3. Với JavaScript/Fetch

```javascript
// Bước 1: Login
async function login(email, password) {
  const response = await fetch('/api/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password })
  });
  
  const data = await response.json();
  if (data.success) {
    localStorage.setItem('access_token', data.access_token);
    return data.access_token;
  }
  throw new Error(data.error);
}

// Bước 2: Chat với token
async function sendMessage(message, model = 'gemini-flash-lite') {
  const token = localStorage.getItem('access_token');
  
  const response = await fetch('/v1/chat', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message, model })
  });
  
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') {
          return;
        }
        try {
          const json = JSON.parse(data);
          console.log(json.content);
        } catch (e) {
          // Ignore parse errors
        }
      }
    }
  }
}
```

## Cấu hình

Trong file `.env`, thêm:
```
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production
```

**Lưu ý:** Trong production, hãy sử dụng một secret key mạnh và bảo mật.

## Xử lý lỗi

### Token hết hạn (401)
```json
{
  "error": "Token has expired"
}
```
**Giải pháp:** Login lại để lấy token mới.

### Token không hợp lệ (401)
```json
{
  "error": "Invalid token"
}
```
**Giải pháp:** Kiểm tra format token và login lại.

### Thiếu Authorization header (401)
```json
{
  "error": "Missing Authorization header"
}
```
**Giải pháp:** Thêm header `Authorization: Bearer <token>`.

## Ưu điểm của JWT Authentication

1. **Bảo mật cao hơn:** Token có thời hạn, giảm thiểu rủi ro khi bị lộ
2. **Stateless:** Không cần lưu trữ session server-side
3. **User-specific:** Mỗi user có token riêng, dễ tracking và audit
4. **Scalable:** Phù hợp với kiến trúc microservice
5. **Tự động lưu history:** API tự động lưu tin nhắn của từng user