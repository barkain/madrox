# Troubleshooting Guide

Comprehensive guide for diagnosing and resolving common issues with Madrox.

## Quick Diagnostics

### Fast Health Checks

```bash
# Check if server is running
curl http://localhost:8001/health

# List all instances
curl http://localhost:8001/instances

# Check specific instance status
curl http://localhost:8001/instances/{instance_id}

# View orchestrator logs
tail -f /tmp/madrox_logs/orchestrator.log

# Check recent audit events
tail -n 100 /tmp/madrox_logs/audit/audit_$(date +%Y%m%d).jsonl
```

### Quick Verification Checklist

- [ ] Server running on port 8001
- [ ] Python 3.11+ installed
- [ ] Required dependencies installed (`uv sync --all-groups`)
- [ ] Anthropic API key set (if using direct API)
- [ ] Workspace directory writable (`/tmp/claude_orchestrator`)
- [ ] Log directory writable (`/tmp/madrox_logs`)

## Common Issues

### Installation Issues

#### Server Won't Start

**Symptoms:**
- Error when running `python run_orchestrator.py`
- "Module not found" errors
- Port binding failures

**Causes:**
1. Missing dependencies
2. Port 8001 already in use
3. Python version incompatibility

**Solutions:**

```bash
# Verify Python version (3.11+ required)
python --version

# Install/update dependencies
cd src/orchestrator
uv sync --all-groups

# Check if port 8001 is in use
lsof -i :8001

# Kill process using port 8001
kill -9 $(lsof -t -i:8001)

# Use alternate port
export ORCHESTRATOR_PORT=8002
python run_orchestrator.py
```

#### Dependencies Installation Failure

**Symptoms:**
- `uv sync` fails
- Package conflicts
- Build errors

**Solutions:**

```bash
# Clear cache and reinstall
rm -rf .venv
uv sync --all-groups

# Verify uv installation
uv --version

# Update uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Type Errors in Tests

**Symptoms:**
- Type checking failures
- `pyright` or `mypy` errors

**Solutions:**

```bash
# Ensure Python 3.11+ is being used
python --version

# Modern Python type syntax requires 3.11+
# Check pyproject.toml for requires-python setting
```

### Runtime Issues

#### Instance Spawn Fails

**Symptoms:**
- `spawn_claude` or `spawn_codex_instance` returns error
- Instance never becomes ready
- Timeout during initialization

**Causes:**
1. Invalid Anthropic API key
2. Missing Claude Code CLI installation
3. tmux session creation failure
4. Workspace permission issues

**Solutions:**

```bash
# Verify API key (if using direct API)
echo $ANTHROPIC_API_KEY

# Check Claude CLI installation
claude --version

# Verify tmux is installed
tmux -V

# Check workspace permissions
ls -la /tmp/claude_orchestrator
chmod 755 /tmp/claude_orchestrator

# Enable debug logging
export LOG_LEVEL=DEBUG
python run_orchestrator.py

# Check instance logs
tail -f /tmp/madrox_logs/instances/{instance_id}/instance.log
```

#### Instance Not Responding

**Symptoms:**
- `send_to_instance` times out
- Instance shows as "running" but no output
- Messages queue up without responses

**Diagnosis:**

```python
# Check instance status
status = manager.get_instance_status(instance_id)
print(f"State: {status['state']}")
print(f"Last activity: {status['last_activity_time']}")

# Get raw tmux output
logs = await manager.get_instance_logs(
    instance_id=instance_id,
    log_type="tmux_output",
    tail=50
)
for line in logs:
    print(line)

# Check communication logs
comm_logs = await manager.get_instance_logs(
    instance_id=instance_id,
    log_type="communication",
    tail=20
)
```

**Solutions:**

```python
# Interrupt stuck instance (preserves context)
await manager.interrupt_instance(instance_id)

# Send simpler task to verify responsiveness
await manager.send_to_instance(instance_id, "Reply with 'OK'")

# If still unresponsive, terminate and respawn
await manager.terminate_instance(instance_id)
```

#### Message Delivery Failures

**Symptoms:**
- `send_to_instance` returns error
- Parent-child communication breaks
- `broadcast_to_children` fails

**Solutions:**

```python
# Verify instance exists and is running
instances = manager.list_instances()
print([i["instance_id"] for i in instances])

# Check parent-child relationships
tree = manager.get_instance_tree()
print(tree)

