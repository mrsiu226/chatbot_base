# Gunicorn configuration file
import multiprocessing
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
PROJECT_ROOT = os.getenv('PROJECT_ROOT', '/home/chatbotySia/chatbot.whoisme.ai')

# Server socket
bind = "127.0.0.1:8200"
backlog = 2048

# Worker processes
workers = 4  # Giảm workers để tiết kiệm memory
worker_class = "sync"
worker_connections = 1000
timeout = 120  # Tăng timeout lên 120s cho AI API calls
keepalive = 2

# Restart workers after this many requests
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = f"{PROJECT_ROOT}/logs/gunicorn_access.log"
errorlog = f"{PROJECT_ROOT}/logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "chatbot_whoisme"

# Server mechanics
daemon = False
pidfile = f"{PROJECT_ROOT}/logs/gunicorn.pid"
tmp_upload_dir = "/tmp"

# SSL (if needed later)
# keyfile = "/path/to/private.key"
# certfile = "/path/to/certificate.crt"

# Environment variables
raw_env = [
    f'PYTHONPATH={PROJECT_ROOT}/chatbot_base',
    f'PROJECT_ROOT={PROJECT_ROOT}'
]