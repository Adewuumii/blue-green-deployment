# Blue/Green Deployment with Nginx

This is a production-ready Blue/Green deployment implementation with automatic failover and real-time monitoring.
---

## Overview

This project implements a complete Blue/Green deployment strategy featuring:

- **Zero-downtime deployments** with automatic failover
- **Health-based routing** via Nginx load balancer
- **Real-time monitoring** with Python log watcher
- **Slack alerting** for operational visibility
- **Docker Compose orchestration** for easy deployment

**Architecture:**
- Two identical application pools (Blue and Green)
- Nginx routes traffic to primary pool (Blue by default)
- Automatic failover to backup pool on primary failure
- Log monitoring detects issues and sends Slack alerts

---

## Prerequisites

- **Docker** 
- **Docker Compose** 
- **Linux/WSL environment** (for testing)
- **Slack workspace** (for alerts)

---

## Quick Start
```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/blue-green-deployment.git
cd blue-green-deployment

# Configure environment
cp .env.example .env
nano .env  # Add your configuration

# Start all services
docker-compose up -d

# Verify deployment
curl http://localhost:8080/version
```

---

## Part 1: Blue/Green Deployment with Failover

### Features

**Automatic Failover** - Primary fails → Traffic routes to backup instantly  
**Zero Downtime** - Failures handled within the same request  
**Fast Detection** - Tight timeouts (2-5 seconds) for quick failover  
**Health-Based Routing** - Nginx monitors upstream health automatically  
**Header Forwarding** - Pool and release information in response headers  


### Setup

#### 1. Configure Environment Variables
```bash
cp .env.example .env
nano .env
```

**Required variables:**
```bash
# Docker Images
BLUE_IMAGE=your-dockerhub-user/your-app:tag
GREEN_IMAGE=your-dockerhub-user/your-app:tag

# Active Pool
ACTIVE_POOL=blue

# Release IDs
RELEASE_ID_BLUE=blue-v1.0.0
RELEASE_ID_GREEN=green-v1.0.0

# Application Port
PORT=3000
```

#### 2. Start Services
```bash
docker-compose up -d
```

**Containers started:**
- `nginx_lb` - Nginx load balancer (port 8080)
- `app_blue` - Blue application (port 8081)
- `app_green` - Green application (port 8082)

#### 3. Verify Deployment
```bash
# Check container status
docker-compose ps

# Test main endpoint
curl -i http://localhost:8080/version

# Should show:
# HTTP/1.1 200 OK
# X-App-Pool: blue
# X-Release-Id: blue-v1.0.0
```

### Testing Failover

#### Test 1: Baseline 
```bash
# Send 5 requests to verify Blue is active
for i in {1..5}; do 
  curl -s -i http://localhost:8080/version | grep -E "X-App-Pool|X-Release-Id"
done
```

**Expected output:**
```
X-App-Pool: blue
X-Release-Id: blue-v1.0.0
```

#### Test 2: Trigger Failover
```bash
# Step 1: Simulate failure on Blue
curl -X POST "http://localhost:8081/chaos/start?mode=error"

# Step 2: Make requests - should failover to Green
for i in {1..10}; do 
  echo "Request $i:"
  curl -s -i http://localhost:8080/version | grep -E "X-App-Pool|HTTP/1.1"
  echo ""
done
```

**Expected results:**
- All requests return `HTTP/1.1 200 OK` 
- All requests show `X-App-Pool: green` 
- Failover happens within 2-5 seconds

#### Test 3: Verify Recovery
```bash
# Stop chaos on Blue
curl -X POST "http://localhost:8081/chaos/stop"

# Wait for Blue to recover 
sleep 10

# Make requests - should return to Blue
for i in {1..5}; do 
  curl -s -i http://localhost:8080/version | grep X-App-Pool
done
```

**Expected output:**
```
X-App-Pool: blue
```

Traffic automatically returns to primary pool

### Available Endpoints

#### Through Nginx (Port 8080)
- `GET /version` - Application version with headers
- `GET /healthz` - Health check endpoint
- `GET /nginx-health` - Nginx health status