# For children, verify parent is still alive
children = manager.get_children(parent_id)
print(f"Active children: {len(children)}")

# Retry with explicit error handling
try:
    response = await manager.send_to_instance(
        instance_id,
        message,
        timeout_seconds=60
    )
except TimeoutError:
    print("Instance timed out - may be processing")
except InstanceNotFoundError:
    print("Instance no longer exists")
```

#### Hierarchical Communication Issues

**Symptoms:**
- Child instances can't spawn their own children
- Parent can't see grandchildren
- `get_instance_tree` incomplete

**Solutions:**

```python
# Verify Madrox is enabled for child
instance = await manager.spawn_instance(
    name="parent-instance",
    enable_madrox=True  # Critical for hierarchical spawning
)

# Check if child has Madrox access
status = manager.get_instance_status(child_id)
print(f"Madrox enabled: {status.get('enable_madrox', False)}")

# View complete hierarchy
tree = manager.get_instance_tree()
# Should show parent → child → grandchild relationships
```

### Performance Issues

#### Slow Instance Spawning

**Symptoms:**
- `spawn_instance` takes >30 seconds
- Initialization hangs
- Multiple spawns block each other

**Solutions:**

```python
# Use parallel spawning for multiple instances
instances = await manager.spawn_multiple_instances([
    {"name": "worker-1", "role": "general", "wait_for_ready": False},
    {"name": "worker-2", "role": "general", "wait_for_ready": False},
    {"name": "worker-3", "role": "general", "wait_for_ready": False},
])
# Returns immediately, instances initialize in background

# Use non-blocking mode for single spawn
instance_id = await manager.spawn_instance(
    name="async-worker",
    wait_for_ready=False  # Don't block waiting for initialization
)
# Poll for readiness separately
```

#### High Response Times

**Symptoms:**
- `send_to_instance` takes >30 seconds
- Communication logs show slow response_time_seconds

**Diagnosis:**

```python
# Analyze response times from audit logs
audit = await manager.get_audit_logs(limit=1000)

response_times = [
    entry["details"]["response_time_seconds"]
    for entry in audit
    if entry["event_type"] == "message_exchange"
]

avg_response = sum(response_times) / len(response_times)
max_response = max(response_times)
print(f"Average: {avg_response:.2f}s, Max: {max_response:.2f}s")

# Find slow messages
slow_messages = [
    entry for entry in audit
    if entry["event_type"] == "message_exchange"
    and entry["details"]["response_time_seconds"] > 10
]
```

**Solutions:**

1. **Reduce message complexity** - Break large tasks into smaller steps
2. **Use cheaper models** - Haiku for simpler tasks instead of Opus
3. **Check token limits** - Large responses take longer
4. **Monitor resource usage** - Ensure system has adequate CPU/memory

#### Resource Exhaustion

**Symptoms:**
- Instance hit token limit
- Cost exceeded
- System running out of memory

**Solutions:**

```python
# Set explicit resource limits when spawning
instance_id = await manager.spawn_instance(
    name="limited-worker",
    max_total_tokens=50000,
    max_cost=10.0,
    timeout_minutes=30
)

# Monitor usage
status = manager.get_instance_status(instance_id)
print(f"Tokens: {status['total_tokens_used']}/{status.get('max_total_tokens', 'unlimited')}")
print(f"Cost: ${status['total_cost']:.4f}/{status.get('max_cost', 'unlimited')}")

# Terminate expensive instances
if status['total_cost'] > 5.0:
    await manager.terminate_instance(instance_id)

# Check system-wide limits
config = OrchestratorConfig(
    max_concurrent_instances=10,
    max_total_cost=100.0
)
```

### Network Issues

#### HTTP Transport Failures

**Symptoms:**
- MCP HTTP requests fail
- Claude Desktop can't connect
- "Connection refused" errors

**Solutions:**

```bash
# Verify HTTP server is running
curl http://localhost:8001/health

# Check server logs
tail -f /tmp/madrox_logs/orchestrator.log | grep ERROR

# Restart HTTP server
pkill -f "run_orchestrator.py"
python run_orchestrator.py

# Verify port not blocked by firewall
# macOS:
sudo pfctl -s rules | grep 8001

# Linux:
sudo iptables -L | grep 8001
```

#### Stdio Transport Issues (Codex)

**Symptoms:**
- Codex instances can't connect
- stdio proxy errors
- "No such command" in Codex

**Solutions:**

```bash
# Verify stdio server is running
ps aux | grep run_orchestrator_stdio.py

