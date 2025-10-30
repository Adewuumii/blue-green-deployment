# Blue/Green Deployment Runbook

## Overview

This runbook provides operational guidance for responding to alerts from the Blue/Green deployment monitoring system.

---

## Alert Types

### 1. 🔄 Failover Detected

**Alert Message:**
```
🔄 Failover Detected!
Pool changed: blue → green (or green → blue)
Time: [timestamp]
Action: Check health of [failed pool] container
```

**What It Means:**
- The primary application pool has failed health checks
- Nginx automatically routed traffic to the backup pool
- Zero downtime was maintained for end users
- The system is currently running on backup infrastructure

**Immediate Actions:**

1. **Verify current pool status:**
```bash
   curl -i http://localhost:8080/version | grep X-App-Pool
```

2. **Check logs of the failed pool:**
```bash
   # If blue failed:
   docker-compose logs app_blue --tail=50
   
   # If green failed:
   docker-compose logs app_green --tail=50
```

3. **Check if chaos mode is active:**
```bash
   # Check Blue
   curl http://localhost:8081/chaos/status
   
   # Check Green
   curl http://localhost:8082/chaos/status
```

4. **Stop chaos if it's a test:**
```bash
   curl -X POST "http://localhost:8081/chaos/stop"
   curl -X POST "http://localhost:8082/chaos/stop"
```

5. **Monitor for recovery:**
   - Wait 6+ seconds for health checks
   - Traffic should automatically return to primary pool
   - Verify with: `curl -i http://localhost:8080/version`

**Non-Urgent Actions:**
- Review application logs for root cause
- Check resource usage (CPU, memory)
- Investigate external dependencies
- Document incident for postmortem

**Recovery Confirmation:**
When the alert shows pool changed back to the original (e.g., green → blue), the primary pool has recovered and normal operations resumed.

---

### 2. ⚠️ High Error Rate Detected

**Alert Message:**
```
⚠️ High Error Rate Detected!
Error rate: X% (threshold: 2%)
Window size: 200 requests
Time: [timestamp]
Action: Investigate upstream services
```

**What It Means:**
- More than 2% of requests (in the last 200 requests) returned 5xx errors
- This could indicate application issues, resource constraints, or dependency failures
- Users may be experiencing degraded service

**Immediate Actions:**

1. **Check current error rate in real-time:**
```bash
   docker-compose logs alert_watcher --tail=20
```

2. **Inspect both pools:**
```bash
   # Check Blue health
   curl http://localhost:8081/version
   
   # Check Green health
   curl http://localhost:8082/version
```

3. **Review Nginx error logs:**
```bash
   docker-compose exec nginx tail -n 50 /var/log/nginx/error.log
```

4. **Check container resource usage:**
```bash
   docker stats app_blue app_green
```

5. **Review recent application logs:**
```bash
   docker-compose logs app_blue app_green --tail=100
```

**Potential Causes:**
- Application code errors (bugs, exceptions)
- Resource exhaustion (CPU, memory)
- Database connection issues
- External API failures
- Network problems
- Chaos testing in progress

**Mitigation Steps:**

1. **If chaos mode is active (testing):**
```bash
   curl -X POST "http://localhost:8081/chaos/stop"
   curl -X POST "http://localhost:8082/chaos/stop"
```

2. **If resource constrained:**
```bash
   # Restart the affected container
   docker-compose restart app_blue
   # or
   docker-compose restart app_green
```

3. **If persistent application errors:**
   - Check application logs for stack traces
   - Review recent deployments for bad code
   - Consider rolling back to previous version

4. **If external dependency issue:**
   - Verify connectivity to databases/APIs
   - Check third-party service status pages
   - Implement circuit breaker if needed

---

## Configuration Parameters

The monitoring system can be tuned via environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `ERROR_RATE_THRESHOLD` | 2 | Percentage of 5xx errors to trigger alert (e.g., 2 = 2%) |
| `WINDOW_SIZE` | 200 | Number of recent requests to analyze for error rate |
| `ALERT_COOLDOWN_SEC` | 300 | Seconds between duplicate alerts (prevents spam) |
| `SLACK_WEBHOOK_URL` | - | Slack incoming webhook URL for alerts |

**To adjust thresholds:**

1. Edit `.env` file:
```bash
   nano .env
```

2. Modify values (example):
```bash
   ERROR_RATE_THRESHOLD=5    # More lenient (5%)
   WINDOW_SIZE=100           # Smaller window (faster detection)
   ALERT_COOLDOWN_SEC=600    # Longer cooldown (10 minutes)
```

3. Restart the watcher:
```bash
   docker-compose restart alert_watcher
```

---

## Maintenance Mode

### Suppressing Alerts During Planned Changes

When performing planned maintenance, deployments, or testing, you may want to temporarily suppress alerts.

