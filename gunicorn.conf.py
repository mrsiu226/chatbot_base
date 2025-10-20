# Gunicorn configuration file
import multiprocessing

# Server socket
bind = "127.0.0.1:8200"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 300
keepalive = 2

# Restart workers after this many requests
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "/home/chatbotD8ZL/chatbot.toila.ai.vn/logs/gunicorn_access.log"
errorlog = "/home/chatbotD8ZL/chatbot.toila.ai.vn/logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "chatbot_toila"

# Server mechanics
daemon = False
pidfile = "/home/chatbotD8ZL/chatbot.toila.ai.vn/logs/gunicorn.pid"
tmp_upload_dir = "/tmp"

# SSL (if needed later)
# keyfile = "/path/to/private.key"
# certfile = "/path/to/certificate.crt"

# Environment variables
raw_env = [
    'PYTHONPATH=/home/chatbotD8ZL/chatbot.toila.ai.vn/chatbot_base'
]