# Check if HTTP server is reachable from stdio
curl http://localhost:8001/health

# Restart stdio proxy
python run_orchestrator_stdio.py

# Test Codex MCP connection
codex mcp list
# Should show 'madrox' in the list
```

#### MCP Server Registration

**Symptoms:**
- Claude Desktop doesn't show Madrox tools
- "Unknown MCP server" errors
- Tools not available in sessions

**Solutions:**

**For Claude Desktop:**

```bash
# macOS config location
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Windows config location
type %APPDATA%\Claude\claude_desktop_config.json

# Verify config format
{
  "mcpServers": {
    "madrox": {
      "url": "http://localhost:8001",
      "transport": "http"
    }
  }
}

# Restart Claude Desktop after config changes
```

**For Claude CLI:**

```bash
# Re-register MCP server
claude mcp remove madrox
claude mcp add madrox http://localhost:8001/mcp --transport http

# Verify registration
claude mcp list

# Test tools availability
claude
# In session, tools should appear automatically
```

## Debugging

### Debug Mode

**Enable verbose logging:**

```bash
# Set debug level
export LOG_LEVEL=DEBUG

# Run server with debug output
python run_orchestrator.py

# Watch debug logs in real-time
tail -f /tmp/madrox_logs/orchestrator.log | grep DEBUG
```

### Log Analysis

#### Per-Instance Logs

**Location:** `/tmp/madrox_logs/instances/{instance_id}/`

```bash
# View lifecycle events
cat /tmp/madrox_logs/instances/{instance_id}/instance.log

# View all messages
cat /tmp/madrox_logs/instances/{instance_id}/communication.jsonl | jq

# View raw tmux output (most detailed)
cat /tmp/madrox_logs/instances/{instance_id}/tmux_output.log

# Check instance metadata
cat /tmp/madrox_logs/instances/{instance_id}/metadata.json | jq
```

**Programmatic access:**

```python
# Get specific log type
logs = await manager.get_instance_logs(
    instance_id="abc123",
    log_type="communication",  # or "instance", "tmux_output"
    tail=100  # last 100 lines, 0 for all
)

# Parse communication logs
import json
with open(f"/tmp/madrox_logs/instances/{instance_id}/communication.jsonl") as f:
    messages = [json.loads(line) for line in f]

# Find message by content
target = [m for m in messages if "error" in m["content"].lower()]
```

#### System-Wide Audit Trail

**Location:** `/tmp/madrox_logs/audit/audit_{YYYYMMDD}.jsonl`

```bash
# View today's audit log
cat /tmp/madrox_logs/audit/audit_$(date +%Y%m%d).jsonl | jq

# Count events by type
cat /tmp/madrox_logs/audit/audit_$(date +%Y%m%d).jsonl | \
  jq -s 'group_by(.event_type) | map({event: .[0].event_type, count: length})'

# Calculate total cost for the day
cat /tmp/madrox_logs/audit/audit_$(date +%Y%m%d).jsonl | \
  jq -s 'map(select(.event_type == "message_exchange") | .details.cost) | add'

# Find slow responses (>5 seconds)
cat /tmp/madrox_logs/audit/audit_$(date +%Y%m%d).jsonl | \
  jq 'select(.event_type == "message_exchange" and .details.response_time_seconds > 5)'

# Track instance lifecycle
cat /tmp/madrox_logs/audit/audit_$(date +%Y%m%d).jsonl | \
  jq 'select(.instance_id == "abc123")'
```

**Programmatic queries:**

```python
# Query recent audit events
audit = await manager.get_audit_logs(
    since="2025-10-03T00:00:00",
    limit=100
)

# Cost analysis
total_cost = sum(
    entry["details"]["cost"]
    for entry in audit
    if entry["event_type"] == "message_exchange"
)
print(f"Total cost: ${total_cost:.4f}")

# Performance metrics
response_times = [
    entry["details"]["response_time_seconds"]
    for entry in audit
    if entry["event_type"] == "message_exchange"
]
avg = sum(response_times) / len(response_times)
print(f"Average response time: {avg:.2f}s")

# Find errors
errors = [
    entry for entry in audit
    if "error" in entry.get("details", {})
]
```

#### Orchestrator System Logs

**Location:** `/tmp/madrox_logs/orchestrator.log`

```bash
# View errors only
cat /tmp/madrox_logs/orchestrator.log | jq 'select(.level == "ERROR")'

