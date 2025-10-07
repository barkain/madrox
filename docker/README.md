# Madrox Docker Deployment Guide

Complete guide for deploying Madrox as a containerized MCP server using Docker and Docker Compose.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [Building & Running](#building--running)
5. [Data Persistence](#data-persistence)
6. [Health & Monitoring](#health--monitoring)
7. [Security](#security)
8. [Advanced Usage](#advanced-usage)
9. [Maintenance](#maintenance)
10. [Troubleshooting](#troubleshooting)

---

## Overview

### What's Included

The Madrox Docker setup provides:

- **Multi-stage build** - Optimized production image (Python 3.12-slim base)
- **Non-root execution** - Runs as `madrox` user (UID 1000)
- **Persistent storage** - Named volumes for database, logs, and workspaces
- **Health monitoring** - Automatic health checks with /health endpoint
- **Graceful shutdown** - Proper signal handling and cleanup
- **Resource limits** - Configurable CPU and memory constraints
- **Security hardening** - tmpfs mounts, no-new-privileges, minimal attack surface

### Architecture

```
┌─────────────────────────────────────────────────────┐
│ Container: madrox-server                            │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │ FastAPI Server (port 8001)                   │  │
│  │ ├─ /health (health checks)                   │  │
│  │ ├─ /mcp (MCP protocol endpoint)              │  │
│  │ └─ /tools (orchestration API)                │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │ Instance Manager                              │  │
│  │ ├─ Spawn/manage Claude instances             │  │
│  │ ├─ Spawn/manage Codex instances              │  │
│  │ └─ Hierarchical orchestration                │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  Persistent Volumes:                                │
│  ├─ /data          (SQLite database)               │
│  ├─ /logs          (Audit & instance logs)         │
│  └─ /tmp/claude_orchestrator (Instance workspaces) │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### System Requirements

- **Docker Engine**: 20.10+ (or Docker Desktop)
- **Docker Compose**: 2.0+ (plugin or standalone)
- **Host Resources**:
  - CPU: 2+ cores (4+ recommended)
  - RAM: 2GB minimum (4GB+ recommended)
  - Disk: 10GB+ available space
- **Network**: Internet access for Anthropic API calls

---

## Quick Start

### Prerequisites

1. Docker and Docker Compose installed
2. Anthropic API key (get one at [console.anthropic.com](https://console.anthropic.com))
3. Optional: OpenAI API key for Codex support

### 1. Clone Repository

```bash
git clone <repository-url>
cd madrox-containerization
```

### 2. Configure Environment

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` and set your API key:

```bash
# Required: Your Anthropic API key
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional: Adjust defaults
ORCHESTRATOR_PORT=8001
LOG_LEVEL=INFO
MAX_INSTANCES=10
```

### 3. Start Services

```bash
# Start Madrox in detached mode
docker compose up -d

# View logs
docker compose logs -f madrox
```

### 4. Verify Health

```bash
# Check health endpoint
curl http://localhost:8001/health

# Expected response:
# {"status":"healthy","instances_active":0,"instances_total":0}

# List available tools
curl http://localhost:8001/tools
```

### 5. Connect MCP Client

**Claude Desktop (macOS/Windows):**

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "madrox": {
      "url": "http://localhost:8001/mcp",
      "transport": "http"
    }
  }
}
```

Restart Claude Desktop.

**Claude Code CLI:**

```bash
# Register MCP server
claude mcp add madrox http://localhost:8001/mcp --transport http --model sonnet

# Verify registration
claude mcp list
```

---

## Configuration

### Environment Variables

#### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude instances | `sk-ant-api03-...` |

#### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ORCHESTRATOR_HOST` | `0.0.0.0` | Server bind address (use 0.0.0.0 for containers) |
| `ORCHESTRATOR_PORT` | `8001` | Server port (external port mapped via docker-compose) |

#### Resource Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_INSTANCES` | `10` | Maximum concurrent Claude/Codex instances |
| `MAX_TOKENS_PER_INSTANCE` | `100000` | Token limit per instance before termination |
| `MAX_TOTAL_COST` | `100.0` | Total cost limit in USD across all instances |
| `INSTANCE_TIMEOUT_MINUTES` | `60` | Auto-terminate idle instances after N minutes |

#### Storage & Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKSPACE_DIR` | `/tmp/claude_orchestrator` | Base directory for instance workspaces |
| `LOG_DIR` | `/logs` | Directory for audit logs and instance logs |
| `LOG_LEVEL` | `INFO` | Logging verbosity: DEBUG, INFO, WARNING, ERROR |
| `DATABASE_URL` | `sqlite:////data/claude_orchestrator.db` | SQLite database path |

#### Optional - Multi-Model Support

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for Codex instances | `sk-proj-...` |

### Configuration File Reference

**`.env` (recommended):**

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Server
ORCHESTRATOR_HOST=0.0.0.0
ORCHESTRATOR_PORT=8001

# Resource limits
MAX_INSTANCES=10
MAX_TOKENS_PER_INSTANCE=100000
MAX_TOTAL_COST=100.0
INSTANCE_TIMEOUT_MINUTES=60

# Storage
WORKSPACE_DIR=/tmp/claude_orchestrator
LOG_DIR=/logs
LOG_LEVEL=INFO
DATABASE_URL=sqlite:////data/claude_orchestrator.db

# Optional: OpenAI support
# OPENAI_API_KEY=sk-proj-your-key-here
```

**`docker-compose.yml` (already configured):**

All environment variables from `.env` are automatically loaded via `${VARIABLE:-default}` syntax. You typically don't need to edit docker-compose.yml unless customizing volumes or resource limits.

---

## Building & Running

### Using Docker Compose (Recommended)

Docker Compose handles multi-container setup, networking, and volumes automatically.

#### Start Services

```bash
# Start in background (detached)
docker compose up -d

# Start with logs visible
docker compose up

# Rebuild and start (after code changes)
docker compose up -d --build
```

#### View Logs

```bash
# Follow logs
docker compose logs -f

# View last 100 lines
docker compose logs --tail=100

# View logs for specific service
docker compose logs -f madrox
```

#### Stop Services

```bash
# Graceful shutdown (preserves data)
docker compose down

# Shutdown and remove volumes (⚠️ deletes database/logs)
docker compose down -v
```

#### Restart Services

```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart madrox
```

### Using Docker CLI (Manual)

For manual control without docker-compose:

#### Build Image

```bash
docker build -t madrox-mcp:latest .
```

#### Run Container

```bash
docker run -d \
  --name madrox-server \
  -p 8001:8001 \
  -e ANTHROPIC_API_KEY=sk-ant-your-key-here \
  -e LOG_LEVEL=INFO \
  -v madrox-data:/data \
  -v madrox-logs:/logs \
  -v madrox-workspaces:/tmp/claude_orchestrator \
  madrox-mcp:latest
```

#### Manage Container

```bash
# View logs
docker logs -f madrox-server

# Stop container
docker stop madrox-server

# Start stopped container
docker start madrox-server

# Remove container
docker rm -f madrox-server
```

### Development Build

For development with hot-reload:

```bash
# Mount source code as volume (changes reflected immediately)
docker run -d \
  --name madrox-dev \
  -p 8001:8001 \
  -e ANTHROPIC_API_KEY=sk-ant-your-key-here \
  -e LOG_LEVEL=DEBUG \
  -v $(pwd)/src:/app/src:ro \
  -v madrox-data:/data \
  -v madrox-logs:/logs \
  madrox-mcp:latest
```

**Note:** Hot-reload requires uvicorn's `--reload` flag. Modify `run_orchestrator.py` or override CMD:

```bash
docker run ... madrox-mcp:latest python -m uvicorn src.orchestrator.server:app --host 0.0.0.0 --port 8001 --reload
```

---

## Data Persistence

### Volume Overview

Three named volumes preserve data across container restarts:

| Volume | Mount Point | Purpose | Size Estimate |
|--------|-------------|---------|---------------|
| `madrox-data` | `/data` | SQLite database (instance metadata, state) | 100MB - 1GB |
| `madrox-logs` | `/logs` | Audit logs, instance logs, communication logs | 500MB - 5GB |
| `madrox-workspaces` | `/tmp/claude_orchestrator` | Instance working directories | 1GB - 10GB |

### Managing Volumes

#### Inspect Volumes

```bash
# List all volumes
docker volume ls

# Inspect volume details
docker volume inspect madrox-data

# View volume location on host
docker volume inspect madrox-data --format '{{.Mountpoint}}'
```

#### Backup Data

```bash
# Backup database
docker run --rm \
  -v madrox-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/madrox-data-$(date +%Y%m%d).tar.gz -C /data .

# Backup logs
docker run --rm \
  -v madrox-logs:/logs \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/madrox-logs-$(date +%Y%m%d).tar.gz -C /logs .
```

#### Restore Data

```bash
# Stop services first
docker compose down

# Restore database
docker run --rm \
  -v madrox-data:/data \
  -v $(pwd)/backups:/backup \
  alpine sh -c "cd /data && tar xzf /backup/madrox-data-20251007.tar.gz"

# Restart services
docker compose up -d
```

#### Clean Workspaces (Free Disk Space)

Instance workspaces can accumulate. Clean periodically:

```bash
# Connect to running container
docker exec -it madrox-server bash

# Inside container, remove old workspaces
find /tmp/claude_orchestrator -type d -mtime +7 -exec rm -rf {} + 2>/dev/null

# Or clean everything (⚠️ terminates active instances)
rm -rf /tmp/claude_orchestrator/*
```

#### Reset Everything

```bash
# ⚠️ WARNING: Deletes ALL data (database, logs, workspaces)
docker compose down -v
docker compose up -d
```

---

## Health & Monitoring

### Health Checks

Madrox includes automatic health monitoring:

#### Docker Health Status

```bash
# Check container health
docker ps

# View health check logs
docker inspect madrox-server --format='{{json .State.Health}}' | jq
```

**Health Check Details:**
- **Interval:** Every 30 seconds
- **Timeout:** 10 seconds per check
- **Start Period:** 40 seconds (allows initialization)
- **Retries:** 3 failures before marked unhealthy
- **Endpoint:** `GET http://localhost:8001/health`

#### Manual Health Check

```bash
# HTTP health endpoint
curl http://localhost:8001/health

# Expected healthy response:
{
  "status": "healthy",
  "instances_active": 5,
  "instances_total": 12,
  "uptime_seconds": 3600
}

# Expected unhealthy response:
{
  "status": "unhealthy",
  "error": "Instance manager not responding"
}
```

### Monitoring Logs

#### Real-time Logs

```bash
# All logs
docker compose logs -f

# Last 100 lines
docker compose logs --tail=100 madrox

# Filter for errors
docker compose logs | grep ERROR

# Filter for specific instance
docker compose logs | grep "instance_id=abc123"
```

#### Log Structure

**Container stdout/stderr:**
```
[INFO] Starting Madrox MCP Server...
[INFO] Server started on http://0.0.0.0:8001
[INFO] Instance spawned: instance_id=abc123 name=frontend-dev
[ERROR] Instance timeout: instance_id=abc123
```

**Audit logs (JSON Lines format):**

Location: `/logs/audit/audit_YYYY-MM-DD.jsonl`

```jsonl
{"timestamp":"2025-10-07T12:30:45","event":"instance_spawn","instance_id":"abc123","name":"frontend-dev"}
{"timestamp":"2025-10-07T12:31:10","event":"message_exchange","instance_id":"abc123","tokens":150,"cost":0.00015}
{"timestamp":"2025-10-07T12:35:20","event":"instance_terminate","instance_id":"abc123","uptime_seconds":275}
```

Access audit logs:

```bash
# Copy logs to host
docker cp madrox-server:/logs/audit ./audit_logs

# Query logs inside container
docker exec madrox-server cat /logs/audit/audit-2025-10-07.jsonl | jq '.event'
```

### Resource Monitoring

#### Container Resource Usage

```bash
# Real-time stats
docker stats madrox-server

# Expected output:
# CONTAINER        CPU %   MEM USAGE / LIMIT   MEM %   NET I/O       BLOCK I/O
# madrox-server    15.2%   1.2GiB / 4GiB       30%     10MB / 5MB    100MB / 50MB
```

#### Disk Usage

```bash
# Volume sizes
docker system df -v | grep madrox

# Expected output:
# madrox-data          1.2GB     500MB
# madrox-logs          850MB     850MB
# madrox-workspaces    3.5GB     3.5GB
```

### Alerts & Notifications

#### Health Check Failures

When health checks fail, Docker marks container unhealthy but continues running. To auto-restart on unhealthy:

Edit `docker-compose.yml`:

```yaml
services:
  madrox:
    restart: unless-stopped
    # Add health-based restart (Docker 20.10+)
    deploy:
      restart_policy:
        condition: on-failure
        delay: 30s
        max_attempts: 5
```

#### External Monitoring

Integrate with monitoring systems:

```bash
# Prometheus exporter (example)
curl http://localhost:8001/metrics

# Grafana dashboard (example)
# Query: rate(madrox_requests_total[5m])
```

---

## Security

### Security Features

The Madrox container implements multiple security layers:

#### 1. Non-Root User

Container runs as `madrox` user (UID 1000), not root:

```dockerfile
# Dockerfile excerpt
RUN useradd -m -u 1000 -s /bin/bash madrox
USER madrox
```

Verify:

```bash
docker exec madrox-server whoami
# Output: madrox

docker exec madrox-server id
# Output: uid=1000(madrox) gid=1000(madrox) groups=1000(madrox)
```

#### 2. Security Options

Enabled in docker-compose.yml:

```yaml
security_opt:
  - no-new-privileges:true  # Prevent privilege escalation
```

#### 3. Resource Limits

CPU and memory constraints prevent resource exhaustion:

```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'      # Max 4 CPU cores
      memory: 4G       # Max 4GB RAM
    reservations:
      cpus: '1.0'      # Guaranteed 1 core
      memory: 512M     # Guaranteed 512MB
```

#### 4. Network Isolation

Container uses bridge network (isolated from host):

```bash
# Inspect network
docker network inspect madrox-network
```

#### 5. Tmpfs Mounts

Temporary data uses tmpfs (memory-backed, not persisted):

```yaml
tmpfs:
  - /tmp:mode=1777,size=1G    # Temp files
  - /run:mode=755,size=100M   # Runtime data
```

### API Key Security

#### Best Practices

1. **Never commit API keys** to version control
2. **Use `.env` file** (excluded by .gitignore)
3. **Rotate keys regularly** (every 90 days)
4. **Use read-only keys** if possible (limit permissions)
5. **Monitor API usage** at [console.anthropic.com](https://console.anthropic.com)

#### Secrets Management

For production deployments, use secrets management:

**Docker Swarm Secrets:**

```bash
# Create secret
echo "sk-ant-your-key-here" | docker secret create anthropic_key -

# Use in docker-compose.yml
services:
  madrox:
    secrets:
      - anthropic_key
    environment:
      ANTHROPIC_API_KEY_FILE: /run/secrets/anthropic_key

secrets:
  anthropic_key:
    external: true
```

**Kubernetes Secrets:**

```bash
# Create secret
kubectl create secret generic madrox-secrets \
  --from-literal=anthropic-api-key=sk-ant-your-key-here

# Reference in deployment
env:
  - name: ANTHROPIC_API_KEY
    valueFrom:
      secretKeyRef:
        name: madrox-secrets
        key: anthropic-api-key
```

### Network Security

#### Restrict External Access

By default, server binds to `0.0.0.0:8001` (all interfaces). For local-only access:

```yaml
# docker-compose.yml
ports:
  - "127.0.0.1:8001:8001"  # Only localhost can connect
```

#### Reverse Proxy with TLS

For production, use reverse proxy with HTTPS:

**Nginx Example:**

```nginx
server {
    listen 443 ssl http2;
    server_name madrox.example.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### Firewall Rules

Restrict access to port 8001:

```bash
# Allow only specific IP (example)
sudo ufw allow from 192.168.1.0/24 to any port 8001

# Or use Docker firewall (iptables)
iptables -I DOCKER-USER -p tcp --dport 8001 -s 192.168.1.0/24 -j ACCEPT
iptables -I DOCKER-USER -p tcp --dport 8001 -j DROP
```

### Vulnerability Scanning

Scan container image for vulnerabilities:

```bash
# Using Docker Scout
docker scout cves madrox-mcp:latest

# Using Trivy
trivy image madrox-mcp:latest

# Using Grype
grype madrox-mcp:latest
```

---

## Advanced Usage

### Custom Configuration

#### Override Entrypoint

Run custom initialization:

```bash
docker run -it --rm \
  -e ANTHROPIC_API_KEY=sk-ant-key \
  madrox-mcp:latest \
  /bin/bash -c "echo 'Custom init' && python run_orchestrator.py"
```

#### Mount Custom Scripts

Add initialization scripts:

```bash
# Create custom init
cat > custom_init.sh <<'EOF'
#!/bin/bash
echo "Running custom initialization..."
# Your custom logic here
EOF

# Mount and run
docker run -d \
  -v $(pwd)/custom_init.sh:/app/custom_init.sh:ro \
  -e ANTHROPIC_API_KEY=sk-ant-key \
  madrox-mcp:latest \
  /bin/bash -c "/app/custom_init.sh && python run_orchestrator.py"
```

### Multi-Instance Deployment

Run multiple Madrox instances on different ports:

#### docker-compose-multi.yml

```yaml
version: '3.8'

services:
  madrox-1:
    build:
      context: .
      dockerfile: Dockerfile
    image: madrox-mcp:latest
    container_name: madrox-server-1
    ports:
      - "${ORCHESTRATOR_PORT:-8001}:8001"
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      ORCHESTRATOR_PORT: 8001
    volumes:
      - madrox-data-1:/data
      - madrox-logs-1:/logs

  madrox-2:
    build:
      context: .
      dockerfile: Dockerfile
    image: madrox-mcp:latest
    container_name: madrox-server-2
    ports:
      - "8002:8001"
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      ORCHESTRATOR_PORT: 8001
    volumes:
      - madrox-data-2:/data
      - madrox-logs-2:/logs

volumes:
  madrox-data-1:
  madrox-logs-1:
  madrox-data-2:
  madrox-logs-2:
```

Start:

```bash
docker compose -f docker-compose-multi.yml up -d
```

### Integration with CI/CD

#### GitHub Actions Example

```yaml
# .github/workflows/deploy.yml
name: Deploy Madrox

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build Docker image
        run: docker build -t madrox-mcp:${{ github.sha }} .

      - name: Push to registry
        run: |
          echo "${{ secrets.DOCKER_PASSWORD }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
          docker tag madrox-mcp:${{ github.sha }} myregistry/madrox-mcp:latest
          docker push myregistry/madrox-mcp:latest

      - name: Deploy to server
        run: |
          ssh deploy@server.example.com "
            cd /opt/madrox &&
            docker compose pull &&
            docker compose up -d
          "
```

### Load Balancing

Use HAProxy or Nginx for load balancing multiple instances:

**HAProxy Example:**

```
# haproxy.cfg
frontend madrox_frontend
    bind *:8001
    mode http
    default_backend madrox_backend

backend madrox_backend
    mode http
    balance roundrobin
    option httpchk GET /health
    server madrox1 localhost:8001 check
    server madrox2 localhost:8002 check
    server madrox3 localhost:8003 check
```

### Database Migration

For production, consider external database (PostgreSQL):

```yaml
# docker-compose-postgres.yml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: madrox
      POSTGRES_USER: madrox
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data

  madrox:
    build: .
    environment:
      DATABASE_URL: postgresql://madrox:${DB_PASSWORD}@postgres:5432/madrox
    depends_on:
      - postgres

volumes:
  postgres-data:
```

**Note:** Requires database migration scripts (not included by default - SQLite-only currently).

---

## Maintenance

### Regular Maintenance Tasks

#### 1. Log Rotation

Logs auto-rotate (5MB per file, 3 backups), but clean old logs periodically:

```bash
# Remove logs older than 30 days
docker exec madrox-server find /logs -name "*.log" -mtime +30 -delete

# Remove old audit logs
docker exec madrox-server find /logs/audit -name "*.jsonl" -mtime +30 -delete
```

#### 2. Database Cleanup

```bash
# Vacuum database (reclaim space)
docker exec madrox-server sqlite3 /data/claude_orchestrator.db "VACUUM;"

# Check database size
docker exec madrox-server du -sh /data/claude_orchestrator.db
```

#### 3. Workspace Cleanup

```bash
# Remove terminated instance workspaces
docker exec madrox-server bash -c "
  find /tmp/claude_orchestrator -type d -mtime +7 -exec rm -rf {} + 2>/dev/null
"
```

#### 4. Volume Pruning

```bash
# Remove unused volumes (⚠️ careful - checks first)
docker volume ls -qf dangling=true

# Prune dangling volumes
docker volume prune -f
```

### Updates & Upgrades

#### Update to Latest Version

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker compose down
docker compose up -d --build

# Verify health
curl http://localhost:8001/health
```

#### Rolling Update (Zero Downtime)

For multi-instance setups:

```bash
# Update instance 1
docker compose stop madrox-1
docker compose up -d --build madrox-1

# Wait for health check
sleep 30

# Update instance 2
docker compose stop madrox-2
docker compose up -d --build madrox-2
```

### Backup Strategy

#### Automated Backup Script

```bash
#!/bin/bash
# backup_madrox.sh

BACKUP_DIR="/backups/madrox"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup database
docker run --rm \
  -v madrox-data:/data \
  -v "$BACKUP_DIR":/backup \
  alpine tar czf /backup/data_$DATE.tar.gz -C /data .

# Backup logs
docker run --rm \
  -v madrox-logs:/logs \
  -v "$BACKUP_DIR":/backup \
  alpine tar czf /backup/logs_$DATE.tar.gz -C /logs .

# Remove backups older than 7 days
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/data_$DATE.tar.gz"
```

Schedule with cron:

```bash
# Run daily at 2 AM
0 2 * * * /opt/madrox/backup_madrox.sh
```

---

## Troubleshooting

### Common Issues

#### Issue: Container Won't Start

**Symptom:** `docker compose up` fails immediately

**Diagnosis:**

```bash
# Check container logs
docker compose logs madrox

# Check container status
docker ps -a
```

**Common Causes:**

1. **Missing API key:**
   ```
   [ERROR] ANTHROPIC_API_KEY is not set
   ```
   **Fix:** Set `ANTHROPIC_API_KEY` in `.env` file

2. **Port already in use:**
   ```
   Error: bind: address already in use
   ```
   **Fix:** Change port in `.env` or stop conflicting service
   ```bash
   # Find process using port 8001
   lsof -i :8001
   kill <PID>
   ```

3. **Invalid API key format:**
   ```
   [WARN] ANTHROPIC_API_KEY format may be invalid
   ```
   **Fix:** Verify key starts with `sk-ant-`

#### Issue: Health Check Failing

**Symptom:** `docker ps` shows container as "unhealthy"

**Diagnosis:**

```bash
# Check health check logs
docker inspect madrox-server --format='{{json .State.Health}}' | jq

# Test health endpoint manually
docker exec madrox-server curl -f http://localhost:8001/health
```

**Common Causes:**

1. **Server not responding:**
   ```bash
   # Check if server process is running
   docker exec madrox-server ps aux | grep python
   ```
   **Fix:** Restart container
   ```bash
   docker compose restart madrox
   ```

2. **Port binding issue:**
   ```bash
   # Check port binding inside container
   docker exec madrox-server netstat -tlnp | grep 8001
   ```

3. **Insufficient resources:**
   ```bash
   # Check resource usage
   docker stats madrox-server
   ```
   **Fix:** Increase memory limit in docker-compose.yml

#### Issue: Cannot Connect to MCP Server

**Symptom:** Claude Desktop/CLI can't connect to Madrox

**Diagnosis:**

```bash
# Test connectivity
curl http://localhost:8001/health

# Check if port is accessible
telnet localhost 8001
```

**Common Causes:**

1. **Firewall blocking connection:**
   ```bash
   # Check firewall rules
   sudo ufw status
   ```
   **Fix:** Allow port 8001
   ```bash
   sudo ufw allow 8001/tcp
   ```

2. **Wrong URL in MCP config:**
   **Fix:** Verify URL is `http://localhost:8001/mcp` (not `/` or `/tools`)

3. **Container not running:**
   ```bash
   docker ps | grep madrox
   ```
   **Fix:** Start container
   ```bash
   docker compose up -d
   ```

#### Issue: Instance Spawn Failures

**Symptom:** Spawning Claude instances fails with errors

**Diagnosis:**

```bash
# Check logs for spawn errors
docker compose logs | grep -i "spawn"

# Check instance logs
docker exec madrox-server ls -la /logs/instances/
```

**Common Causes:**

1. **API rate limit:**
   ```
   Error: Rate limit exceeded
   ```
   **Fix:** Wait and retry, or upgrade API tier

2. **Insufficient workspace permissions:**
   ```bash
   # Check workspace directory
   docker exec madrox-server ls -ld /tmp/claude_orchestrator
   ```
   **Fix:** Ensure `madrox` user owns directory

3. **tmux not available:**
   ```
   Error: tmux command not found
   ```
   **Fix:** Rebuild image (tmux should be installed by Dockerfile)

#### Issue: High Memory Usage

**Symptom:** Container using excessive RAM

**Diagnosis:**

```bash
# Monitor memory usage
docker stats madrox-server

# Check active instances
curl http://localhost:8001/instances | jq '.[] | {id, name, status}'
```

**Solutions:**

1. **Reduce MAX_INSTANCES:**
   ```bash
   # In .env
   MAX_INSTANCES=5
   ```

2. **Set stricter token limits:**
   ```bash
   # In .env
   MAX_TOKENS_PER_INSTANCE=50000
   ```

3. **Terminate idle instances:**
   ```bash
   # Set shorter timeout
   INSTANCE_TIMEOUT_MINUTES=30
   ```

#### Issue: Disk Space Exhausted

**Symptom:** "No space left on device" errors

**Diagnosis:**

```bash
# Check volume sizes
docker system df -v

# Check workspace size
docker exec madrox-server du -sh /tmp/claude_orchestrator/*
```

**Solutions:**

1. **Clean old workspaces:**
   ```bash
   docker exec madrox-server rm -rf /tmp/claude_orchestrator/*
   ```

2. **Prune old logs:**
   ```bash
   docker exec madrox-server find /logs -name "*.log" -mtime +7 -delete
   ```

3. **Clean Docker system:**
   ```bash
   docker system prune -af --volumes
   ```

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Stop services
docker compose down

# Start with DEBUG logging
LOG_LEVEL=DEBUG docker compose up

# Or edit .env
echo "LOG_LEVEL=DEBUG" >> .env
docker compose up -d
```

### Accessing Container Shell

For advanced debugging:

```bash
# Open interactive shell
docker exec -it madrox-server bash

# Inside container:
# - Check processes: ps aux
# - Check network: netstat -tlnp
# - Check files: ls -la /data /logs
# - Test API: curl http://localhost:8001/health
# - View logs: tail -f /logs/audit/audit-*.jsonl
```

### Support Resources

- **GitHub Issues:** [Report bugs/issues](https://github.com/your-repo/issues)
- **Documentation:** Main README at repository root
- **Health Check:** `GET http://localhost:8001/health`
- **API Reference:** `GET http://localhost:8001/tools`

---

## Additional Resources

- **Main Documentation:** [../README.md](../README.md)
- **MCP Setup Guide:** [../MCP_SETUP.md](../MCP_SETUP.md)
- **Quick Start:** [../QUICK_START.md](../QUICK_START.md)
- **Stress Testing:** [../docs/STRESS_TESTING.md](../docs/STRESS_TESTING.md)

---

**Ready for production deployment!** 🚀

For questions or issues, consult the main project documentation or open an issue on GitHub.
