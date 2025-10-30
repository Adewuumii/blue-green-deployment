#!/usr/bin/env python3

import json
import time
import os
import sys
from collections import deque
from datetime import datetime
import requests
import subprocess

# Configuration from environment variables
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '')
ERROR_RATE_THRESHOLD = float(os.getenv('ERROR_RATE_THRESHOLD', '2.0'))  
WINDOW_SIZE = int(os.getenv('WINDOW_SIZE', '200'))  
ALERT_COOLDOWN_SEC = int(os.getenv('ALERT_COOLDOWN_SEC', '300'))  
LOG_FILE = '/var/log/nginx/access.log'

# State tracking
last_pool = None
request_window = deque(maxlen=WINDOW_SIZE)
last_failover_alert = 0
last_error_rate_alert = 0

def send_slack_alert(message, alert_type="info"):
    """Send alert to Slack"""
    if not SLACK_WEBHOOK_URL:
        print(f"⚠️  No Slack webhook configured. Alert: {message}")
        return
    
    # Color coding based on alert type
    color = {
        "danger": "#ff0000",   # Red for errors/failover
        "warning": "#ff9900",  # Orange for warnings
        "good": "#00ff00",     # Green for recovery
        "info": "#0099ff"      # Blue for info
    }.get(alert_type, "#808080")
    
    payload = {
        "attachments": [{
            "color": color,
            "title": f"Blue/Green Deployment Alert",
            "text": message,
            "footer": "Nginx Log Watcher",
            "ts": int(time.time())
        }]
    }
    
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"Slack alert sent: {message}")
        else:
            print(f"Failed to send Slack alert: {response.status_code}")
    except Exception as e:
        print(f"Error sending Slack alert: {e}")

def calculate_error_rate():
    """Calculate 5xx error rate over the request window"""
    if len(request_window) == 0:
        return 0.0
    
    error_count = sum(1 for status in request_window if status >= 500)
    return (error_count / len(request_window)) * 100

def check_failover(pool):
    """Check if pool has changed (failover detected)"""
    global last_pool, last_failover_alert
    
    if last_pool is None:
        last_pool = pool
        print(f"ℹInitial pool detected: {pool}")
        return
    
    if pool != last_pool:

        current_time = time.time()
        
        # Check cooldown
        if current_time - last_failover_alert < ALERT_COOLDOWN_SEC:
            print(f"Failover detected ({last_pool} → {pool}) but in cooldown period")
            return
        
        message = f"**Failover Detected!**\n" \
                  f"Pool changed: `{last_pool}` → `{pool}`\n" \
                  f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
                  f"Action: Check health of `{last_pool}` container"
        
        send_slack_alert(message, alert_type="danger")
        last_failover_alert = current_time
        last_pool = pool
        print(f"Failover: {last_pool} → {pool}")

def check_error_rate():
    """Check if error rate exceeds threshold"""
    global last_error_rate_alert
    
    if len(request_window) < WINDOW_SIZE:
        
        return
    
    error_rate = calculate_error_rate()
    
    if error_rate > ERROR_RATE_THRESHOLD:
        current_time = time.time()
        
        # Check cooldown
        if current_time - last_error_rate_alert < ALERT_COOLDOWN_SEC:
            print(f"High error rate ({error_rate:.2f}%) but in cooldown period")
            return
        
        message = f" **High Error Rate Detected!**\n" \
                  f"Error rate: `{error_rate:.2f}%` (threshold: {ERROR_RATE_THRESHOLD}%)\n" \
                  f"Window size: {WINDOW_SIZE} requests\n" \
                  f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
                  f"Action: Investigate upstream services"
        
        send_slack_alert(message, alert_type="warning")
        last_error_rate_alert = current_time
        print(f"  High error rate: {error_rate:.2f}%")

def tail_log_file():
    """Tail the Nginx log file and process each line"""
    print(f" Starting log watcher...")
    print(f" Configuration:")
    print(f"   - Log file: {LOG_FILE}")
    print(f"   - Error rate threshold: {ERROR_RATE_THRESHOLD}%")
    print(f"   - Window size: {WINDOW_SIZE} requests")
    print(f"   - Alert cooldown: {ALERT_COOLDOWN_SEC}s")
    print(f"   - Slack webhook: {'configured' if SLACK_WEBHOOK_URL else 'NOT configured'}")
    print()
    
    # Use tail -f to follow the log file
    process = subprocess.Popen(
        ['tail', '-f', '-n', '0', LOG_FILE],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            
            try:
                # Parse JSON log line
                log_entry = json.loads(line)
                
                # Extract relevant fields
                status = int(log_entry.get('status', 0))
                pool = log_entry.get('pool', 'unknown')
                release = log_entry.get('release', 'unknown')
                upstream_status = log_entry.get('upstream_status', '')
                
                # Add status to rolling window
                request_window.append(status)
                
                # Check for failover
                if pool != 'unknown':
                    check_failover(pool)
                
                # Check error rate
                check_error_rate()
                
                # Log summary
                error_rate = calculate_error_rate()
                print(f" [{pool}] Status: {status} | Error Rate: {error_rate:.2f}% | Window: {len(request_window)}/{WINDOW_SIZE}")
                
            except json.JSONDecodeError:
                print(f"  Failed to parse log line: {line}")
            except Exception as e:
                print(f" Error processing log line: {e}")
    
    except KeyboardInterrupt:
        print("\n Stopping log watcher...")
        process.terminate()
        sys.exit(0)

if __name__ == '__main__':
    # Wait a bit for nginx to start and create log file
    print(" Waiting for log file to be created...")
    for i in range(30):
        if os.path.exists(LOG_FILE):
            print(f" Log file found!")
            break
        time.sleep(1)
    else:
        print(f" Log file not found: {LOG_FILE}")
        sys.exit(1)
    
    # Start tailing
    tail_log_file()