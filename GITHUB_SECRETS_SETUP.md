# 🔐 Hướng dẫn cấu hình GitHub Secrets cho Auto Deploy

Để GitHub Action có thể tự động deploy lên server, bạn cần cấu hình các **Repository Secrets** trong GitHub.

## 📋 Các Secrets cần thiết

Truy cập: `Repository Settings` → `Secrets and variables` → `Actions` → `New repository secret`

### 1. SERVER_HOST
- **Tên**: `SERVER_HOST`  
- **Giá trị**: IP hoặc domain của server (ví dụ: `192.168.1.100` hoặc `your-server.com`)

### 2. SERVER_USERNAME  
- **Tên**: `SERVER_USERNAME`
- **Giá trị**: Username để SSH vào server (ví dụ: `ubuntu`, `root`, `deploy`)

### 3. SERVER_SSH_KEY
- **Tên**: `SERVER_SSH_KEY`
- **Giá trị**: Private SSH key để kết nối server

#### 🔑 Tạo SSH Key (nếu chưa có):
```bash
# Trên máy local hoặc server
ssh-keygen -t rsa -b 4096 -C "deploy@github-actions"

# Copy public key lên server
ssh-copy-id username@your-server.com

# Copy private key content để paste vào GitHub Secret
cat ~/.ssh/id_rsa
```

### 4. PROJECT_ROOT
- **Tên**: `PROJECT_ROOT`
- **Giá trị**: Đường dẫn thư mục gốc trên server (ví dụ: `/var/www/chatbot` hoặc `/home/ubuntu/projects`)

### 5. SERVER_PORT (Optional)
- **Tên**: `SERVER_PORT`
- **Giá trị**: Port SSH của server (mặc định: `22`)

### 6. TELEGRAM_BOT_TOKEN 🤖
- **Tên**: `TELEGRAM_BOT_TOKEN`
- **Giá trị**: Token của Telegram Bot để gửi thông báo

#### 🤖 Tạo Telegram Bot:
```bash
1. Mở Telegram và tìm @BotFather
2. Gửi lệnh: /newbot
3. Đặt tên cho bot: "Deploy Notifications Bot"
4. Đặt username: "your_deploy_bot"
5. Copy token nhận được (dạng: 123456789:ABCdefGHI...)
```

### 7. TELEGRAM_CHAT_ID 💬
- **Tên**: `TELEGRAM_CHAT_ID`
- **Giá trị**: Chat ID để gửi thông báo (cá nhân hoặc group)

#### 📱 Lấy Chat ID:
```bash
# Phương pháp 1: Personal chat
1. Gửi tin nhắn cho bot của bạn
2. Truy cập: https://api.telegram.org/bot<TOKEN>/getUpdates
3. Tìm "chat":{"id": số_chat_id}

# Phương pháp 2: Group chat
1. Thêm bot vào group
2. Gửi tin nhắn mention bot: "@your_bot hello"
3. Truy cập: https://api.telegram.org/bot<TOKEN>/getUpdates
4. Tìm chat ID (số âm cho group)

# Phương pháp 3: Sử dụng @userinfobot
1. Forward tin nhắn của bạn cho @userinfobot
2. Bot sẽ trả lời với User ID của bạn
```

## 🖼️ Ví dụ cấu hình

### Server Secrets:
```
SERVER_HOST = 192.168.1.100
SERVER_USERNAME = ubuntu  
SERVER_SSH_KEY = -----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1234567890...
...full private key content...
-----END RSA PRIVATE KEY-----
PROJECT_ROOT = /var/www/chatbot
SERVER_PORT = 22
```

### Telegram Secrets:
```
TELEGRAM_BOT_TOKEN = 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID = 987654321
# Hoặc group chat ID (số âm): -1001234567890
```

## ✅ Kiểm tra cấu hình

Sau khi thêm secrets, bạn có thể test bằng cách:

1. **Push code lên main branch** hoặc
2. **Trigger thủ công**: `Actions` → `Deploy to Server` → `Run workflow`

## 🔐 Bảo mật

- ✅ Không bao giờ commit SSH keys vào code
- ✅ Sử dụng SSH key riêng cho deployment
- ✅ Giới hạn quyền của user deploy trên server
- ✅ Thường xuyên rotate SSH keys
- ✅ Monitor deployment logs

## 🚨 Lưu ý quan trọng

1. **SSH Key Format**: Phải là private key hoàn chỉnh bao gồm header và footer
2. **Server Permissions**: User phải có quyền sudo để quản lý systemd service
3. **Project Directory**: Đảm bảo PROJECT_ROOT có quyền ghi
4. **Git Access**: Server phải có thể clone từ GitHub (public repo hoặc có SSH key)

## 🔄 Quy trình Auto Deploy

Khi có commit mới vào `main` branch:

1. 🔍 GitHub Action checkout code
2. 🐍 Setup Python environment  
3. 📦 Install dependencies
4. 🔗 SSH vào server
5. 📥 Pull/clone code mới
6. 🔧 Cài đặt dependencies trên server
7. ⚙️ Cập nhật cấu hình
8. 🚀 Deploy systemd service
9. ✅ Kiểm tra service status
10. 🎉 Thông báo kết quả

## 📱 Telegram Notifications

Sau khi cấu hình Telegram, bạn sẽ nhận được thông báo với thông tin:

### ✅ Deploy thành công:
```
🚀 Deployment Successful!

📦 Repository: daohuong605/chatbot_base
� Branch: main
👤 Author: Your Name
💬 Commit: abc1234 - Fix bug in health check
🕐 Time: 2025-11-06 14:30:15 UTC
🖥️ Server: your-server.com

✅ Chatbot service is now running with the latest code!
```

### ❌ Deploy thất bại:
```
🚨 Deployment Failed!

📦 Repository: daohuong605/chatbot_base
🌿 Branch: main
👤 Author: Your Name
💬 Commit: def5678 - Update dependencies
🕐 Time: 2025-11-06 14:30:15 UTC
🖥️ Server: your-server.com

❌ Please check the deployment logs and fix the issues.
```

## �🎯 Kết quả

Sau khi cấu hình xong, mỗi lần push code lên main sẽ tự động:
- ✅ Update code trên server
- ✅ Restart service
- ✅ Kiểm tra health check
- ✅ **Gửi thông báo Telegram**