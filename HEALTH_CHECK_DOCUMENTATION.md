# 🏥 Health Check System Documentation

Hệ thống health check bao gồm 3 components chính:

## 📁 Files đã tạo:

### 1. `.github/workflows/health-check.yml`
- **Mô tả**: Workflow chính cho health check chi tiết
- **Chạy**: Mỗi 30 phút hoặc trigger thủ công
- **Features**: 
  - SSH vào server
  - Kiểm tra systemd service
  - Kiểm tra port 8200
  - Test HTTP endpoints
  - Chạy health check script

### 2. `.github/workflows/simple-health-check.yml`
- **Mô tả**: Workflow đơn giản, ít phụ thuộc
- **Chạy**: Mỗi 1 giờ hoặc trigger thủ công
- **Features**:
  - Ping server
  - Basic service checks
  - Resource monitoring

### 3. `health_check.py`
- **Mô tả**: Python script cho health check chi tiết
- **Chạy**: Từ server hoặc từ GitHub Actions
- **Features**:
  - 7 loại kiểm tra khác nhau
  - Detailed logging
  - Exit codes cho automation

## 🚀 Cách sử dụng:

### Chạy health check thủ công:

#### 1. Từ GitHub Actions:
```
1. Vào repository trên GitHub
2. Click "Actions" tab
3. Chọn "Health Check" hoặc "Simple Health Check"
4. Click "Run workflow"
```

#### 2. Từ server:
```bash
# SSH vào server
ssh username@your-server

# Chạy Python script
cd /path/to/project/chatbot_base
source venv/bin/activate
python health_check.py

# Hoặc chạy system checks
systemctl status chatbot-whoisme.service
netstat -tuln | grep 8200
curl http://localhost:8200/health
```

## 📊 Các loại kiểm tra:

### Health Check Workflow:
1. **Service Status** - Systemd service active
2. **Port Check** - Port 8200 listening  
3. **HTTP Response** - Endpoints responding
4. **Detailed Script** - Chạy health_check.py

### Simple Health Check Workflow:
1. **Server Ping** - Connectivity check
2. **Service Status** - Basic service check
3. **Process Check** - Gunicorn running
4. **Resource Check** - Disk & memory

### Python Health Script:
1. **Service Status** - Systemd service
2. **Process Running** - Gunicorn process
3. **Port Listening** - Port 8200
4. **HTTP Response** - Test endpoints
5. **Log Errors** - Recent error logs
6. **Disk Space** - Storage usage
7. **Memory Usage** - RAM usage

## ⚙️ Cấu hình Schedule:

### Health Check (Detailed):
```yaml
schedule:
  - cron: '*/30 * * * *'  # Mỗi 30 phút
```

### Simple Health Check:
```yaml
schedule:
  - cron: '0 * * * *'     # Mỗi 1 giờ
```

## 🔧 Troubleshooting:

### Workflow không chạy:
- Kiểm tra GitHub Secrets đã cấu hình đúng
- Xem logs trong Actions tab
- Đảm bảo SSH key có quyền truy cập

### Health check failed:
1. SSH vào server kiểm tra thủ công
2. Xem service status: `systemctl status chatbot-whoisme.service`
3. Xem logs: `journalctl -u chatbot-whoisme.service -f`
4. Restart service: `sudo systemctl restart chatbot-whoisme.service`

### Script báo lỗi:
- Kiểm tra Python environment
- Đảm bảo có quyền chạy system commands
- Install missing dependencies

## 📈 Monitoring Strategy:

### Tự động:
- GitHub Actions sẽ email khi workflow failed
- Health checks chạy định kỳ
- Logs được lưu trong Actions history

### Thủ công:
- Check GitHub Actions tab thường xuyên
- SSH vào server kiểm tra khi cần
- Monitor server resources

## 🎯 Best Practices:

1. **Regular Monitoring**: Kiểm tra Actions tab hàng ngày
2. **Quick Response**: Investigate failed checks ngay lập tức  
3. **Resource Monitoring**: Theo dõi disk và memory usage
4. **Log Analysis**: Xem logs khi có warning
5. **Backup Strategy**: Đảm bảo có backup trước khi fix issues

## 📞 Emergency Response:

### Khi service down:
```bash
# 1. SSH vào server
ssh username@your-server

# 2. Kiểm tra service
sudo systemctl status chatbot-whoisme.service

# 3. Restart service
sudo systemctl restart chatbot-whoisme.service

# 4. Kiểm tra logs
sudo journalctl -u chatbot-whoisme.service -f

# 5. Test endpoints
curl http://localhost:8200/health
```

### Khi resource cao:
```bash
# Kiểm tra processes
top -n 1
ps aux | grep gunicorn

# Kiểm tra disk
df -h
du -sh /path/to/logs/*

# Restart nếu cần
sudo systemctl restart chatbot-whoisme.service
```