# View warnings and errors
cat /tmp/madrox_logs/orchestrator.log | jq 'select(.level == "WARNING" or .level == "ERROR")'

# Filter by module
cat /tmp/madrox_logs/orchestrator.log | jq 'select(.module == "instance_manager")'

# Recent activity (last 50 lines)
tail -n 50 /tmp/madrox_logs/orchestrator.log | jq
```

### Diagnostic Tools

#### Instance Health Checks

```python
# Get all instance statuses
instances = manager.list_instances()
for inst in instances:
    status = manager.get_instance_status(inst["instance_id"])
    print(f"{inst['name']}: {status['state']} (tokens: {status['total_tokens_used']}, cost: ${status['total_cost']:.4f})")

# Check if instance is responsive
try:
    response = await manager.send_to_instance(
        instance_id,
        "Echo: OK",
        timeout_seconds=10
    )
    print(f"Instance responsive: {response}")
except TimeoutError:
    print("Instance unresponsive (timeout)")
```

#### Network Topology Verification

```python
# View full instance tree
tree = manager.get_instance_tree()
print(tree)

# Expected format:
# Parent (abc123) [idle] (claude)
# ├── Child1 (def456) [running] (claude)
# │   └── Grandchild1 (xyz789) [idle] (codex)
# └── Child2 (ghi012) [running] (claude)

# Verify parent-child relationships
parent_id = "abc123"
children = manager.get_children(parent_id)
print(f"Parent {parent_id} has {len(children)} children")

# Check for orphaned instances
all_instances = manager.list_instances()
for inst in all_instances:
    if inst.get("parent_instance_id"):
        # Verify parent exists
        try:
            parent = manager.get_instance_status(inst["parent_instance_id"])
            print(f"✓ {inst['name']} parent valid")
        except InstanceNotFoundError:
            print(f"✗ {inst['name']} parent missing (orphaned)")
```

#### Message Flow Tracing

```python
# Trace message through hierarchy
async def trace_message(instance_id, message):
    """Send message and track through logs."""
    print(f"Sending to {instance_id}: {message}")

    # Send message
    response = await manager.send_to_instance(instance_id, message)

    # Check communication log
    logs = await manager.get_instance_logs(
        instance_id=instance_id,
        log_type="communication",
        tail=5
    )

    print("Recent communication:")
    for log in logs:
        print(f"  {log}")

    return response

# Trace broadcast
async def trace_broadcast(parent_id, message):
    """Trace broadcast to all children."""
    children_before = manager.get_children(parent_id)
    print(f"Broadcasting to {len(children_before)} children")

    responses = await manager.broadcast_to_children(
        parent_id=parent_id,
        message=message,
        wait_for_responses=True
    )

    print(f"Received {len(responses)} responses")
    for child_id, response in responses.items():
        print(f"  {child_id}: {response[:50]}...")
```

## FAQ

### General Questions

**Q: Do I need an Anthropic API key?**

A: Not if you have a Claude Pro subscription and use Claude Desktop or Claude CLI. The key is only needed for direct API access via the Python SDK.

**Q: What's the difference between Claude and Codex instances?**

A: Claude instances use Anthropic's Claude models (Opus, Sonnet, Haiku) and support hierarchical spawning. Codex instances use OpenAI's Codex model and are great for code generation tasks. Both can work together in multi-model networks.

**Q: Can instances spawn their own children?**

A: Yes! Set `enable_madrox=True` when spawning an instance to give it access to Madrox tools. It can then spawn its own children, creating hierarchies 3+ levels deep.

**Q: How do I see all instances in the network?**

A: Use `manager.get_instance_tree()` for a hierarchical view, or `manager.list_instances()` for a flat list with full details.

### Configuration Questions

**Q: Can I change the default model?**

A: Yes. Set `model` parameter when spawning:
```python
instance_id = await manager.spawn_instance(
    name="worker",
    model="claude-opus-4"  # or sonnet, haiku
)
```

**Q: How do I limit resource usage?**

A: Set limits when spawning instances:
```python
instance_id = await manager.spawn_instance(
    name="limited",
    max_total_tokens=50000,
    max_cost=10.0,
    timeout_minutes=30
)
```

**Q: Can I add custom MCP servers to instances?**

A: Yes! Use the MCP loader utility:
```python
from orchestrator.mcp_loader import get_mcp_servers

