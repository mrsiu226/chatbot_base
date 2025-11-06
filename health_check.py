#!/usr/bin/env python3
"""
Health Check Script for Chatbot Service
Kiểm tra sức khỏe của chatbot service và các thành phần quan trọng
"""

import requests
import sys
import time
import subprocess
import os
import json
from datetime import datetime
from pathlib import Path

def check_service_status():
    """Kiểm tra trạng thái systemd service"""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'chatbot-whoisme.service'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip() == 'active'
    except Exception as e:
        print(f"❌ Error checking service status: {e}")
        return False

def check_port_listening():
    """Kiểm tra port 8200 có đang listen không"""
    try:
        # Thử ss command trước (modern)
        result = subprocess.run(
            ['ss', '-tuln'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if ':8200 ' in result.stdout:
            return True
            
        # Fallback to netstat
        result = subprocess.run(
            ['netstat', '-tuln'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return ':8200 ' in result.stdout
    except Exception as e:
        print(f"❌ Error checking port: {e}")
        return False

def check_http_response():
    """Kiểm tra HTTP response của service"""
    endpoints = [
        'http://localhost:8200/health',
        'http://localhost:8200/',
        'http://127.0.0.1:8200/health',
        'http://127.0.0.1:8200/'
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, timeout=5)
            if response.status_code in [200, 404]:  # 404 cũng OK vì service đang chạy
                return True, endpoint
        except requests.exceptions.RequestException:
            continue
    
    return False, None

def check_process_running():
    """Kiểm tra gunicorn process có đang chạy không"""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'gunicorn.*ai_bot'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return len(result.stdout.strip()) > 0
    except Exception as e:
        print(f"❌ Error checking process: {e}")
        return False

def check_log_errors():
    """Kiểm tra logs có lỗi nghiêm trọng không"""
    try:
        result = subprocess.run(
            ['journalctl', '-u', 'chatbot-whoisme.service', '--since', '10 minutes ago', '--no-pager'],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        error_keywords = ['ERROR', 'CRITICAL', 'FATAL', 'Exception', 'Traceback']
        log_content = result.stdout.lower()
        
        recent_errors = []
        for keyword in error_keywords:
            if keyword.lower() in log_content:
                recent_errors.append(keyword)
        
        return len(recent_errors) == 0, recent_errors
    except Exception as e:
        print(f"❌ Error checking logs: {e}")
        return True, []  # Không fail health check vì lỗi check logs

def check_disk_space():
    """Kiểm tra dung lượng đĩa"""
    try:
        project_root = os.getenv('PROJECT_ROOT', '/var/www/chatbot')
        target_dir = project_root if os.path.exists(project_root) else '/'
        
        result = subprocess.run(
            ['df', '-h', target_dir],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            usage_line = lines[1].split()
            if len(usage_line) >= 5:
                usage_percent = usage_line[4].replace('%', '')
                try:
                    return int(usage_percent) < 90, usage_percent  # Cảnh báo nếu > 90%
                except ValueError:
                    return True, "unknown"
        
        return True, "unknown"
    except Exception as e:
        print(f"❌ Error checking disk space: {e}")
        return True, "error"

def check_memory_usage():
    """Kiểm tra memory usage"""
    try:
        result = subprocess.run(
            ['free', '-m'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            mem_line = lines[1].split()
            if len(mem_line) >= 3:
                total = int(mem_line[1])
                used = int(mem_line[2])
                usage_percent = (used / total) * 100
                return usage_percent < 90, f"{usage_percent:.1f}%"
        
        return True, "unknown"
    except Exception as e:
        print(f"❌ Error checking memory: {e}")
        return True, "error"

def main():
    """Main health check function"""
    print("🏥 Starting chatbot health check...")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    checks = []
    
    # 1. Service Status
    print("1️⃣ Checking service status...")
    service_ok = check_service_status()
    checks.append(('Service Status', service_ok))
    print(f"   {'✅' if service_ok else '❌'} Service status: {'Running' if service_ok else 'Not running'}")
    
    # 2. Process Running
    print("\n2️⃣ Checking process...")
    process_ok = check_process_running()
    checks.append(('Process Running', process_ok))
    print(f"   {'✅' if process_ok else '❌'} Gunicorn process: {'Running' if process_ok else 'Not found'}")
    
    # 3. Port Listening
    print("\n3️⃣ Checking port 8200...")
    port_ok = check_port_listening()
    checks.append(('Port 8200', port_ok))
    print(f"   {'✅' if port_ok else '❌'} Port 8200: {'Listening' if port_ok else 'Not accessible'}")
    
    # 4. HTTP Response
    print("\n4️⃣ Checking HTTP response...")
    http_ok, endpoint = check_http_response()
    checks.append(('HTTP Response', http_ok))
    if http_ok:
        print(f"   ✅ HTTP response: OK ({endpoint})")
    else:
        print("   ❌ HTTP response: Failed")
    
    # 5. Log Errors
    print("\n5️⃣ Checking recent logs...")
    logs_ok, errors = check_log_errors()
    checks.append(('Recent Errors', logs_ok))
    if logs_ok:
        print("   ✅ No recent errors in logs")
    else:
        print(f"   ❌ Found recent errors: {', '.join(errors)}")
    
    # 6. Disk Space
    print("\n6️⃣ Checking disk space...")
    disk_ok, disk_usage = check_disk_space()
    checks.append(('Disk Space', disk_ok))
    print(f"   {'✅' if disk_ok else '⚠️'} Disk space: {disk_usage} {'(OK)' if disk_ok else '(HIGH)'}")
    
    # 7. Memory Usage
    print("\n7️⃣ Checking memory usage...")
    mem_ok, mem_usage = check_memory_usage()
    checks.append(('Memory Usage', mem_ok))
    print(f"   {'✅' if mem_ok else '⚠️'} Memory usage: {mem_usage} {'(OK)' if mem_ok else '(HIGH)'}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 HEALTH CHECK SUMMARY:")
    
    failed_checks = []
    warning_checks = []
    
    for check_name, status in checks:
        if check_name in ['Disk Space', 'Memory Usage'] and not status:
            status_icon = "⚠️"
            warning_checks.append(check_name)
        else:
            status_icon = "✅" if status else "❌"
            if not status:
                failed_checks.append(check_name)
        
        print(f"   {status_icon} {check_name}")
    
    # Final result
    if not failed_checks and not warning_checks:
        print("\n🎉 All health checks passed!")
        return 0
    elif not failed_checks:
        print(f"\n⚠️ {len(warning_checks)} warning(s): {', '.join(warning_checks)}")
        return 0  # Warnings don't fail the health check
    else:
        print(f"\n❌ {len(failed_checks)} critical check(s) failed: {', '.join(failed_checks)}")
        if warning_checks:
            print(f"⚠️ {len(warning_checks)} warning(s): {', '.join(warning_checks)}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)