# 🤖 Chatbot WhoIsMe - Quick Setup

## 🚀 Quick Deploy to New Environment

1. **Clone project:**
   ```bash
   git clone <repo> /your/desired/path/chatbot_base
   cd /your/desired/path/chatbot_base
   ```

2. **Update PROJECT_ROOT in .env:**
   ```bash
   nano .env
   # Change first line to:
   PROJECT_ROOT=/your/desired/path
   ```

3. **Setup Python environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install gunicorn
   ```

4. **Deploy service:**
   ```bash
   ./deploy-service.sh
   ```

5. **Verify:**
   ```bash
   ./service.sh status
   curl -I http://127.0.0.1:8200/
   ```

## 📋 Management Commands

```bash
./service.sh start      # Start service
./service.sh stop       # Stop service  
./service.sh restart    # Restart service
./service.sh status     # Check status
./service.sh logs       # View logs
```

## 📚 Full Documentation

- **[Setup Complete](setup_complete.md)** - Complete installation guide
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)** - Multi-environment deployment

## 🌐 Access Points

- **Main App:** http://127.0.0.1:8200
- **Login:** http://127.0.0.1:8200/login-ui
- **Register:** http://127.0.0.1:8200/register-ui

---
✅ **Ready for Production!** Auto-start enabled, systemd managed, full logging.