mcp_servers = get_mcp_servers("playwright", "github", "postgres")
instance_id = await manager.spawn_instance(
    name="browser-agent",
    mcp_servers=mcp_servers
)
```

### Operational Questions

**Q: How do I stop a long-running task without losing context?**

A: Use `interrupt_instance()`:
```python
await manager.interrupt_instance(instance_id)
# Instance stops current task but preserves all context
# Can immediately send new task
```

**Q: What happens to logs when I terminate an instance?**

A: Logs are preserved in `/tmp/madrox_logs/instances/{instance_id}/`. They remain after termination for debugging and audit purposes.

**Q: How do I resume a workflow across sessions?**

A: Instance state is currently ephemeral (lost on termination). Workflow persistence is on the roadmap. For now, use logs to reconstruct state:
```python
# Get full communication history
logs = await manager.get_instance_logs(
    instance_id=old_instance_id,
    log_type="communication",
    tail=0  # all logs
)
# Use logs to recreate context in new instance
```

**Q: Can I run multiple Madrox servers?**

A: Yes, use different ports:
```bash
# Server 1
export ORCHESTRATOR_PORT=8001
python run_orchestrator.py &

# Server 2
export ORCHESTRATOR_PORT=8002
python run_orchestrator.py &
```

### Troubleshooting Questions

**Q: Instance stuck in "initializing" state?**

A: Check logs for initialization errors:
```bash
tail -f /tmp/madrox_logs/instances/{instance_id}/tmux_output.log
```
Common causes: API key issues, Claude CLI not installed, tmux problems.

**Q: Why can't my child instance spawn grandchildren?**

A: Ensure `enable_madrox=True` when spawning the child:
```python
child_id = await manager.spawn_instance(
    name="child",
    parent_instance_id=parent_id,
    enable_madrox=True  # Critical!
)
```

**Q: How do I debug message delivery failures?**

A: Check communication logs on both sides:
```python
# Sender side
sender_logs = await manager.get_instance_logs(sender_id, "communication")

# Receiver side
receiver_logs = await manager.get_instance_logs(receiver_id, "communication")

# Also check audit trail
audit = await manager.get_audit_logs(limit=50)
```

## Getting Help

### Before Reporting Issues

1. **Check logs**: Start with `/tmp/madrox_logs/orchestrator.log`
2. **Enable debug mode**: `export LOG_LEVEL=DEBUG`
3. **Review instance logs**: Check `tmux_output.log` for stuck instances
4. **Query audit trail**: Look for patterns in message exchanges
5. **Verify configuration**: Ensure all environment variables are set correctly

### Reporting Issues

When reporting issues, include:

**System Information:**
- Operating system and version
- Python version (`python --version`)
- Madrox version/commit hash
- Claude CLI version (`claude --version`)

**Configuration:**
```bash
# Sanitize API keys before sharing!
env | grep -E "ORCHESTRATOR|ANTHROPIC|LOG_"
```

**Relevant Logs:**
```bash
# Orchestrator errors
cat /tmp/madrox_logs/orchestrator.log | jq 'select(.level == "ERROR")'

# Recent audit events
tail -n 50 /tmp/madrox_logs/audit/audit_$(date +%Y%m%d).jsonl

# Instance details (if applicable)
cat /tmp/madrox_logs/instances/{instance_id}/instance.log
```

**Reproduction Steps:**
1. Exact commands/code used
2. Expected behavior
3. Actual behavior
4. Error messages

### Support Channels

- **GitHub Issues**: https://github.com/yourusername/madrox/issues
- **Documentation**: See `docs/` directory for comprehensive guides
- **Examples**: Review `tests/integration_demo.py` for working patterns

### Additional Resources

- [Design Documentation](DESIGN.md) - Architecture and system design
- [API Reference](API_ENDPOINTS.md) - HTTP REST API details
- [Logging Guide](LOGGING.md) - Complete logging system documentation
- [MCP Configuration](MCP_SERVER_CONFIGURATION.md) - Custom MCP server setup
- [Stress Testing](STRESS_TESTING.md) - Production validation scenarios
- [Interrupt Feature](INTERRUPT_FEATURE.md) - Task control documentation

---

**For urgent production issues**, enable debug logging and review the full audit trail to understand the sequence of events leading to the problem.
