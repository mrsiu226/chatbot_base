#!/bin/bash

# Script to generate and deploy systemd service with dynamic PROJECT_ROOT
# Usage: ./deploy-service.sh

set -e

# Load PROJECT_ROOT from .env safely
if [ -f ".env" ]; then
    PROJECT_ROOT=$(grep "^PROJECT_ROOT=" .env | cut -d '=' -f2 | tr -d '"')
fi

# Use PROJECT_ROOT from env or detect current path
if [ -z "$PROJECT_ROOT" ]; then
    PROJECT_ROOT=$(cd .. && pwd)
    echo "⚠️  PROJECT_ROOT not set in .env, using detected path: $PROJECT_ROOT"
else
    echo "✅ Using PROJECT_ROOT from .env: $PROJECT_ROOT"
fi

# Validate paths exist
if [ ! -d "$PROJECT_ROOT/chatbot_base" ]; then
    echo "❌ Error: $PROJECT_ROOT/chatbot_base does not exist!"
    exit 1
fi

if [ ! -d "$PROJECT_ROOT/logs" ]; then
    echo "📁 Creating logs directory: $PROJECT_ROOT/logs"
    mkdir -p "$PROJECT_ROOT/logs"
fi

# Generate service file from template
echo "🔧 Generating service file..."
sed "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" chatbot-whoisme.service.template > chatbot-whoisme.service

# Deploy service
echo "🚀 Deploying service to systemd..."
sudo cp chatbot-whoisme.service /etc/systemd/system/
sudo systemctl daemon-reload

# Check if service was running and stop it
if sudo systemctl is-active --quiet chatbot-whoisme.service; then
    echo "⏹️  Stopping existing service..."
    sudo systemctl stop chatbot-whoisme.service
fi

# Enable and start service
echo "✅ Enabling and starting service..."
sudo systemctl enable chatbot-whoisme.service
sudo systemctl start chatbot-whoisme.service

# Wait a moment and check status
sleep 3
echo "📊 Service status:"
sudo systemctl status chatbot-whoisme.service --no-pager -l

echo ""
echo "🎉 Service deployment completed!"
echo "📋 Useful commands:"
echo "   ./service.sh status    - Check service status"
echo "   ./service.sh logs      - View live logs"
echo "   ./service.sh restart   - Restart service"