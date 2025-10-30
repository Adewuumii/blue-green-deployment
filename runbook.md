# Blue/Green Deployment Runbook

Quick operational guide for responding to monitoring alerts.

---

## Alert Types

### Failover Detected

**Alert Message:**
```
Failover Detected
Pool changed: blue → green
Time: [timestamp]
Action: Check health of blue container
```

**What It Means:**
- Primary pool failed health checks
- Traffic automatically routed to backup
- Zero downtime maintained

**Immediate Actions:**

1. **Verify current pool:**
```bash
   curl -i http://localhost:8080/version | grep X-App-Pool
```

2. **Check failed pool logs:**
```bash
   # If blue failed:
   docker-compose logs app_blue --tail=50
   
   # If green failed:
   docker-compose logs app_green --tail=50
```

3. **Stop chaos if testing:**
```bash
   curl -X POST "http://localhost:8081/chaos/stop"
   curl -X POST "http://localhost:8082/chaos/stop"
```

4. **Wait for recovery:**
   - After 6+ seconds, traffic returns to primary automatically
   - Verify: `curl -i http://localhost:8080/version | grep X-App-Pool`

**When to Escalate:**
- Failover persists > 1 minute
- Pool won't recover
- Repeated failovers

---

### High Error Rate Detected

**Alert Message:**
```
 High Error Rate Detected!
Error rate: 5.5% (threshold: 2%)
Window size: 200 requests
Time: [timestamp]
Action: Investigate upstream services
```

**What It Means:**
- More than 2% of recent requests returned 5xx errors
- Users experiencing degraded service
- Application or dependency issues

**Immediate Actions:**

1. **Check watcher logs:**
```bash
   docker-compose logs alert_watcher --tail=20
```

2. **Test both pools:**
```bash
   curl http://localhost:8081/version  # Blue
   curl http://localhost:8082/version  # Green
```

3. **Check Nginx errors:**
```bash
   docker-compose exec nginx tail -n 50 /var/log/nginx/error.log
```

4. **If chaos mode is active:**
```bash
   curl -X POST "http://localhost:8081/chaos/stop"
   curl -X POST "http://localhost:8082/chaos/stop"
```

5. **If resource issues:**
```bash
   docker stats app_blue app_green
   docker-compose restart app_blue  # or app_green
```

**Common Causes:**
- Chaos testing in progress
- Application bugs/crashes
- Resource exhaustion (CPU/memory)
- Database/API connectivity issues

**When to Escalate:**
- Error rate stays high after stopping chaos
- Both pools failing
- Unknown root cause

---

## Configuration

Adjust thresholds in `.env`:
```bash
ERROR_RATE_THRESHOLD=2      # Alert when errors > 2%
WINDOW_SIZE=200             # Analyze last 200 requests
ALERT_COOLDOWN_SEC=60      # Wait 1 minute between alerts
```

**Apply changes:**
```bash
docker-compose restart alert_watcher
```

---

## Testing Alerts

### Test Failover Alert
```bash
# Trigger chaos on Blue
curl -X POST "http://localhost:8081/chaos/start?mode=error"

# Generate traffic
for i in {1..20}; do curl -s http://localhost:8080/version > /dev/null; sleep 0.2; done

# Check Slack for alert
# Stop chaos
curl -X POST "http://localhost:8081/chaos/stop"
```

### Test Error Rate Alert
```bash
# Trigger chaos on BOTH pools
curl -X POST "http://localhost:8081/chaos/start?mode=error"
curl -X POST "http://localhost:8082/chaos/start?mode=error"

# Generate traffic
for i in {1..250}; do curl -s http://localhost:8080/version > /dev/null; sleep 0.05; done

# Check Slack for alert
# Stop chaos
curl -X POST "http://localhost:8081/chaos/stop"
curl -X POST "http://localhost:8082/chaos/stop"
```

---

## Monitoring Commands
```bash
# View watcher logs (real-time)
docker-compose logs -f alert_watcher

# View Nginx JSON logs
docker-compose exec nginx tail -f /var/log/nginx/access.log

# Check container status
docker-compose ps

# Check resource usage
docker stats

# Restart all services
docker-compose restart

# View all logs
docker-compose logs --tail=100
```

---

## Troubleshooting

**No alerts received:**
1. Check watcher is running: `docker-compose ps alert_watcher`
2. Verify Slack webhook: `docker-compose exec alert_watcher env | grep SLACK`
3. Check watcher logs: `docker-compose logs alert_watcher`

**Alerts too frequent:**
- Increase `ALERT_COOLDOWN_SEC` in `.env`
- Restart watcher: `docker-compose restart alert_watcher`

**False positive error alerts:**
- Increase `ERROR_RATE_THRESHOLD` in `.env`
- Restart watcher: `docker-compose restart alert_watcher`

---
 
**Last Updated:** October 30, 2025