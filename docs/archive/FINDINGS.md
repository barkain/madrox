# Madrox Network Debug - Initial Findings

## Test Setup
- **Date**: 2025-10-03
- **Duration**: 2 minutes of observation
- **Topology**: 1 main → 2 backend → 4 testers (7 instances total)
- **Task**: Complex REST API implementation requiring >5 min

## Observed Behavior

### ✅ Successful Operations
1. **Instance Spawning**: All 7 instances spawned successfully in ~120 seconds
2. **Tmux Sessions**: All instances running in isolated tmux sessions
3. **Logging**: Communication logs being written correctly
4. **Task Assignment**: Task successfully sent to main orchestrator

### ⚠️ Identified Issue: Instances Not Processing

**Symptom**: All instances remain idle after task assignment

**Evidence**:
```
Main orchestrator:  3 messages (created, initialized, task_sent)
Backend dev 1:      2 messages (created, initialized)  ← IDLE
Backend dev 2:      2 messages (created, initialized)  ← IDLE
Tester 1.1:         2 messages (created, initialized)  ← IDLE
Tester 1.2:         2 messages (created, initialized)  ← IDLE
Tester 2.1:         2 messages (created, initialized)  ← IDLE
Tester 2.2:         2 messages (created, initialized)  ← IDLE
```

**Timeline**:
- 22:29:07 - Task sent to main orchestrator
- 22:30:52 - Still no processing activity (1min 45s later)

## ROOT CAUSE IDENTIFIED ✅

### The Issue
**Long messages sent via tmux `send_keys(message, enter=True)` are treated as paste events by Claude Code UI and NOT automatically submitted.**

### Evidence
1. Tmux pane shows: `[Pasted text #1 +133 lines][Pasted text #2 +37 lines]`
2. Message IS in the paste buffer but waiting for user to press Enter
3. Claude instance is idle, waiting for submission

### Code Location
`src/orchestrator/tmux_instance_manager.py:337`
```python
else:
    pane.send_keys(message, enter=True)  # ← Doesn't work for long messages!
```

### Why It Fails
- Claude Code detects rapid input as paste event
- Paste events show preview but require manual Enter press
- `enter=True` parameter is part of the pasted text, not a separate Enter command

### Fix Required
Treat Claude instances like Codex - send message and Enter separately:
```python
pane.send_keys(message, enter=False)
pane.send_keys("", enter=True)  # Send Enter as separate command
```

## Next Debug Steps

1. **Check Claude CLI stdout/stderr** in tmux sessions
   ```bash
   tmux attach -t madrox-<instance-id>
   ```

2. **Verify MCP tool availability** in instances
   - Check if madrox tools are registered
   - Verify instances can see spawn/delegate tools

3. **Test manual message injection**
   - Directly send message to tmux pane
   - Observe if Claude processes it

4. **Check for errors in orchestrator logs**
   ```bash
   tail -f /tmp/madrox_logs/orchestrator.log
   ```

5. **Monitor tmux pane activity**
   - Check if tmux panes are receiving input
   - Verify output is being captured

## Code Locations

### Test Scripts
- `debug_network_test.py` - Main test orchestration
- `watch_network_activity.sh` - Real-time activity monitor
- `check_instance_activity.sh` - Instance status checker

### Logs
- `/tmp/madrox_logs/instances/<id>/communication.jsonl` - Message logs
- `/tmp/madrox_logs/instances/<id>/instance.log` - Instance logs
- `/tmp/madrox_logs/orchestrator.log` - Orchestrator log
- `debug_network_run.log` - Test execution log

## Configuration
```python
OrchestratorConfig(
    workspace_base_dir="/tmp/madrox_debug_network",
    log_dir="/tmp/madrox_logs",
    log_level="DEBUG",
    max_concurrent_instances=20
)
```

## Instance IDs Reference
```json
{
  "main": "8f09e67e-73dc-4850-8a6e-335b045dbee4",
  "backend_1": "a8aca09f-488c-40d4-a81a-88b8b57e9474",
  "backend_2": "09255de6-631f-4b5b-8048-b81f18267188",
  "tester_1_1": "9180f19a-4158-4a03-aebb-20d138a48c23",
  "tester_1_2": "3d763299-02c0-4483-abc0-55931feeed0c",
  "tester_2_1": "a7de6da9-4367-4ece-a79a-60cfe0129876",
  "tester_2_2": "ba2ffb27-80f8-48cc-b1a1-4fcd18b7a41d"
}
```

## Recommendations

1. **Immediate**: Attach to main orchestrator tmux session to see what's happening
2. **Short-term**: Add message consumption monitoring
3. **Medium-term**: Implement health checks for message processing
4. **Long-term**: Add timeout/retry mechanisms for stuck instances
