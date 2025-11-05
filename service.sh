#!/bin/bash

# Chatbot WhoIsMe Service Management Script
# Usage: ./service.sh [start|stop|restart|status|enable|disable|logs]

SERVICE_NAME="chatbot-whoisme.service"

case "$1" in
    start)
        echo "🚀 Starting chatbot service..."
        sudo systemctl start $SERVICE_NAME
        sleep 2
        sudo systemctl status $SERVICE_NAME --no-pager -l
        ;;
    stop)
        echo "⏹️  Stopping chatbot service..."
        sudo systemctl stop $SERVICE_NAME
        echo "Service stopped."
        ;;
    restart)
        echo "🔄 Restarting chatbot service..."
        sudo systemctl restart $SERVICE_NAME
        sleep 2
        sudo systemctl status $SERVICE_NAME --no-pager -l
        ;;
    status)
        echo "📊 Checking service status..."
        sudo systemctl status $SERVICE_NAME --no-pager -l
        echo ""
        echo "📡 Port status:"
        netstat -tlnp | grep 8200
        ;;
    enable)
        echo "✅ Enabling service to start on boot..."
        sudo systemctl enable $SERVICE_NAME
        echo "Service enabled."
        ;;
    disable)
        echo "❌ Disabling service from starting on boot..."
        sudo systemctl disable $SERVICE_NAME
        echo "Service disabled."
        ;;
    logs)
        echo "📋 Showing service logs (Press Ctrl+C to exit)..."
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|enable|disable|logs}"
        echo ""
        echo "Commands:"
        echo "  start    - Start the chatbot service"
        echo "  stop     - Stop the chatbot service"
        echo "  restart  - Restart the chatbot service"
        echo "  status   - Show service status and port info"
        echo "  enable   - Enable service to start on boot"
        echo "  disable  - Disable service from starting on boot"
        echo "  logs     - Show live service logs"
        exit 1
        ;;
esac