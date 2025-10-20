#!/bin/bash

# Chatbot application startup script
# Usage: ./start.sh [start|stop|restart|status]

APPDIR="/home/chatbotD8ZL/chatbot.toila.ai.vn/chatbot_base"
PIDFILE="/home/chatbotD8ZL/chatbot.toila.ai.vn/logs/gunicorn.pid"
LOGDIR="/home/chatbotD8ZL/chatbot.toila.ai.vn/logs"
USER="root"

cd $APPDIR

start() {
    echo "Starting chatbot application..."
    
    # Create log directory if not exists
    mkdir -p $LOGDIR
    
    # Check if already running
    if [ -f $PIDFILE ]; then
        PID=$(cat $PIDFILE)
        if kill -0 $PID 2>/dev/null; then
            echo "Application is already running (PID: $PID)"
            return 1
        else
            echo "Removing stale PID file"
            rm -f $PIDFILE
        fi
    fi
    
    # Start the application
    gunicorn --config gunicorn.conf.py ai_bot:app &
    
    echo "Application started successfully"
    sleep 2
    status
}

stop() {
    echo "Stopping chatbot application..."
    
    if [ -f $PIDFILE ]; then
        PID=$(cat $PIDFILE)
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            echo "Application stopped (PID: $PID)"
            rm -f $PIDFILE
        else
            echo "Application is not running"
            rm -f $PIDFILE
        fi
    else
        echo "PID file not found. Application may not be running."
        # Try to kill by process name
        pkill -f "gunicorn.*ai_bot:app"
    fi
}

restart() {
    stop
    sleep 3
    start
}

status() {
    if [ -f $PIDFILE ]; then
        PID=$(cat $PIDFILE)
        if kill -0 $PID 2>/dev/null; then
            echo "Application is running (PID: $PID)"
            echo "Listening on: http://127.0.0.1:8200"
            return 0
        else
            echo "Application is not running (stale PID file)"
            return 1
        fi
    else
        echo "Application is not running"
        return 1
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac