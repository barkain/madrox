# API Reference

Complete technical reference for Madrox MCP tools, HTTP endpoints, configuration, and return types.

---

## Table of Contents

- [MCP Tools](#mcp-tools)
  - [Instance Management](#instance-management)
  - [Communication](#communication)
  - [Status & Monitoring](#status--monitoring)
  - [Coordination](#coordination)
  - [Bidirectional Messaging](#bidirectional-messaging)
- [HTTP REST API](#http-rest-api)
  - [Network Hierarchy](#network-hierarchy)
  - [Log Streaming](#log-streaming)
- [Configuration](#configuration)
  - [Server Configuration](#server-configuration)
  - [Instance Configuration](#instance-configuration)
  - [MCP Server Configuration](#mcp-server-configuration)
  - [Environment Variables](#environment-variables)
- [Return Types](#return-types)
  - [Instance Objects](#instance-objects)
  - [Response Formats](#response-formats)
  - [Error Responses](#error-responses)

---

## MCP Tools

Madrox provides MCP (Model Context Protocol) tools for orchestrating multi-agent systems. These tools are available through both HTTP and stdio transports.

### Instance Management

#### spawn_claude

Spawn a new Claude instance with specific role and configuration.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | Yes | - | Human-readable name for the instance |
| `role` | string | No | `"general"` | Predefined role (see [Instance Roles](#instance-roles)) |
| `system_prompt` | string | No | `null` | Custom system prompt (overrides role defaults) |
| `model` | string | No | CLI default | Claude model to use (e.g., `claude-4-sonnet-20250514`) |
| `bypass_isolation` | boolean | No | `false` | Allow full filesystem access (disables workspace isolation) |
| `enable_madrox` | boolean | No | `true` | Enable Madrox MCP server (allows spawning sub-instances) |
| `parent_instance_id` | string | No | `null` | Parent instance ID (for hierarchical networks) |
| `mcp_servers` | object | No | `{}` | Additional MCP servers to configure (see [MCP Server Configuration](#mcp-server-configuration)) |

**⚠️ Important - Automatic Enforcement:**

When `parent_instance_id` is provided (supervised instances), the system **automatically enforces `enable_madrox=true`** regardless of the provided value. This is required for bidirectional communication between supervisor and workers.

```python
# If you try this:
spawn_claude(
    name="worker",
    parent_instance_id="supervisor-123",
    enable_madrox=False  # Will be overridden
)

# System automatically changes it to:
# enable_madrox=True

# With warning:
# "Forcing enable_madrox=True for supervised instance 'worker' with parent
#  supervisor-123. Workers must have madrox enabled for bidirectional communication."
```

**Why:** Supervised workers need madrox MCP server to use `reply_to_caller()` and receive messages from their supervisor. See [Coordination Patterns](FEATURES.md#coordination-patterns) for details on independent vs supervised instances.

**Returns:**

```json
{
  "success": true,
  "instance_id": "abc123-456def-789ghi",
  "name": "data-analyst",
  "role": "data_analyst",
  "model": "claude-4-sonnet-20250514",
  "message": "Successfully spawned Claude instance 'data-analyst'"
}
```

**Example:**

```python
# Basic spawn
instance_id = await spawn_claude(
    name="security-auditor",
    role="security_analyst"
)

# Advanced spawn with MCP servers
instance_id = await spawn_claude(
    name="web-scraper",
    role="data_analyst",
    enable_madrox=True,
    mcp_servers={
        "playwright": {
            "transport": "stdio",
            "command": "npx",
            "args": ["@playwright/mcp@latest"]
        }
    }
)
```

**Instance Roles:**

Available roles with predefined system prompts:

- `general` - General-purpose assistant
- `architect` - System design and architecture
- `backend_developer` - Backend development
- `frontend_developer` - Frontend development
- `full_stack_developer` - Full-stack development
- `devops_engineer` - DevOps and infrastructure
- `data_analyst` - Data analysis and visualization
- `security_analyst` - Security auditing and testing
- `qa_engineer` - Quality assurance and testing
- `technical_writer` - Documentation and writing

---

#### spawn_multiple_instances

Spawn multiple Claude instances in parallel for improved performance.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instances` | array | Yes | List of instance configurations (each with same parameters as `spawn_claude`) |

**Returns:**

```json
{
  "success": true,
  "total_requested": 3,
  "spawned": 3,
  "failed": 0,
  "instances": [
    {
      "success": true,
      "instance_id": "abc123",
      "name": "worker-1",
      "role": "backend_developer"
    },
    {
      "success": true,
      "instance_id": "def456",
      "name": "worker-2",
      "role": "frontend_developer"
    },
    {
      "success": true,
      "instance_id": "ghi789",
      "name": "worker-3",
      "role": "qa_engineer"
    }
  ],
  "errors": null,
  "message": "Successfully spawned 3/3 instances"
}
```

**Example:**

```python
result = await spawn_multiple_instances(
    instances=[
        {"name": "backend-1", "role": "backend_developer"},
        {"name": "frontend-1", "role": "frontend_developer"},
        {"name": "tester-1", "role": "qa_engineer"}
    ]
)
```

---

#### spawn_codex_instance

Spawn a new OpenAI Codex instance (similar to `spawn_claude` but for Codex CLI).

**Parameters:**

Same as `spawn_claude`, with Codex-specific considerations:
- Uses `codex` CLI instead of `claude` CLI
- Codex only supports stdio transport for MCP
- Different model options (GPT-4, O1, etc.)

**Returns:**

Same format as `spawn_claude`.

---

#### terminate_instance

Terminate a Claude instance and clean up resources.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `instance_id` | string | Yes | - | ID of the instance to terminate |
| `force` | boolean | No | `false` | Force termination even if busy |

**Returns:**

```json
{
  "success": true,
  "instance_id": "abc123-456def-789ghi",
  "message": "Successfully terminated instance abc123-456def-789ghi"
}
```

**Behavior:**

- **Cascade termination**: Automatically terminates all child instances
- **Cleanup**: Removes tmux session and cleans up workspace
- **Logging**: Records termination in audit trail
- **Force mode**: Kills tmux session immediately without graceful shutdown

**Example:**

```python
# Graceful termination
success = await terminate_instance(instance_id="abc123")

# Force termination
success = await terminate_instance(instance_id="abc123", force=True)
```

---

#### terminate_multiple_instances

Terminate multiple Claude instances in parallel.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `instance_ids` | array | Yes | - | List of instance IDs to terminate |
| `force` | boolean | No | `false` | Force termination for all instances |

**Returns:**

```json
{
  "success": true,
  "total_requested": 3,
  "terminated": 3,
  "failed": 0,
  "terminated_instances": ["abc123", "def456", "ghi789"],
  "errors": null,
  "message": "Successfully terminated 3/3 instances"
}
```

---

#### interrupt_instance

Interrupt a running task without terminating the instance. Preserves context and conversation history.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instance_id` | string | Yes | ID of the instance to interrupt |

**Returns:**

```json
{
  "success": true,
  "instance_id": "abc123-456def-789ghi",
  "message": "Task interrupted successfully",
  "timestamp": "2025-10-07T12:34:56.789Z"
}
```

**Technical Details:**

- Sends **Escape key** signal to tmux pane
- Claude displays: `"⎿ Interrupted · What should Claude do instead?"`
- Codex displays: `"Esc edit prev"`
- Context is fully preserved
- Instance remains active and ready for new tasks

**Use Cases:**

- Redirect long-running tasks
- Stop expensive operations
- Change priorities mid-execution
- Debug intermediate state

**Example:**

```python
# Start a long-running task
send_to_instance(instance_id, "count to 1000 slowly")

# Interrupt after a few seconds
await interrupt_instance(instance_id)

# Give new task
send_to_instance(instance_id, "Instead, summarize this data")
```

---

#### interrupt_multiple_instances

Interrupt multiple instances in parallel.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instance_ids` | array | Yes | List of instance IDs to interrupt |

**Returns:**

```json
{
  "success": true,
  "interrupted_instances": ["abc123", "def456"],
  "errors": []
}
```

---

### Communication

#### send_to_instance

Send a message to a specific Claude instance and optionally wait for response.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `instance_id` | string | Yes | - | Target instance ID |
| `message` | string | Yes | - | Message content to send |
| `wait_for_response` | boolean | No | `true` | Wait for instance to respond |
| `timeout_seconds` | integer | No | `30` | Response timeout in seconds |

**Returns:**

**With response:**
```json
{
  "success": true,
  "instance_id": "abc123",
  "response": "Analysis complete: found 3 security vulnerabilities...",
  "message": "Message sent and response received"
}
```

**Without response:**
```json
{
  "success": true,
  "instance_id": "abc123",
  "message": "Message sent (no response requested)"
}
```

**Behavior:**

- Messages are prefixed with `[MSG:message_id]` for correlation
- Response waits use asyncio queues (in-memory, ephemeral)
- Timeout returns control to caller without error
- Messages are logged in communication logs

**Example:**

```python
# Send and wait for response
response = await send_to_instance(
    instance_id="analyst-1",
    message="Analyze this dataset and provide summary statistics",
    wait_for_response=True,
    timeout_seconds=60
)

# Fire and forget
await send_to_instance(
    instance_id="logger-1",
    message="Log this event",
    wait_for_response=False
)
```

---

#### reply_to_caller

**Available to supervised instances**. Reply back to the parent/coordinator that sent a message. **This is MANDATORY for all supervised instances** (instances with `parent_instance_id`).

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instance_id` | string | Yes | **YOUR OWN instance ID** (the responder's ID, NOT the correlation_id) |
| `reply_message` | string | Yes | Reply content |
| `correlation_id` | string | No | Message ID from incoming message (strongly recommended for tracking) |

> **⚠️ CRITICAL - Common Mistake**
>
> **`instance_id` must be YOUR OWN instance ID, NOT the correlation_id from the message!**
>
> When you receive a message like `[MSG:abc-123-def] Hello child-1`, you must use:
> - ✅ **`instance_id`**: Your actual instance ID (e.g., `79b048a8-46c7-43dc-846a-1266aead9e61`)
> - ✅ **`correlation_id`**: The message ID from `[MSG:...]` (e.g., `abc-123-def`)
>
> **DON'T DO THIS** ❌:
> ```python
> reply_to_caller(
>     instance_id="abc-123-def",  # WRONG! This is the correlation_id
>     reply_message="My response",
>     correlation_id="abc-123-def"
> )
> # Error: "Instance abc-123-def not found"
> ```
>
> **DO THIS** ✅:
> ```python
> reply_to_caller(
>     instance_id="79b048a8-46c7-43dc-846a-1266aead9e61",  # Your actual instance ID
>     reply_message="My response",
>     correlation_id="abc-123-def"  # Message ID from [MSG:...]
> )
> # Success: Reply delivered to parent
> ```

**Returns:**

```json
{
  "success": true,
  "delivered_to": "parent-instance-id",
  "correlation_id": "2ea0e30e-7ec3-4537-8f38-c059018a3f95",
  "timestamp": "2025-10-11T16:10:31.045425Z"
}
```

**Behavior:**

1. **Response Queue Routing**: Reply is queued in parent's `response_queue` (asyncio.Queue)
2. **Instant Delivery**: Parent's `send_to_instance()` receives reply immediately from queue
3. **Message Correlation**: Correlation ID links reply to original request in `message_registry`
4. **Communication Logging**: Logged as `bidirectional_reply_received` event
5. **Automatic Target**: Routes to `parent_instance_id` or coordinator if no parent

**Why Mandatory?**

Supervised instances receive explicit instructions in their system prompt:

```
BIDIRECTIONAL MESSAGING PROTOCOL (REQUIRED):
When you receive messages formatted as [MSG:correlation-id] content,
you MUST respond using the reply_to_caller tool.
```

**Benefits:**
- ⚡ 10-100x faster than tmux pane polling
- ✅ Guaranteed delivery with correlation tracking
- 📊 Structured communication audit trail
- 🔗 Supports multi-level hierarchical networks

**Implementation Details:**

**Message Envelope System:**

Every message sent via `send_to_instance` creates a `MessageEnvelope`:

```python
@dataclass
class MessageEnvelope:
    message_id: str                  # UUID for correlation
    sender_id: str                   # Parent/coordinator ID
    recipient_id: str                # Child instance ID
    content: str                     # Original message
    sent_at: datetime               # Timestamp
    delivered_at: datetime | None   # When received by child
    replied_at: datetime | None     # When child used reply_to_caller
    reply_content: str | None       # Reply message
    status: str                      # 'sent' | 'delivered' | 'replied' | 'timeout'
```

**Response Queue Lifecycle:**

```python
# Response queues created at spawn time (not send time!)
self.response_queues: dict[str, asyncio.Queue] = {}

# When instance spawns:
async def spawn_instance(...):
    # Create response queue immediately
    self.response_queues[instance_id] = asyncio.Queue()
    # ✅ Instance can now receive replies even before sending messages

# When parent sends message:
async def send_to_instance(instance_id, message, wait_for_response=True):
    message_id = str(uuid.uuid4())
    formatted_message = f"[MSG:{message_id}] {message}"

    if wait_for_response:
        # Wait on parent's response queue (already exists!)
        reply = await asyncio.wait_for(
            self.response_queues[parent_id].get(),
            timeout=timeout_seconds
        )
        return reply["reply_message"]

# When child uses reply_to_caller:
async def handle_reply_to_caller(instance_id, reply_message, correlation_id):
    parent_id = instance["parent_instance_id"]

    # Queue reply in parent's response queue
    await self.response_queues[parent_id].put({
        "sender_id": instance_id,
        "reply_message": reply_message,
        "correlation_id": correlation_id,
        "timestamp": datetime.now().isoformat()
    })

    # Parent's send_to_instance() receives it immediately ✅
```

**Key Fix (October 2025):**

Before: Response queues created in `send_message()` → parent couldn't receive first reply from child

After: Response queues created in `spawn_instance()` → parent can receive replies immediately

**Example (from child instance perspective):**

```python
# Child receives message like:
# [MSG:2ea0e30e-7ec3-4537-8f38-c059018a3f95] Analyze this code for vulnerabilities

# Child MUST reply using reply_to_caller (mandatory):
reply_to_caller(
    instance_id="child-abc123",
    reply_message="Security analysis complete:\n- SQL injection risk in line 42\n- XSS vulnerability in template rendering",
    correlation_id="2ea0e30e-7ec3-4537-8f38-c059018a3f95"  # Extracted from [MSG:...]
)

# Parent's send_to_instance() returns immediately with the reply ✅
```

**Example (from parent instance perspective):**

```python
# Parent sends message and waits
response = await send_to_instance(
    instance_id="child-abc123",
    message="Analyze this code for vulnerabilities",
    wait_for_response=True,
    timeout_seconds=60
)

# When child uses reply_to_caller, response contains:
# "Security analysis complete:\n- SQL injection risk..."

# Correlation is tracked automatically via message_registry
```

**Communication Events Logged:**

```json
{
  "timestamp": "2025-10-11T19:10:31.045425",
  "event_type": "bidirectional_reply_received",
  "message": "Received bidirectional response (740 chars, 10.59s)",
  "message_id": "2ea0e30e-7ec3-4537-8f38-c059018a3f95",
  "direction": "inbound",
  "content": "Security analysis complete..."
}
```

---

#### get_pending_replies

**Available to parent/supervisor instances**. Poll for queued replies from children.

When children use `reply_to_caller`, their replies are queued in the parent's response queue. This tool allows the parent to actively poll for these queued replies.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `instance_id` | string | Yes | - | Your instance ID (to check your inbox) |
| `wait_timeout` | integer | No | `0` | Seconds to wait for at least one reply (0 = non-blocking) |

**Returns:**

**Non-blocking mode (wait_timeout=0):**
```json
[
  {
    "sender_id": "child-abc123",
    "reply_message": "Task completed successfully",
    "correlation_id": "2ea0e30e-7ec3-4537-8f38-c059018a3f95",
    "timestamp": "2025-10-12T15:30:45.123Z"
  },
  {
    "sender_id": "child-def456",
    "reply_message": "Analysis complete",
    "correlation_id": "8f3a5c2d-9b1e-4f67-a8d2-1c4e6b9f0a3d",
    "timestamp": "2025-10-12T15:30:46.456Z"
  }
]
```

**Blocking mode (wait_timeout > 0):**
Waits up to `wait_timeout` seconds for at least one reply, then returns all available replies (including any that arrived during the wait).

**When to Use:**

This tool is essential when supervisors need to poll for responses from children that used `reply_to_caller`. Use cases:

1. **After Broadcasting**: Poll for replies after using `broadcast_to_children`
2. **Periodic Status Checks**: Regularly poll to collect progress updates
3. **Batch Processing**: Wait for multiple children to complete before proceeding
4. **Coordination**: Gather responses from parallel workers

**Example (Non-blocking Polling):**

```python
# Supervisor broadcasts task to all children
await broadcast_to_children(
    parent_id="supervisor-abc123",
    message="Analyze your assigned dataset partition"
)

# Poll periodically for replies
import time
all_replies = []
timeout = 60  # 60 second total timeout
start_time = time.time()

while time.time() - start_time < timeout:
    # Non-blocking poll
    new_replies = await get_pending_replies(
        instance_id="supervisor-abc123",
        wait_timeout=0
    )

    all_replies.extend(new_replies)

    # Check if all children responded
    if len(all_replies) >= expected_child_count:
        break

    # Wait before next poll
    await asyncio.sleep(2)

# Process all collected replies
for reply in all_replies:
    print(f"Child {reply['sender_id']}: {reply['reply_message']}")
```

**Example (Blocking with Timeout):**

```python
# Wait up to 30 seconds for first reply, then grab all available
replies = await get_pending_replies(
    instance_id="supervisor-abc123",
    wait_timeout=30  # Block up to 30 seconds
)

if not replies:
    print("No replies received within timeout")
else:
    print(f"Received {len(replies)} replies")
    for reply in replies:
        print(f"  - {reply['sender_id']}: {reply['reply_message'][:50]}...")
```

**Implementation Notes:**

- Replies are drained from an `asyncio.Queue` in the parent's `response_queues` dictionary
- Non-blocking mode (`wait_timeout=0`) returns immediately with whatever is queued
- Blocking mode (`wait_timeout > 0`) waits for first reply, then drains remaining queue
- Returns empty list `[]` if no replies available (non-blocking) or timeout expires (blocking)
- Each reply includes `sender_id`, `reply_message`, `correlation_id`, and `timestamp`

---

#### get_instance_output

Get recent output from a Claude instance.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `instance_id` | string | Yes | - | Instance ID |
| `limit` | integer | No | `100` | Maximum number of messages to retrieve |
| `since` | string | No | `null` | ISO timestamp to filter messages from |

**Returns:**

```json
{
  "success": true,
  "instance_id": "abc123",
  "output": [
    "Analysis started...",
    "Processing file 1 of 10...",
    "Found potential issue in module X..."
  ],
  "count": 3,
  "message": "Retrieved 3 output messages"
}
```

**Example:**

```python
# Get recent output
output = await get_instance_output(
    instance_id="worker-1",
    limit=50
)

# Get output since specific time
output = await get_instance_output(
    instance_id="worker-1",
    since="2025-10-07T12:00:00Z"
)
```

---

#### broadcast_to_children

**Available to parent instances**. Send message to all child instances.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `parent_id` | string | Yes | Parent instance ID |
| `message` | string | Yes | Message to broadcast |

**Returns:**

```json
{
  "success": true,
  "parent_id": "parent-abc",
  "children_count": 3,
  "message": "Broadcast sent to 3 children"
}
```

---

#### get_children

Get list of child instances for a parent.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `parent_id` | string | Yes | Parent instance ID |

**Returns:**

```json
{
  "parent_id": "parent-abc",
  "children": [
    {
      "id": "child-1",
      "name": "worker-1",
      "role": "backend_developer",
      "state": "running"
    },
    {
      "id": "child-2",
      "name": "worker-2",
      "role": "qa_engineer",
      "state": "idle"
    }
  ],
  "count": 2
}
```

---

### Status & Monitoring

#### get_instance_status

Get status for a single instance or all instances.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instance_id` | string | No | Optional instance ID (omit for all instances) |

**Returns:**

**Single instance:**
```json
{
  "success": true,
  "status": {
    "id": "abc123",
    "name": "data-analyst",
    "role": "data_analyst",
    "state": "running",
    "parent_id": null,
    "children": [],
    "model": "claude-4-sonnet-20250514",
    "created_at": "2025-10-07T12:00:00Z",
    "total_tokens": 15234,
    "total_cost": 0.45,
    "request_count": 12
  }
}
```

**All instances:**
```json
{
  "success": true,
  "status": {
    "total_instances": 5,
    "by_state": {
      "running": 3,
      "idle": 2,
      "terminated": 0
    },
    "instances": [...]
  }
}
```

---

### Coordination

#### coordinate_instances

Coordinate multiple instances for a complex task.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `coordinator_id` | string | Yes | - | Coordinating instance ID |
| `participant_ids` | array | Yes | - | Participant instance IDs |
| `task_description` | string | Yes | - | Task description |
| `coordination_type` | string | No | `"sequential"` | How to coordinate: `sequential`, `parallel`, `consensus` |

**Returns:**

```json
{
  "success": true,
  "task_id": "task-xyz789",
  "coordinator_id": "coord-abc",
  "participant_ids": ["worker-1", "worker-2", "worker-3"],
  "coordination_type": "parallel",
  "message": "Started coordination task task-xyz789"
}
```

**Coordination Types:**

- **sequential**: Tasks execute one after another
- **parallel**: All tasks execute simultaneously
- **consensus**: Gather responses from all instances and synthesize

**Example:**

```python
task_id = await coordinate_instances(
    coordinator_id="main-coordinator",
    participant_ids=["analyst-1", "analyst-2", "analyst-3"],
    task_description="Review this codebase for security issues",
    coordination_type="parallel"
)
```

---

### Bidirectional Messaging

Madrox implements lightweight bidirectional messaging using in-memory asyncio primitives.

**Key Features:**

- **In-memory only**: Uses `asyncio.Queue` for runtime routing
- **No database**: Zero external dependencies
- **Ephemeral**: Message tracking lives only during server runtime
- **Fast**: Direct queue operations, no DB round-trips
- **Message correlation**: Track request-response pairs with message IDs

**Message Flow:**

```
1. Parent sends message with unique message_id
   └─> Message format: [MSG:abc123] Your task here

2. Message delivered to child instance pane

3. Child uses reply_to_caller() to respond
   └─> Routes through asyncio.Queue

4. Parent receives response via send_to_instance() return
   └─> Response includes correlation_id
```

**Tools Involved:**

- `send_to_instance` (with `wait_for_response=True`)
- `reply_to_caller` (child instances only)
- `get_pending_replies` (parent instances poll for queued replies)
- `broadcast_to_children`
- `get_children`

---

## HTTP REST API

Madrox provides HTTP REST endpoints for direct integration, monitoring, and debugging.

**Base URL:** `http://localhost:8001`

### Network Hierarchy

#### GET /network/hierarchy

Get complete network topology showing all instances and parent-child relationships.

**Response:**

```json
{
  "total_instances": 3,
  "root_instances": [
    {
      "id": "48cbbfda-f75a-43b2-9bc0-a1ff173b1dee",
      "name": "parent-coordinator",
      "type": "claude",
      "role": "architect",
      "state": "running",
      "parent_id": null,
      "children": [
        {
          "id": "1e65b11a-807f-40a0-a226-c87af93cdd70",
          "name": "child-worker-1",
          "type": "claude",
          "role": "security_analyst",
          "state": "running",
          "parent_id": "48cbbfda-f75a-43b2-9bc0-a1ff173b1dee",
          "children": [],
          "created_at": "2025-10-03T10:59:47.198432+00:00",
          "total_tokens": 12450,
          "total_cost": 0.37,
          "request_count": 8
        }
      ],
      "created_at": "2025-10-03T10:59:25.422151+00:00",
      "total_tokens": 23890,
      "total_cost": 0.72,
      "request_count": 15
    }
  ],
  "all_instances": [...]
}
```

**Fields:**

- `total_instances`: Total number of active instances
- `root_instances`: Instances with no parent (top-level coordinators)
- `all_instances`: Flat array of all instances

**Example:**

```bash
curl "http://localhost:8001/network/hierarchy" | jq
```

---

### Log Streaming

#### GET /logs/audit

Get audit trail logs from the orchestrator.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | `100` | Maximum number of log entries |
| `since` | string | `null` | ISO timestamp to filter logs from |

**Response:**

```json
{
  "logs": [
    {
      "timestamp": "2025-10-03T13:45:59.868017",
      "level": "INFO",
      "event": "instance_spawn",
      "instance_id": "9e240be1-3989-47a1-b3a0-59a616d7923f",
      "details": {
        "instance_name": "logging-test",
        "role": "general"
      }
    }
  ],
  "total": 2,
  "file": "/tmp/madrox_logs/audit/audit_20251003.jsonl"
}
```

**Example:**

```bash
curl "http://localhost:8001/logs/audit?limit=10"
```

---

#### GET /logs/instances/{instance_id}

Get instance-specific logs (human-readable format).

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instance_id` | string | Yes | Instance UUID |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | `100` | Maximum number of log entries |
| `since` | string | `null` | ISO timestamp filter |

**Response:**

```json
{
  "logs": [
    "2025-10-03 13:45:59 - INFO - Instance created with role: general",
    "2025-10-03 13:46:11 - INFO - Instance initialization completed"
  ],
  "total": 3,
  "instance_id": "9e240be1-3989-47a1-b3a0-59a616d7923f",
  "file": "/tmp/madrox_logs/instances/9e240be1.../instance.log"
}
```

**Example:**

```bash
curl "http://localhost:8001/logs/instances/9e240be1-3989-47a1-b3a0-59a616d7923f?limit=50"
```

---

#### GET /logs/communication/{instance_id}

Get communication logs for instance (structured JSON format).

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instance_id` | string | Yes | Instance UUID |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | `100` | Maximum number of log entries |
| `since` | string | `null` | ISO timestamp filter |

**Response:**

```json
{
  "logs": [
    {
      "timestamp": "2025-10-03T13:45:59.867838",
      "event_type": "message_received",
      "message": "Analyze this code for vulnerabilities",
      "correlation_id": "msg-abc123"
    }
  ],
  "total": 3,
  "instance_id": "9e240be1-3989-47a1-b3a0-59a616d7923f",
  "file": "/tmp/madrox_logs/instances/9e240be1.../communication.jsonl"
}
```

**Example:**

```bash
curl "http://localhost:8001/logs/communication/9e240be1-3989-47a1-b3a0-59a616d7923f"
```

---

### Error Responses

**404 Not Found:**
```json
{
  "detail": "No logs found for instance {instance_id}"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Error reading log file: {error_message}"
}
```

---

## Configuration

### Server Configuration

Configure the Madrox orchestrator server.

**Environment Variables:**

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ANTHROPIC_API_KEY` | string | **Required** | Anthropic API key for Claude instances |
| `ORCHESTRATOR_HOST` | string | `localhost` | Server host |
| `ORCHESTRATOR_PORT` | integer | `8001` | Server port |
| `MAX_INSTANCES` | integer | `10` | Maximum concurrent instances |
| `WORKSPACE_DIR` | string | `/tmp/claude_orchestrator` | Base directory for instance workspaces |
| `LOG_DIR` | string | `/tmp/madrox_logs` | Log directory |
| `LOG_LEVEL` | string | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

**Example:**

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export ORCHESTRATOR_PORT=8001
export MAX_INSTANCES=20
export LOG_LEVEL=DEBUG

python run_orchestrator.py
```

---

### Instance Configuration

Configure individual instances when spawning.

**Workspace Isolation:**

By default, instances are isolated to their own workspace directory:

```
/tmp/claude_orchestrator/
  ├── abc123-456def-789ghi/  # Instance workspace
  │   ├── .madrox_instance_id
  │   └── [user files]
  └── def456-789ghi-abc123/  # Another instance
```

**Bypass Isolation:**

Set `bypass_isolation=true` to allow full filesystem access:

```python
instance_id = await spawn_claude(
    name="admin-tool",
    role="devops_engineer",
    bypass_isolation=True  # Can access entire filesystem
)
```

---

### MCP Server Configuration

Configure additional MCP servers for child instances.

**Configuration Format:**

```python
mcp_servers = {
    "server_name": {
        "transport": "http" | "stdio",  # Optional, auto-detected
        "url": "http://localhost:PORT/mcp",  # For HTTP transport
        # OR
        "command": "npx",  # For stdio transport
        "args": ["-y", "@modelcontextprotocol/server-filesystem"]
    }
}
```

**Quick Start: Prebuilt Configs**

Madrox includes prebuilt MCP configurations:

```python
from orchestrator.mcp_loader import get_mcp_servers

# Load multiple prebuilt configs
mcp_servers = get_mcp_servers("playwright", "github", "memory")

instance_id = await spawn_claude(
    name="agent",
    role="general",
    enable_madrox=True,
    mcp_servers=mcp_servers
)
```

**Available Prebuilt Configs:**

- `playwright` - Browser automation (headless)
- `puppeteer` - Alternative browser automation
- `github` - GitHub API access
- `filesystem` - Filesystem operations
- `sqlite` - SQLite database access
- `postgres` - PostgreSQL database access
- `brave-search` - Web search via Brave
- `google-drive` - Google Drive integration
- `slack` - Slack messaging
- `memory` - Persistent memory/notes

**Configuration Merging:**

⚠️ **Important**: Child instances inherit the user's global MCP configuration and add any servers specified via `mcp_servers` parameter. Complete MCP isolation is not currently possible due to Claude CLI's configuration merge behavior.

- `enable_madrox=False` → Instance will NOT have Madrox MCP, but WILL have user's global MCP servers
- `enable_madrox=True` → Instance will have Madrox MCP + user's global MCP servers
- `mcp_servers={...}` → Additional servers are added to global + Madrox (if enabled)

**Automatic Madrox Addition:**

If `enable_madrox=True` and `"madrox"` is not explicitly in `mcp_servers`, Madrox is automatically added:

```python
if enable_madrox and "madrox" not in mcp_servers:
    mcp_servers["madrox"] = {
        "transport": "http",
        "url": f"http://localhost:{server_port}/mcp"
    }
```

**Examples:**

**Browser Automation:**
```python
spawn_claude(
    name="web-scraper",
    role="data_analyst",
    enable_madrox=True,
    mcp_servers={
        "playwright": {
            "command": "npx",
            "args": ["@playwright/mcp@latest"]
        }
    }
)
```

**Multiple MCP Servers:**
```python
spawn_claude(
    name="data-processor",
    role="data_analyst",
    enable_madrox=True,
    mcp_servers={
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
        },
        "database": {
            "transport": "http",
            "url": "http://localhost:5432/mcp"
        }
    }
)
```

**Scope:**

All MCP servers are added with `--scope local`, meaning they only affect the current tmux session and don't pollute the user's global Claude configuration.

---

### Environment Variables

Full list of environment variables supported by Madrox.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ANTHROPIC_API_KEY` | string | **Required** | Anthropic API key |
| `OPENAI_API_KEY` | string | Optional | OpenAI API key (for Codex instances) |
| `ORCHESTRATOR_HOST` | string | `localhost` | HTTP server host |
| `ORCHESTRATOR_PORT` | integer | `8001` | HTTP server port |
| `MAX_INSTANCES` | integer | `10` | Maximum concurrent instances |
| `WORKSPACE_DIR` | string | `/tmp/claude_orchestrator` | Instance workspace base directory |
| `LOG_DIR` | string | `/tmp/madrox_logs` | Log directory |
| `LOG_LEVEL` | string | `INFO` | Logging level |

---

## Return Types

### Instance Objects

Standard instance object structure returned by various endpoints.

```typescript
{
  id: string;              // UUID
  name: string;            // Human-readable name
  type: "claude" | "codex"; // Instance type
  role: string;            // Assigned role
  state: "running" | "idle" | "busy" | "terminated"; // Current state
  parent_id: string | null; // Parent instance ID
  children: Instance[];    // Child instances (recursive)
  model: string;           // Model identifier
  created_at: string;      // ISO 8601 timestamp
  terminated_at?: string;  // ISO 8601 timestamp (if terminated)
  total_tokens: number;    // Total tokens used
  total_cost: number;      // Total cost in USD
  request_count: number;   // Number of requests
  workspace_dir: string;   // Workspace directory path
  tmux_session: string;    // Tmux session name
}
```

---

### Response Formats

#### Success Response

```json
{
  "success": true,
  "data": { /* response data */ },
  "message": "Operation completed successfully"
}
```

#### Error Response

```json
{
  "success": false,
  "error": "Error description",
  "message": "User-friendly error message"
}
```

#### Timeout Response

```json
{
  "success": true,
  "status": "timeout",
  "message": "Operation timed out",
  "timeout_seconds": 30
}
```

---

### Error Responses

Common error responses across all endpoints.

**400 Bad Request:**
```json
{
  "success": false,
  "error": "Missing required parameter: instance_id",
  "message": "Invalid request parameters"
}
```

**404 Not Found:**
```json
{
  "success": false,
  "error": "Instance not found: abc123",
  "message": "The requested instance does not exist"
}
```

**500 Internal Server Error:**
```json
{
  "success": false,
  "error": "Failed to spawn instance: tmux session creation failed",
  "message": "Internal server error occurred"
}
```

**503 Service Unavailable:**
```json
{
  "success": false,
  "error": "Maximum instances limit reached (10/10)",
  "message": "Cannot spawn new instance: service at capacity"
}
```

---

## Transport Architecture

Madrox supports dual transport modes with unified instance registry.

### Transports

| Transport | Protocol | Use Cases | Role |
|-----------|----------|-----------|------|
| **HTTP** | `http://localhost:8001` | Claude Code CLI, Claude Desktop, REST APIs | **Primary** - Single source of truth |
| **Stdio** | JSON-RPC over stdin/stdout | Codex CLI (required), Claude Desktop (alternative) | **Proxy** - Forwards to HTTP server |

### Unified Registry

Both transports share the same instance registry:

```
┌─────────────────────────────────────┐
│   HTTP Server (:8001)               │
│   Single Source of Truth            │
│   ┌───────────────────────────────┐ │
│   │   Instance Manager            │ │
│   │   - All instances tracked     │ │
│   │   - Parent-child relationships│ │
│   │   - Resource tracking         │ │
│   └───────────────────────────────┘ │
└─────────────────────────────────────┘
       ▲                       ▲
       │                       │
  HTTP requests          Proxied requests
       │                       │
┌──────┴──────┐       ┌────────┴────────┐
│ Claude Code │       │  Stdio Server   │
│ (HTTP)      │       │  (proxies HTTP) │
└─────────────┘       └─────────────────┘
```

### Configuration Examples

**HTTP Transport (Claude Code CLI):**
```bash
claude mcp add madrox http://localhost:8001/mcp --transport http
```

**Stdio Transport (Codex - automatic):**
```python
# Codex instances spawned with enable_madrox=true
# automatically connect to stdio server
spawn_codex_instance(name="codex-worker", enable_madrox=True)
```

---

## See Also

- [DESIGN.md](DESIGN.md) - System architecture and design philosophy
- [MCP_SERVER_CONFIGURATION.md](MCP_SERVER_CONFIGURATION.md) - Detailed MCP configuration guide
- [LOGGING.md](LOGGING.md) - Logging system documentation
- [INTERRUPT_FEATURE.md](INTERRUPT_FEATURE.md) - Task interruption capabilities
- [BIDIRECTIONAL_MESSAGING_DESIGN.md](BIDIRECTIONAL_MESSAGING_DESIGN.md) - Bidirectional communication design