**Option 1: Stop the Watcher**
```bash
docker-compose stop alert_watcher
```

Perform your maintenance, then restart:
```bash
docker-compose start alert_watcher
```

**Option 2: Adjust Cooldown**
```bash
# Set very long cooldown in .env
ALERT_COOLDOWN_SEC=7200  # 2 hours

# Restart watcher
docker-compose restart alert_watcher
```

**Option 3: Use a Different Slack Channel**
```bash
# Temporarily point to a #test-alerts channel
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/.../test-channel

# Restart watcher
docker-compose restart alert_watcher
```

---

## Testing the Alert System

### Test Failover Alert
```bash
# 1. Trigger chaos on Blue
curl -X POST "http://localhost:8081/chaos/start?mode=error"

# 2. Generate traffic to trigger failover
for i in {1..20}; do 
  curl -s http://localhost:8080/version > /dev/null
  sleep 0.2
done

# 3. Check Slack for failover alert

# 4. Stop chaos
curl -X POST "http://localhost:8081/chaos/stop"

# 5. Wait for recovery (traffic returns to blue)
sleep 10
curl -i http://localhost:8080/version | grep X-App-Pool
```

### Test Error Rate Alert
```bash
# 1. Keep chaos running
curl -X POST "http://localhost:8081/chaos/start?mode=error"

# 2. Generate enough traffic to exceed threshold
for i in {1..250}; do 
  curl -s http://localhost:8080/version > /dev/null
  sleep 0.1
done

# 3. Check Slack for error rate alert

# 4. Stop chaos
curl -X POST "http://localhost:8081/chaos/stop"
```

---

## Monitoring Dashboard

### View Real-Time Logs

**Watcher logs (shows alerts and metrics):**
```bash
docker-compose logs -f alert_watcher
```

**Nginx access logs (JSON format):**
```bash
docker-compose exec nginx tail -f /var/log/nginx/access.log
```

**All services:**
```bash
docker-compose logs -f
```

### Check Service Status
```bash
# All containers
docker-compose ps

# Specific service health
curl http://localhost:8080/version
curl http://localhost:8081/version
curl http://localhost:8082/version
```

---

## Troubleshooting

### No Alerts Received

**Check 1: Watcher is running**
```bash
docker-compose ps alert_watcher
```

**Check 2: Slack webhook configured**
```bash
docker-compose exec alert_watcher env | grep SLACK_WEBHOOK
```

**Check 3: Watcher logs for errors**
```bash
docker-compose logs alert_watcher | grep -i error
```

**Check 4: Test Slack webhook manually**
```bash
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test alert"}' \
  YOUR_SLACK_WEBHOOK_URL
```

### Alerts Too Frequent

**Adjust cooldown period:**
```bash
# In .env
ALERT_COOLDOWN_SEC=600  # 10 minutes instead of 5

# Restart
docker-compose restart alert_watcher
```

### False Positive Error Rate Alerts

**Adjust threshold:**
```bash
# In .env
ERROR_RATE_THRESHOLD=5  # 5% instead of 2%

# Restart
docker-compose restart alert_watcher
```

---

## Escalation

### When to Escalate

- Failover persists beyond 5 minutes
- Error rate remains high after mitigation attempts
- Both blue and green pools are failing
- Database or critical dependencies unavailable
- Security alerts or suspicious activity

### Escalation Contacts

- **Platform Team:** [Contact Info]
- **On-Call Engineer:** [Pager/Phone]
- **Infrastructure Team:** [Slack Channel]
- **Security Team:** [Emergency Contact]

---

## Appendix

### Log Format Reference

Each Nginx access log line contains:
```json
{
  "time": "ISO8601 timestamp",
  "remote_addr": "Client IP",
  "request": "HTTP method and path",
  "status": "HTTP status code",
  "request_time": "Total request time in seconds",
  "upstream_addr": "Upstream server address (app_blue or app_green)",
  "upstream_status": "Status from upstream",
  "upstream_response_time": "Upstream processing time",
  "pool": "blue or green",
  "release": "Release ID from X-Release-Id header"
}
```

### Alert Cooldown Behavior

- Alerts of the same type are rate-limited by `ALERT_COOLDOWN_SEC`
- Cooldown applies per alert type (failover and error rate tracked separately)
- After cooldown expires, the next occurrence will trigger a new alert
- This prevents alert spam during ongoing incidents

### Useful Commands
```bash
# View all environment variables
docker-compose config

# Restart all services
docker-compose restart

# View resource usage
docker stats

# Clean up and rebuild
docker-compose down
docker-compose up -d --build

# View Nginx configuration
docker-compose exec nginx cat /etc/nginx/conf.d/default.conf
```

---

**Document Version:** 1.0  
**Last Updated:** October 30, 2025  
