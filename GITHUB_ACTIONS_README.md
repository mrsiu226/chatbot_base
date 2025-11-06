# 🚀 GitHub Actions Auto Deploy

Dự án này đã được cấu hình GitHub Actions để tự động deploy lên server khi có commit mới vào branch `main`.

## 📁 Files quan trọng

- `.github/workflows/deploy.yml` - Workflow chính cho auto deploy
- `.github/workflows/health-check.yml` - Health check định kỳ
- `health_check.py` - Script kiểm tra sức khỏe service
- `chatbot-whoisme.service.template` - Template cho systemd service
- `GITHUB_SECRETS_SETUP.md` - Hướng dẫn cấu hình secrets

## ⚙️ Cách sử dụng

### 1. Cấu hình Secrets
Làm theo hướng dẫn trong `GITHUB_SECRETS_SETUP.md` để thêm các secrets cần thiết:
- `SERVER_HOST`
- `SERVER_USERNAME` 
- `SERVER_SSH_KEY`
- `PROJECT_ROOT`
- `SERVER_PORT` (optional)

### 2. Auto Deploy
- Push code lên branch `main` → Tự động deploy
- Hoặc trigger thủ công từ Actions tab

### 3. Monitor
- Health check chạy mỗi 30 phút
- Kiểm tra logs trong Actions tab
- Chạy health check thủ công: `python health_check.py`

## 🔍 Quy trình Deploy

1. **Backup** code hiện tại
2. **Pull** code mới từ GitHub
3. **Install** dependencies
4. **Update** cấu hình
5. **Deploy** systemd service
6. **Restart** service
7. **Health check** 
8. **Notify** kết quả

## 🛠️ Commands hữu ích

```bash
# Xem status workflow
gh workflow list

# Xem logs của workflow gần nhất
gh run list --limit 1
gh run view [run-id] --log

# Trigger deploy thủ công
gh workflow run deploy.yml

# SSH vào server kiểm tra
ssh username@server
sudo systemctl status chatbot-whoisme.service
./service.sh logs
```

## 🔧 Troubleshooting

### Deploy failed
1. Kiểm tra GitHub Secrets đã đúng chưa
2. Kiểm tra SSH key và quyền user trên server
3. Xem logs chi tiết trong Actions

### Service không start
1. SSH vào server: `sudo systemctl status chatbot-whoisme.service`
2. Xem logs: `sudo journalctl -u chatbot-whoisme.service`
3. Chạy health check: `python health_check.py`

### Port không accessible
1. Kiểm tra firewall: `sudo ufw status`
2. Kiểm tra process: `netstat -tlnp | grep 8200`
3. Restart service: `./service.sh restart`

## 📈 Monitoring

- **GitHub Actions**: Theo dõi deploy history
- **Health Check**: Tự động kiểm tra mỗi 30 phút  
- **Server Logs**: `./service.sh logs`
- **Health Script**: `python health_check.py`

## 🎯 Benefits

✅ **Zero downtime** deployment  
✅ **Automatic** backup before deploy  
✅ **Rollback** capability với backup  
✅ **Health monitoring** 24/7  
✅ **Notification** khi có vấn đề  
✅ **Easy** trigger manual deploy  