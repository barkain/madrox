# Debugging Madrox Networks

This document describes the debugging methodology and tools for Madrox multi-instance orchestration.

## Quick Debug Commands

### Check Network Activity
```bash
./watch_network_activity.sh
```

### Check Instance Status
```bash
./check_instance_activity.sh
```

### Run Full Network Test
```bash
python debug_network_test.py
```

## Common Issues

### Issue: Instances Remain Idle

**Symptom**: Instances spawn successfully but don't process tasks

**Root Cause**: Long messages may trigger paste detection in Claude Code UI

**Solution**: Already fixed in `src/orchestrator/tmux_instance_manager.py:330-335`
- Messages and Enter are sent as separate commands
- Works for all message lengths

**Verification**:
```bash
# Check tmux pane content
tmux capture-pane -t madrox-<instance-id> -p | tail -50

# Look for "[Pasted text]" indicators (should NOT appear)
```

### Issue: Monitor Script Errors

**Symptom**: TypeError about datetime operations

**Cause**: Instance `created_at` is stored as ISO string

**Solution**: Parse with `datetime.fromisoformat()` before comparisons

## Debug Methodology

### 1. Spawn Test Network
```python
from orchestrator.instance_manager import InstanceManager
from orchestrator.simple_models import OrchestratorConfig

config = OrchestratorConfig(
    workspace_base_dir="/tmp/madrox_debug",
    log_dir="/tmp/madrox_logs",
    log_level="DEBUG"
)

manager = InstanceManager(config.to_dict())

# Spawn instances...
```

### 2. Monitor Communication
```bash
# Watch communication logs
tail -f /tmp/madrox_logs/instances/<instance-id>/communication.jsonl

# Check message counts
wc -l /tmp/madrox_logs/instances/*/communication.jsonl
```

### 3. Inspect Tmux Sessions
```bash
# List all madrox sessions
tmux list-sessions | grep madrox

# Attach to instance
tmux attach -t madrox-<instance-id>

# Capture pane content
tmux capture-pane -t madrox-<instance-id> -p
```

### 4. Analyze Instance State
```bash
# Check instance logs
cat /tmp/madrox_logs/instances/<instance-id>/instance.log

# Check orchestrator log
tail -f /tmp/madrox_logs/orchestrator.log
```

## Test Infrastructure

### debug_network_test.py
Full hierarchical network test (1-2-4 topology):
- 1 main orchestrator
- 2 backend developers
- 4 testing specialists

Features:
- Real-time monitoring
- Activity tracking
- Communication logging
- Automatic cleanup

### watch_network_activity.sh
Real-time monitoring script showing:
- Message counts per instance
- Last activity timestamps
- Network-wide statistics

### check_instance_activity.sh
Quick status check showing:
- Active tmux sessions
- Recent log activity
- Instance states

## Log Locations

```
/tmp/madrox_logs/
├── orchestrator.log              # Main orchestrator log
├── audit/                        # Audit logs
└── instances/
    └── <instance-id>/
        ├── metadata.json         # Instance metadata
        ├── instance.log          # Instance-specific log
        └── communication.jsonl   # Message history
```

## Troubleshooting Tips

1. **Always check tmux pane content** - Visual inspection reveals paste buffer issues
2. **Monitor message counts** - Should increase as instances communicate
3. **Check for error patterns** - Look for repeated errors in logs
4. **Verify parent-child relationships** - Ensure hierarchy is correct
5. **Test message submission manually** - Attach to tmux and try sending messages

## Reference

See `FINDINGS.md` for detailed analysis of the message submission issue and resolution.
