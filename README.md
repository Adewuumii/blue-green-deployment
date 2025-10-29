# Blue/Green Deployment with Nginx

This project implements a Blue/Green deployment strategy for a Node.js application using Nginx as a load balancer with automatic failover capabilities.

## Overview

- **Blue/Green Architecture**: Two identical Node.js services (Blue and Green) running behind Nginx
- **Automatic Failover**: When the primary service (Blue) fails, Nginx automatically routes traffic to the backup (Green)
- **Zero Downtime**: Failures are detected and handled within the same request - clients never see errors
- **Health-Based Routing**: Tight timeouts and retry policies ensure fast failure detection


## Prerequisites

- Docker
- Docker Compose
- Linux/WSL environment (for testing)

## Project Structure
```
├── docker-compose.yml          
 nginx, app_blue, app_green
├── nginx.conf.template         
 configuration with failover logic
├── .env                        
 variables 
├── .env.example                
   # Template for environment variables
└── README.md                   
```

## Setup Instructions

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd <repo-directory>
```

### 2. Configure Environment Variables

Copy the example environment file and update with your values:
```bash
cp .env.example .env
```

Edit `.env` and set your Docker image URLs and release IDs.

### 3. Start the Services
```bash
docker-compose up -d
```

This will start three containers:
- `nginx_lb` - Nginx load balancer (port 8080)
- `app_blue` - Blue application instance (port 8081)
- `app_green` - Green application instance (port 8082)

### 4. Verify the Deployment

Check that all containers are running:
```bash
docker-compose ps
```

Test the main endpoint:
```bash
curl -i http://localhost:8080/version
```

## Testing Failover

### 1. Baseline Test

Send multiple requests to verify Blue is handling traffic:
```bash
for i in {1..5}; do 
  curl -s -i http://localhost:8080/version | grep -E "X-App-Pool|X-Release-Id"
done
```

All responses should show `X-App-Pool: blue`.

### 2. Trigger Chaos on Blue

Simulate a failure on the Blue service:
```bash
curl -X POST "http://localhost:8081/chaos/start?mode=error"
```

### 3. Verify Automatic Failover

Send requests through Nginx. Which should now route to Green:
```bash
for i in {1..10}; do 
  echo "Request $i:"
  curl -s -i http://localhost:8080/version | grep -E "X-App-Pool|HTTP/1.1"
  echo ""
done
```

**Expected Results:**
- All requests return `200 OK` (zero failures)
- All requests show `X-App-Pool: green`
- Failover happens automatically within seconds

### 4. Stop Chaos and Verify Recovery

Stop the chaos simulation:
```bash
curl -X POST "http://localhost:8081/chaos/stop"
```

Wait 6 seconds for Blue to recover:
```bash
sleep 6
```

Test again - traffic should return to Blue:
```bash
curl -i http://localhost:8080/version | grep -E "X-App-Pool"
```