#### Direct Access to Blue (Port 8081)
- `GET /version` - Direct Blue access
- `POST /chaos/start?mode=error` - Trigger chaos (simulate failures)
- `POST /chaos/stop` - Stop chaos

#### Direct Access to Green (Port 8082)
- `GET /version` - Direct Green access
- `POST /chaos/start?mode=error` - Trigger chaos
- `POST /chaos/stop` - Stop chaos

### Stopping Services
```bash
# Stop all containers
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

---

## Part 2: Observability & Alerts

### Features

**JSON-formatted Nginx logs** - Structured logging with pool, release, status  
**Real-time log monitoring** - Python watcher tails logs continuously  
**Failover detection** - Alerts when pool changes (blue ↔ green)  
**Error rate monitoring** - Alerts when 5xx errors exceed threshold  
**Alert cooldown** - Prevents spam (5-minute default)  
**Operational runbook** - Guide for responding to alerts  

### Setup

#### Step 1: Get Slack Webhook URL

1. Go to https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. Name: `Blue-Green Alerts`
4. Choose your workspace
5. In left sidebar: **"Incoming Webhooks"** → Toggle **ON**
6. Click **"Add New Webhook to Workspace"**
7. Select a channel (create `#blue-green-alerts` or use existing)
8. Click **"Allow"**
9. **Copy the webhook URL** (looks like: `https://hooks.slack.com/services/T.../B.../...`)

#### Step 2: Configure Environment

Edit `.env` and add these variables:
```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
ERROR_RATE_THRESHOLD=2
WINDOW_SIZE=200
ALERT_COOLDOWN_SEC=60
```

#### Step 3: Start All Services
```bash
docker-compose up -d
```

**Containers started (4 total):**
- `nginx_lb` - Nginx load balancer
- `app_blue` - Blue application
- `app_green` - Green application  
- `alert_watcher` - Python monitoring service

#### Step 4: Verify Watcher is Running
```bash
# Check watcher status
docker-compose ps alert_watcher

# View watcher logs
docker-compose logs alert_watcher

# Should show:
# Log file found!
# Starting log watcher...
# Initial pool detected: blue
```

### Testing Alerts

#### Alert Test 1: Failover Detection

**Trigger a failover event:**
```bash
# 1. Trigger chaos on Blue
curl -X POST "http://localhost:8081/chaos/start?mode=error"

# 2. Generate traffic to trigger failover
for i in {1..20}; do 
  curl -s http://localhost:8080/version > /dev/null
  sleep 0.2
done

# 3. Check your Slack channel for alert
```


**Stop chaos:**
```bash
curl -X POST "http://localhost:8081/chaos/stop"
```

#### Alert Test 2: High Error Rate

**Trigger an error rate alert:**
```bash
# 1. Trigger chaos on BOTH pools (errors can't be recovered)
curl -X POST "http://localhost:8081/chaos/start?mode=error"
curl -X POST "http://localhost:8082/chaos/start?mode=error"

# 2. Generate lots of traffic to build error rate
for i in {1..250}; do 
  curl -s http://localhost:8080/version > /dev/null
  sleep 0.05
done

# 3. Check your Slack channel for alert
```

**Stop chaos:**
```bash
curl -X POST "http://localhost:8081/chaos/stop"
curl -X POST "http://localhost:8082/chaos/stop"
```

### Monitoring

#### View Real-Time Watcher Logs
```bash
docker-compose logs -f alert_watcher
```

#### View Nginx JSON Logs
```bash
docker-compose exec nginx tail -f /var/log/nginx/access.log
```

### Runbook

For operational guidance on responding to alerts, see **[runbook.md](runbook.md)**

### Verification Screenshots
1. **Failover Alert** - Slack message showing pool change detected (blue → green or green → blue)
2. **Error Rate Alert** - Slack message showing error rate threshold exceeded
3. **Nginx JSON Logs** - Terminal output showing structured log format with pool/release data

---

## Project Structure
```
.
├── screenshot
├── docker-compose.yml          
├── nginx.conf.template         
├── watcher.py                   
├── requirements.txt            
├── runbook.md                  
├── .env                        
├── .env.example                
├── .gitignore                  
└── README.md                   
```