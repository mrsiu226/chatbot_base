# Hướng dẫn Cài đặt và Sử dụng Chatbot - Hoàn thành

## ✅ Cài đặt thành công!

Ứng dụng chatbot đã được cài đặt thành công với Python3 và đang chạy trên:
- **URL:** http://127.0.0.1:8200
- **Process ID:** Xem với `./start.sh status`

## 📁 Cấu trúc Project

```
/home/chatbotySia/chatbot.whoisme.ai/
├── chatbot_base/          # Thư mục chính của ứng dụng
│   ├── venv/             # Virtual environment (Python 3.8)
│   ├── ai_bot.py         # File chính của ứng dụng Flask
│   ├── requirements.txt  # Dependencies đã được cài đặt
│   ├── gunicorn.conf.py  # Cấu hình Gunicorn server
│   ├── start.sh          # Script khởi động/dừng ứng dụng
│   └── .env              # File cấu hình môi trường
└── logs/                 # Thư mục log files
    ├── gunicorn_access.log
    ├── gunicorn_error.log
    └── gunicorn.pid
```

## 🚀 Các lệnh quản lý ứng dụng

Tất cả các lệnh phải chạy từ thư mục: `/home/chatbotySia/chatbot.whoisme.ai/chatbot_base/`

### ⭐ SYSTEMD SERVICE (Khuyến khích) ⭐

Ứng dụng hiện chạy như một systemd service và sẽ tự động khởi động cùng server.

```bash
cd /home/chatbotySia/chatbot.whoisme.ai/chatbot_base

# Quản lý service với script tiện lợi
./service.sh start      # Khởi động service
./service.sh stop       # Dừng service  
./service.sh restart    # Khởi động lại service
./service.sh status     # Kiểm tra trạng thái
./service.sh logs       # Xem logs trực tiếp
./service.sh enable     # Bật tự động khởi động
./service.sh disable    # Tắt tự động khởi động
```

### Hoặc sử dụng systemctl trực tiếp:
```bash
sudo systemctl start chatbot-whoisme.service
sudo systemctl stop chatbot-whoisme.service  
sudo systemctl restart chatbot-whoisme.service
sudo systemctl status chatbot-whoisme.service
```

### Script khởi động truyền thống (backup):
```bash
./start.sh start    # Khởi động
./start.sh stop     # Dừng
./start.sh restart  # Khởi động lại
./start.sh status   # Kiểm tra trạng thái
```

## 🔧 Cấu hình

### Port và địa chỉ:
- Ứng dụng chạy trên: `127.0.0.1:8200`
- Để thay đổi, sửa file `gunicorn.conf.py`

### Database:
- PostgreSQL: Đã cấu hình trong `.env`
- Supabase: Đã cấu hình API keys

### AI APIs:
- Google AI: ✅ Đã cấu hình
- DeepSeek: ✅ Đã cấu hình  
- Grok: ✅ Đã cấu hình

## 📝 Log Files

### Service logs (Systemd):
```bash
# Xem logs trực tiếp (khuyến khích)
./service.sh logs

# Hoặc dùng journalctl
sudo journalctl -u chatbot-whoisme.service -f
sudo journalctl -u chatbot-whoisme.service --since "1 hour ago"
```

### Application logs (Gunicorn):
```bash
# Service output logs
tail -f /home/chatbotySia/chatbot.whoisme.ai/logs/service.log

# Gunicorn logs (nếu chạy bằng start.sh)
tail -f /home/chatbotySia/chatbot.whoisme.ai/logs/gunicorn_error.log
tail -f /home/chatbotySia/chatbot.whoisme.ai/logs/gunicorn_access.log
```

## 🌐 Truy cập ứng dụng

1. **Web Interface:** http://127.0.0.1:8200
2. **Login Page:** http://127.0.0.1:8200/login-ui
3. **Register Page:** http://127.0.0.1:8200/register-ui

## 🛠️ Dependencies đã cài đặt

- ✅ Flask web framework
- ✅ LangChain for AI integration
- ✅ OpenAI API client
- ✅ Google AI APIs
- ✅ Supabase client
- ✅ PostgreSQL client (psycopg2)
- ✅ JWT authentication
- ✅ Sentence transformers
- ✅ FAISS vector database
- ✅ Pandas, NumPy cho data processing
- ✅ Gunicorn production server

## 🔄 Tự động khởi động (Đã được cấu hình)

✅ **Systemd Service đã được enable** - Ứng dụng sẽ tự động khởi động khi server reboot.

Service được cấu hình với:
- **Auto-restart:** Tự động khởi động lại nếu crash
- **Logging:** Tất cả logs được ghi vào `/home/chatbotySia/chatbot.whoisme.ai/logs/service.log`
- **Dependencies:** Chỉ khởi động sau khi network sẵn sàng
- **Resource management:** Systemd quản lý memory và process

### Kiểm tra auto-start:
```bash
# Kiểm tra service có enabled không
systemctl is-enabled chatbot-whoisme.service

# Xem service status
./service.sh status
```

## 🔍 Kiểm tra ứng dụng

```bash
# Kiểm tra process
ps aux | grep gunicorn

# Kiểm tra port
netstat -tlnp | grep 8200

# Test HTTP response
curl -I http://127.0.0.1:8200/
```

## ⚠️ Ghi chú quan trọng

1. **Virtual Environment:** Luôn đảm bảo virtual environment được kích hoạt khi làm việc với project
2. **Permissions:** File `start.sh` đã được cấp quyền thực thi
3. **Environment Variables:** Tất cả API keys và database configs đã được cấu hình trong `.env`
4. **Port 8200:** Đảm bảo port này không bị chiếm bởi ứng dụng khác

## 🎉 Hoàn thành!

Ứng dụng chatbot đã sẵn sàng sử dụng với Python3 và đã được cấu hình như một systemd service!

### ✅ Tính năng hiện tại:
- ✅ **Tự động khởi động** cùng server
- ✅ **Tự động restart** nếu có lỗi
- ✅ **Quản lý bằng systemd** - professional deployment
- ✅ **Logging đầy đủ** với journalctl và file logs
- ✅ **Process management** với 4 worker processes
- ✅ **Memory management** bởi systemd

### 🚀 Sẵn sàng cho Production!