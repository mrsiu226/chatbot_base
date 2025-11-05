# 🚀 Hướng dẫn Triển khai Chatbot ở Nhiều Môi trường

Dự án này đã được cấu hình để dễ dàng triển khai ở nhiều nơi khác nhau chỉ bằng cách thay đổi biến môi trường `PROJECT_ROOT`.

## 📁 Cấu trúc Project

```
{PROJECT_ROOT}/
├── chatbot_base/          # Thư mục chính của ứng dụng
│   ├── .env              # File cấu hình (chứa PROJECT_ROOT)
│   ├── gunicorn.conf.py  # Tự động đọc PROJECT_ROOT từ .env
│   ├── start.sh          # Tự động đọc PROJECT_ROOT từ .env
│   ├── service.sh        # Script quản lý service
│   ├── deploy-service.sh # Script tự động deploy systemd service
│   └── ...
└── logs/                 # Thư mục logs (tự động tạo)
```

## 🔧 Cách triển khai ở môi trường mới

### Bước 1: Clone/Copy project
```bash
# Clone về thư mục mong muốn
git clone <repo> /path/to/new/location/chatbot_base
cd /path/to/new/location/chatbot_base
```

### Bước 2: Cập nhật PROJECT_ROOT trong .env
```bash
# Chỉnh sửa file .env
nano .env

# Thay đổi dòng đầu tiên:
PROJECT_ROOT=/path/to/new/location
```

### Bước 3: Cài đặt dependencies
```bash
# Tạo virtual environment
python3 -m venv venv
source venv/bin/activate

# Cài đặt packages
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

### Bước 4: Deploy service
```bash
# Chạy script tự động deploy
./deploy-service.sh
```

**Xong!** Ứng dụng sẽ tự động:
- Tạo thư mục logs nếu chưa có
- Generate service file với đường dẫn đúng
- Deploy và khởi động systemd service
- Enable auto-start cùng server

## 📝 Ví dụ các môi trường khác nhau

### Production Server:
```bash
# .env
PROJECT_ROOT=/var/www/chatbot.company.com
```

### Development Server:
```bash
# .env  
PROJECT_ROOT=/home/developer/projects/chatbot
```

### Staging Server:
```bash
# .env
PROJECT_ROOT=/opt/staging/chatbot-staging
```

### Docker Container:
```bash
# .env
PROJECT_ROOT=/app
```

## 🛠️ Scripts Tự động

Tất cả scripts đã được cập nhật để tự động đọc `PROJECT_ROOT` từ `.env`:

### deploy-service.sh
- Đọc PROJECT_ROOT từ .env
- Generate service file từ template
- Deploy và khởi động service tự động

### start.sh  
- Tự động đọc PROJECT_ROOT
- Sử dụng đường dẫn động cho logs và PID file

### service.sh
- Quản lý systemd service 
- Hoạt động với bất kỳ PROJECT_ROOT nào

### gunicorn.conf.py
- Tự động load PROJECT_ROOT từ .env
- Cấu hình logs và PID file động

## ✅ Lợi ích

1. **🚀 Deploy nhanh chóng**: Chỉ cần thay đổi 1 dòng trong .env
2. **🔧 Không cần sửa code**: Tất cả scripts tự động adapt
3. **⚙️ Systemd service tự động**: Deploy service với đường dẫn đúng
4. **📁 Tự động tạo thư mục**: Logs directory được tạo tự động
5. **🔄 Easy migration**: Di chuyển project dễ dàng

## 🚨 Lưu ý quan trọng

1. **Quyền truy cập**: Đảm bảo user có quyền ghi vào PROJECT_ROOT
2. **Port conflicts**: Kiểm tra port 8200 không bị chiếm
3. **Dependencies**: Virtual environment phải được tạo ở mỗi môi trường
4. **Environment variables**: Copy .env và cập nhật PROJECT_ROOT
5. **Service names**: Có thể cần thay đổi tên service nếu deploy nhiều instance

## 📋 Checklist triển khai

- [ ] Clone/copy project code
- [ ] Cập nhật PROJECT_ROOT trong .env
- [ ] Tạo virtual environment
- [ ] Cài đặt dependencies  
- [ ] Chạy ./deploy-service.sh
- [ ] Kiểm tra service status
- [ ] Test HTTP response

## 🎯 Kết quả

Sau khi hoàn thành, bạn sẽ có:
- ✅ Service chạy ổn định
- ✅ Auto-start cùng server  
- ✅ Logs được ghi đúng nơi
- ✅ Dễ dàng quản lý với ./service.sh