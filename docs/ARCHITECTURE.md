# Madrox Architecture

Comprehensive technical architecture documentation for the Madrox multi-agent orchestration system.

## Table of Contents

- [System Overview](#system-overview)
- [Core Components](#core-components)
  - [Orchestration Layer](#orchestration-layer)
  - [Communication Layer](#communication-layer)
  - [Storage Layer](#storage-layer)
- [Containerization](#containerization)
  - [Docker Architecture](#docker-architecture)
  - [Networking](#networking)
  - [Resource Management](#resource-management)
- [Design Decisions](#design-decisions)
  - [Key Choices](#key-choices)
  - [Trade-offs](#trade-offs)
- [Security Model](#security-model)
- [Scalability](#scalability)

---

## System Overview

Madrox is a Model Context Protocol (MCP) server that enables hierarchical multi-agent orchestration. It allows AI instances to spawn and manage networks of specialized Claude and Codex instances with parent-child relationships, bidirectional communication, and role-based specialization.

### High-Level Architecture

```mermaid
graph TB
    User[User / Client]

    subgraph "MCP Protocol Layer"
        HTTP[HTTP Server :8001<br/>FastAPI + Uvicorn]
        STDIO[Stdio Server<br/>JSON-RPC Proxy]
    end

    subgraph "Core Orchestration"
        Manager[Instance Manager<br/>TmuxInstanceManager]
        Health[Health Monitor]
        Lifecycle[Lifecycle Manager]
    end

    subgraph "Logging & Audit"
        Audit[Audit Logger<br/>JSONL Format]
        InstanceLogs[Instance Logs<br/>Per-Instance Files]
        Comms[Communication Logs<br/>Message Tracking]
    end

    subgraph "Storage Layer"
        DB[(SQLite Database<br/>Instance Metadata)]
        Workspaces[Instance Workspaces<br/>Isolated Directories]
        LogFiles[Log Files<br/>Rotating Logs]
    end

    subgraph "Instance Network"
        Claude1[Claude Instance<br/>Tmux Session]
        Claude2[Claude Instance<br/>Tmux Session]
        Codex1[Codex Instance<br/>Tmux Session]
    end

    User --> HTTP
    User --> STDIO

    HTTP --> Manager
    STDIO -.proxies all requests.-> HTTP

    Manager --> Health
    Manager --> Lifecycle
    Manager --> Audit
    Manager --> InstanceLogs
    Manager --> Comms

    Manager --> DB
    Manager --> Workspaces
    Manager --> LogFiles

    Manager --> Claude1
    Manager --> Claude2
    Manager --> Codex1

    Claude1 -.parent-child.-> Claude2
    Claude2 -.spawns.-> Codex1

    style HTTP fill:#cce5ff
    style STDIO fill:#fff3cd
    style Manager fill:#d4edda
    style Audit fill:#e8f5e9
    style User fill:#e1f5ff
```

### Core Principles

1. **Hierarchical Orchestration**: Instances can spawn child instances recursively (3+ levels deep)
2. **Multi-Model Support**: Orchestrate both Claude (Anthropic) and Codex (OpenAI) instances
3. **Bidirectional Communication**: Parents ↔ children communication with message correlation
4. **Workspace Isolation**: Each instance operates in its own isolated directory
5. **Natural Language Control**: Orchestration via MCP protocol - no direct code interaction required
6. **Production-Ready**: Comprehensive logging, health monitoring, resource limits, and error recovery

---

## Core Components

### Orchestration Layer

The orchestration layer manages the lifecycle of all AI instances and coordinates their interactions.

#### Instance Manager (`TmuxInstanceManager`)

**Responsibilities**:
- Spawn Claude and Codex instances in isolated tmux sessions
- Track parent-child relationships across hierarchical networks
- Route messages between instances
- Manage instance lifecycle (spawn, monitor, terminate)
- Enforce resource limits (tokens, cost, timeout)

**Key Methods**:
```python
async def spawn_instance(
    name: str,
    role: str,
    system_prompt: str | None = None,
    enable_madrox: bool = True,
    parent_instance_id: str | None = None,
    mcp_servers: dict | None = None,
    wait_for_ready: bool = True,
    max_total_tokens: int = 100000,
    max_cost: float = 10.0,
    timeout_minutes: int = 60
) -> str
```

**Instance Lifecycle**:
```
1. Create tmux session with unique ID
2. Configure MCP servers (dynamic tool loading)
3. Initialize instance with role-specific system prompt
4. Register in instance registry with metadata
5. Monitor health and resource usage
6. Handle termination and cleanup
```

#### Instance Registry

Centralized registry maintaining state for all instances:

```python
instances: dict[str, dict[str, Any]] = {
    "instance_id": {
        "id": "uuid",
        "name": "instance-name",
        "type": "claude" | "codex",
        "role": "architect" | "developer" | ...,
        "state": "spawning" | "idle" | "busy" | "terminated",
        "parent_instance_id": "uuid" | None,
        "created_at": datetime,
        "total_tokens_used": int,
        "total_cost": float,
        "request_count": int,
        "workspace_dir": Path,
        "tmux_session": str,
        "mcp_servers": dict
    }
}
```

#### Health Monitor

Automatic health checks with configurable intervals:

**Health Check Process**:
1. Verify tmux session alive
2. Check process liveness (psutil)
3. Validate resource limits (tokens, cost, timeout)
4. Detect and cleanup stuck instances
5. Log health events to audit trail

**Health Check Configuration**:
```python
health_check_interval: int = 60  # seconds
instance_timeout_minutes: int = 60
max_tokens_per_instance: int = 100000
max_total_cost: float = 100.0
```

### Communication Layer

The communication layer handles message passing and coordination across instances.

#### Dual Transport Architecture

Madrox supports two transport modes with a **unified instance registry**:

```
┌─────────────────────────────────────────────────┐
│         HTTP Server (:8001)                     │
│         Single Source of Truth                  │
│  ┌───────────────────────────────────────────┐  │
│  │   Instance Manager                        │  │
│  │   - All instances tracked here            │  │
│  │   - Parent-child relationships            │  │
│  │   - Resource tracking                     │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
         ▲                           ▲
         │                           │
         │                           │
    HTTP requests              Proxied requests
         │                           │
         │                           │
┌────────┴────────┐         ┌────────┴────────────┐
│  Claude Code    │         │  Stdio Server       │
│  (HTTP)         │         │  (proxies to HTTP)  │
│                 │         │                     │
│  Direct access  │         │  Codex CLI          │
└─────────────────┘         └─────────────────────┘
```

**Transport Comparison**:

| Feature | HTTP Transport | Stdio Transport |
|---------|----------------|-----------------|
| **Protocol** | HTTP/REST + SSE | JSON-RPC over stdin/stdout |
| **Use Cases** | Claude Code CLI, Claude Desktop, REST APIs | Codex CLI (required), Claude Desktop (alternative) |
| **Role** | Primary - Single source of truth | Proxy - Forwards to HTTP server |
| **Direct Access** | ✅ Yes | ❌ No - proxies to HTTP |
| **Codex Support** | ❌ No (Codex requires stdio) | ✅ Yes |
| **Network Hierarchy** | ✅ Full visibility | ✅ Full visibility (via proxy) |

**Why Dual Transport?**

Codex CLI only supports stdio transport, not HTTP/SSE. Solution: Stdio server acts as a thin proxy, forwarding all operations to HTTP server for unified registry.

```python
# run_orchestrator_stdio.py - Proxy implementation
async def _proxy_tool(self, tool_name: str, arguments: dict) -> dict:
    """Forward all tool calls to HTTP server."""
    return await self._http_request(
        "POST",
        f"{self.http_server_url}/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}
        }
    )
```

#### Bidirectional Messaging

**Design Philosophy**: Lightweight, zero-dependency messaging using standard library primitives.

**Core Principles**:
- **In-memory only**: Use `asyncio.Queue` for runtime message routing
- **No database**: No SQLAlchemy, no persistent storage for messages
- **Minimal deps**: Standard library only (asyncio, uuid, datetime)
- **Ephemeral**: Message tracking lives only during server runtime
- **Fast**: Direct queue operations, no DB round-trips

**Message Flow**:
```
1. Coordinator sends message with unique message_id
2. Message delivered to instance pane
3. Instance uses reply_to_caller() tool to respond
4. Response queued in coordinator's response queue
5. send_to_instance() returns response (or times out)
```

**Response Queue Lifecycle (Critical Implementation Detail)**:

**Problem**: Response queues must exist before replies can be received.

**Solution**: Initialize response queues at spawn time, not at send time.

```python
class TmuxInstanceManager:
    def __init__(self):
        # Response queues: instance_id -> asyncio.Queue of replies
        self.response_queues: dict[str, asyncio.Queue] = {}

        # Message registry: message_id -> MessageEnvelope
        self.message_registry: dict[str, MessageEnvelope] = {}

async def spawn_instance(...) -> str:
    """Spawn a new instance and initialize its response queue."""
    instance_id = str(uuid.uuid4())

    # ... tmux session creation ...

    # ✅ CRITICAL: Create response queue at spawn time
    # This ensures the instance can receive replies immediately,
    # even before it sends any messages itself
    self.response_queues[instance_id] = asyncio.Queue()

    self.instances[instance_id] = instance
    return instance_id

async def send_message(
    instance_id: str,
    message: str,
    wait_for_response: bool = True,
    timeout_seconds: int = 30
) -> dict[str, Any] | None:
    """Send message to instance and optionally wait for reply."""
    # Generate message ID
    message_id = str(uuid.uuid4())
    formatted_message = f"[MSG:{message_id}] {message}"

    # Send to instance's tmux pane
    session.cmd("send-keys", formatted_message, "Enter")

    if wait_for_response:
        # Wait for response from parent's response queue
        # (queue already exists because created at spawn)
        sender_id = self.instances[instance_id].get("parent_instance_id") or "coordinator"
        response = await asyncio.wait_for(
            self.response_queues[sender_id].get(),
            timeout=timeout_seconds
        )
        return response

async def handle_reply_to_caller(
    instance_id: str,
    reply_message: str,
    correlation_id: str | None = None
) -> dict[str, Any]:
    """Handle reply from child instance to parent."""
    instance = self.instances.get(instance_id)
    parent_id = instance.get("parent_instance_id")

    # Queue reply in parent's response queue
    # (queue guaranteed to exist because created at spawn)
    if parent_id and parent_id in self.response_queues:
        await self.response_queues[parent_id].put({
            "sender_id": instance_id,
            "reply_message": reply_message,
            "correlation_id": correlation_id,
            "timestamp": datetime.now().isoformat()
        })

    return {
        "success": True,
        "delivered_to": parent_id or "coordinator",
        "correlation_id": correlation_id
    }
```

**Why This Matters**:

| Timing | Problem | Impact |
|--------|---------|--------|
| **Before Fix (Queue at send time)** | Parent's queue doesn't exist until parent sends first message | First reply from child to parent fails silently |
| **After Fix (Queue at spawn time)** | Parent's queue exists immediately at spawn | All replies work, even if parent never sends messages |

**Real-World Bug Fixed (October 2025)**:

```python
# Scenario: Supervisor spawns worker, worker replies immediately

# ❌ OLD BEHAVIOR:
supervisor_id = spawn_instance("supervisor")
# supervisor's response_queue: ❌ DOESN'T EXIST YET

worker_id = spawn_instance("worker", parent_instance_id=supervisor_id)
# worker uses reply_to_caller → tries to queue in supervisor's response_queue
# ❌ FAILS: supervisor's queue doesn't exist yet

# ✅ NEW BEHAVIOR:
supervisor_id = spawn_instance("supervisor")
# supervisor's response_queue: ✅ CREATED IMMEDIATELY

worker_id = spawn_instance("worker", parent_instance_id=supervisor_id)
# worker uses reply_to_caller → queues in supervisor's response_queue
# ✅ SUCCESS: supervisor's queue exists and ready
```

**Message Envelope System**:

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

    def mark_delivered(self, timestamp: datetime):
        self.delivered_at = timestamp
        self.status = 'delivered'

    def mark_replied(self, reply: str, timestamp: datetime):
        self.reply_content = reply
        self.replied_at = timestamp
        self.status = 'replied'
```

**MCP Tool for Responses**:
```python
{
    "name": "reply_to_caller",
    "description": "Reply to the instance/coordinator that sent you a message (MANDATORY for supervised instances)",
    "input_schema": {
        "type": "object",
        "properties": {
            "instance_id": {"type": "string", "description": "Your instance ID"},
            "reply_message": {"type": "string", "description": "Your reply content"},
            "correlation_id": {"type": "string", "description": "Message ID from incoming message"}
        },
        "required": ["instance_id", "reply_message"]
    }
}
```

**System Prompt Enforcement**:

All supervised instances receive mandatory instructions:

```
BIDIRECTIONAL MESSAGING PROTOCOL (REQUIRED):
When you receive messages formatted as [MSG:correlation-id] content,
you MUST respond using the reply_to_caller tool:

  reply_to_caller(
    instance_id='your-instance-id',
    reply_message='your response here',
    correlation_id='correlation-id-from-message'
  )

IMPORTANT: Always use reply_to_caller for every response to messages.
This enables instant bidirectional communication and proper correlation.
```

**Performance Characteristics**:

| Operation | Complexity | Latency | Throughput |
|-----------|-----------|---------|------------|
| Queue creation | O(1) | <1ms | N/A |
| Queue put | O(1) | <1ms | 10,000+ ops/sec |
| Queue get (blocking) | O(1) | <1ms (if ready) | 10,000+ ops/sec |
| Message correlation | O(1) dict lookup | <1ms | N/A |

**Benefits Over Polling**:

| Aspect | Bidirectional (Queue) | Polling (Deprecated) |
|--------|---------------------|----------------------|
| Latency | <1ms (queue put/get) | 100-500ms (pane capture) |
| CPU Usage | Minimal (event-driven) | High (periodic polling) |
| Reliability | Guaranteed delivery | May miss rapid outputs |
| Scalability | O(1) per message | O(n) polling overhead |
| Correlation | Explicit correlation IDs | Heuristic matching |

#### Inter-Process Communication (IPC) with SharedStateManager

**Challenge**: STDIO Transport Process Isolation

When Codex instances connect via STDIO transport, they spawn a separate `run_orchestrator.py` subprocess with its own InstanceManager. This creates isolated memory spaces that cannot share state:

```
HTTP Server (localhost:8001)
└─ InstanceManager A (has all instances)

Codex STDIO Connection
└─ run_orchestrator.py (subprocess)
    └─ InstanceManager B (empty, isolated)
```

**Problem**: When Codex instance calls `reply_to_caller()`, the request goes to InstanceManager B, which doesn't have the parent instance's response queue. Result: "Instance not found" error.

**Solution**: `SharedStateManager` with Python `multiprocessing.Manager`

**Architecture**:

```python
from multiprocessing import Manager

class SharedStateManager:
    """Manages cross-process shared state using multiprocessing.Manager.

    Provides:
    - Response queues (instance_id → Manager.Queue)
    - Message registry (message_id → MessageEnvelope dict)
    - Instance metadata (instance_id → metadata dict)
    - Thread-safe locks for synchronization
    """

    def __init__(self):
        self.manager = Manager()  # Daemon process for proxy objects

        # Shared data structures (accessible across processes)
        self.response_queues: dict[str, Queue] = {}  # instance_id → Manager.Queue
        self.message_registry: DictProxy = self.manager.dict()  # Shared dict
        self.instance_metadata: DictProxy = self.manager.dict()  # Shared dict
        self.queue_locks: dict[str, Lock] = {}  # instance_id → Manager.Lock
```

**Key Features**:

1. **Cross-Process Queues**: `Manager.Queue(maxsize=100)` accessible from any process
2. **Shared Dictionaries**: `Manager.dict()` for message registry and metadata
3. **Thread-Safe Locks**: `Manager.Lock()` for concurrent access protection
4. **Automatic Proxy**: Manager daemon provides proxy objects for IPC

**Implementation Flow**:

```
1. HTTP Server Startup:
   └─ Initialize SharedStateManager (starts Manager daemon)
   └─ Pass shared_state_manager to TmuxInstanceManager

2. Instance Spawn (HTTP or STDIO):
   └─ TmuxInstanceManager creates queue:
       - If shared_state exists: shared_state.create_response_queue(id)
       - Else: self.response_queues[id] = asyncio.Queue()  # Local fallback

3. Message Sending:
   └─ Parent sends message with correlation ID
   └─ Child receives message via tmux pane

4. Reply (Child → Parent):
   └─ Child calls reply_to_caller(instance_id, reply_message, correlation_id)
   └─ handle_reply_to_caller():
       - If shared_state: shared_state.get_response_queue(parent_id).put(reply)
       - Else: self.response_queues[parent_id].put(reply)  # Local fallback
```

**Async Wrapper Methods** (Critical for Event Loop Safety):

Since `multiprocessing.Queue` operations are blocking and would deadlock asyncio, we use ThreadPoolExecutor:

```python
async def _get_from_shared_queue(self, instance_id: str, timeout: int = 30):
    """Async wrapper for blocking Queue.get() using ThreadPoolExecutor."""
    queue = self.shared_state.get_response_queue(instance_id)

    def blocking_get():
        return queue.get(timeout=timeout)

    # Run in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, blocking_get)

async def _put_to_shared_queue(self, instance_id: str, message: dict):
    """Async wrapper for blocking Queue.put() using ThreadPoolExecutor."""
    queue = self.shared_state.get_response_queue(instance_id)

    def blocking_put():
        queue.put(message)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, blocking_put)
```

**Backward Compatibility**:

All queue operations use conditional logic to maintain compatibility:

```python
# Queue initialization at spawn time
if self.shared_state:
    # STDIO transport: use cross-process shared queue
    self.shared_state.create_response_queue(instance_id)
else:
    # HTTP transport: use local asyncio.Queue
    self.response_queues[instance_id] = asyncio.Queue()

# Sending replies
if self.shared_state:
    # STDIO: put into shared queue
    await self._put_to_shared_queue(parent_id, reply)
else:
    # HTTP: put into local queue
    await self.response_queues[parent_id].put(reply)
```

**Performance Characteristics**:

| Operation | HTTP (Local Queue) | STDIO (Shared Queue) | Overhead |
|-----------|-------------------|---------------------|----------|
| Queue creation | O(1), <1ms | O(1), ~2-5ms (IPC) | +2-4ms |
| Queue put | O(1), <1ms | O(1), ~1-3ms (IPC) | +1-2ms |
| Queue get | O(1), <1ms | O(1), ~1-3ms (IPC) | +1-2ms |
| Manager daemon | N/A | ~10-20MB RAM | Minimal |

**Cleanup and Shutdown**:

```python
# Instance termination cleanup
async def terminate_instance(self, instance_id: str):
    # ... tmux session cleanup ...

    # Clean up shared state
    if self.shared_state:
        self.shared_state.cleanup_instance(instance_id)
    else:
        # Local queue cleanup
        if instance_id in self.response_queues:
            del self.response_queues[instance_id]

# Server shutdown
async def shutdown(self):
    # ... terminate all instances ...

    # Shutdown Manager daemon
    if self.shared_state:
        self.shared_state.shutdown()  # Graceful Manager daemon shutdown
```

**Benefits**:

| Aspect | Before IPC | After IPC |
|--------|-----------|-----------|
| STDIO reply_to_caller | ❌ Fails (instance not found) | ✅ Works (shared state) |
| Cross-process communication | ❌ Impossible | ✅ Full support |
| HTTP transport | ✅ Works | ✅ Works (unchanged) |
| Memory overhead | Minimal | +10-20MB (Manager daemon) |
| Latency overhead | 0ms | +1-3ms per IPC operation |
| Code complexity | Simple | Moderate (conditional logic) |

**Trade-offs**:

**Chosen**: Conditional IPC (shared state when available, local queues as fallback)

**Why**:
- Preserves HTTP transport performance (zero overhead)
- Enables STDIO transport bidirectional messaging
- Maintains backward compatibility
- Single codebase for both transports

**Cost**:
- Additional complexity (if/else branching)
- ThreadPoolExecutor overhead for async wrapping
- Manager daemon memory footprint

**Implementation Files**:

- `src/orchestrator/shared_state_manager.py` (386 lines) - Core IPC logic
- `src/orchestrator/instance_manager.py` - Initialize and pass SharedStateManager
- `src/orchestrator/tmux_instance_manager.py` - Conditional queue operations
- `run_orchestrator.py` - Cleanup in finally block

#### Message Patterns

**1. Point-to-Point Communication**:
```python
# Parent → Child
response = await manager.send_to_instance(
    instance_id="child-123",
    message="Analyze this data",
    wait_for_response=True
)

# Child → Parent (via reply_to_caller tool)
# Instance executes: reply_to_caller(reply_message="Analysis complete", instance_id="child-123")
```

**2. Broadcast Communication**:
```python
# Parent → All Children
responses = await manager.broadcast_to_children(
    parent_id="parent-123",
    message="Start processing batch",
    wait_for_responses=True
)
```

**3. Parallel Messaging**:
```python
# Coordinator → Multiple Instances
await manager.send_to_multiple_instances([
    {"instance_id": "worker-1", "message": "Task 1"},
    {"instance_id": "worker-2", "message": "Task 2"},
    {"instance_id": "worker-3", "message": "Task 3"}
])
```

### Storage Layer

The storage layer provides persistent and ephemeral storage for instance data.

#### Instance Workspaces

Each instance gets an isolated workspace directory:

**Structure**:
```
/tmp/claude_orchestrator/
├── {instance_id_1}/
│   ├── metadata.json       # Instance configuration
│   ├── workspace/          # Working directory
│   └── ...                 # Instance-specific files
├── {instance_id_2}/
│   ├── metadata.json
│   ├── workspace/
│   └── ...
```

**Benefits**:
- File isolation between instances
- Prevents conflicts and overwrites
- Clean separation of concerns
- Easy cleanup on termination

#### Logging System

Comprehensive logging with per-instance isolation:

**Log Structure**:
```
/tmp/madrox_logs/
├── audit/
│   └── audit_YYYYMMDD.jsonl        # System-wide audit trail
├── instances/
│   ├── {instance_id_1}/
│   │   ├── instance.log            # Lifecycle events (text)
│   │   ├── communication.jsonl     # Message I/O (JSON Lines)
│   │   └── tmux_output.log         # Raw tmux captures
│   ├── {instance_id_2}/
│   │   ├── instance.log
│   │   ├── communication.jsonl
│   │   └── tmux_output.log
```

**Log Types**:

| Log File | Format | Purpose | Retention |
|----------|--------|---------|-----------|
| **audit_YYYYMMDD.jsonl** | JSON Lines | System-wide events | Daily rotation, 30 days |
| **instance.log** | Text | Lifecycle events | 5MB rotating, 3 backups |
| **communication.jsonl** | JSON Lines | Message I/O with timing | Full history |
| **tmux_output.log** | Text | Raw tmux captures | Append-only |

**Audit Log Events**:
```jsonl
{"timestamp":"2025-10-07T12:30:45","event":"instance_spawn","instance_id":"abc123","details":{...}}
{"timestamp":"2025-10-07T12:31:10","event":"message_exchange","instance_id":"abc123","tokens":150,"cost":0.00015}
{"timestamp":"2025-10-07T12:35:20","event":"instance_terminate","instance_id":"abc123","uptime_seconds":275}
```

#### Database Layer

SQLite database for instance metadata (optional - can be in-memory only):

**Schema**:
```sql
CREATE TABLE instances (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,  -- 'claude' or 'codex'
    role TEXT NOT NULL,
    state TEXT NOT NULL,
    parent_instance_id TEXT,
    created_at TIMESTAMP,
    terminated_at TIMESTAMP,
    total_tokens_used INTEGER,
    total_cost REAL,
    request_count INTEGER,
    metadata JSON
);
```

**Use Cases**:
- Persist instance state across server restarts
- Query historical instance data
- Generate usage reports and analytics
- Audit compliance and cost tracking

---

## Containerization

### Docker Architecture

Madrox provides a production-ready containerized deployment with multi-stage builds and security hardening.

#### Multi-Stage Build

```dockerfile
# Stage 1: Builder (install dependencies)
FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
RUN pip install --user uv && \
    ~/.local/bin/uv pip install --system .

# Stage 2: Runtime (minimal image)
FROM python:3.12-slim
RUN useradd -m -u 1000 -s /bin/bash madrox
COPY --from=builder /usr/local /usr/local
COPY --chown=madrox:madrox . /app
USER madrox
CMD ["python", "run_orchestrator.py"]
```

**Benefits**:
- Smaller image size (no build tools in final image)
- Faster deployments
- Improved security (minimal attack surface)

#### Container Structure

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

#### Volume Management

Three named volumes preserve data across container restarts:

| Volume | Mount Point | Purpose | Size Estimate |
|--------|-------------|---------|---------------|
| `madrox-data` | `/data` | SQLite database (instance metadata) | 100MB - 1GB |
| `madrox-logs` | `/logs` | Audit logs, instance logs | 500MB - 5GB |
| `madrox-workspaces` | `/tmp/claude_orchestrator` | Instance working directories | 1GB - 10GB |

**Configuration (docker-compose.yml)**:
```yaml
volumes:
  madrox-data:
  madrox-logs:
  madrox-workspaces:

services:
  madrox:
    volumes:
      - madrox-data:/data
      - madrox-logs:/logs
      - madrox-workspaces:/tmp/claude_orchestrator
```

### Networking

#### Container Network

**Bridge Network Isolation**:
```yaml
networks:
  madrox-network:
    driver: bridge
```

**Port Mapping**:
```yaml
ports:
  - "${ORCHESTRATOR_PORT:-8001}:8001"  # FastAPI HTTP server
```

**Internal Communication**:
- All instances run in the same container
- Communication via localhost (no network overhead)
- Tmux sessions for isolation

#### External Communication

**MCP Protocol Endpoints**:
- HTTP transport: `http://localhost:8001/mcp`
- Stdio transport: Proxies to HTTP server

**REST API Endpoints**:
- `/health` - Health check
- `/tools` - List available tools
- `/tools/execute` - Execute tool
- `/instances` - List instances
- `/network/hierarchy` - Network topology
- `/logs/audit` - Audit logs
- `/logs/instances/{id}` - Instance logs

### Resource Management

#### Resource Limits

**CPU & Memory Constraints**:
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

**Disk Quotas**:
```yaml
tmpfs:
  - /tmp:mode=1777,size=1G    # 1GB temp files
  - /run:mode=755,size=100M   # 100MB runtime data
```

#### Instance Resource Limits

**Per-Instance Limits**:
```python
config = OrchestratorConfig(
    max_concurrent_instances=10,
    max_tokens_per_instance=100000,
    max_total_cost=100.0,
    instance_timeout_minutes=60
)
```

**Enforcement**:
- Health monitor checks limits every 60 seconds
- Automatic termination when limits exceeded
- Graceful shutdown with cleanup
- Audit log entries for limit violations

#### Health Monitoring

**Docker Health Check**:
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8001/health || exit 1
```

**Health Check Response**:
```json
{
  "status": "healthy",
  "instances_active": 5,
  "instances_total": 12,
  "uptime_seconds": 3600
}
```

---

## Design Decisions

### Key Choices

#### 1. Tmux for Instance Isolation

**Decision**: Use tmux sessions instead of separate processes or containers per instance.

**Rationale**:
- **Lightweight**: Tmux sessions consume minimal resources
- **Persistent**: Sessions survive network disconnections
- **Inspectable**: Easy to attach and debug running instances
- **CLI integration**: Natural fit for Claude Code CLI and Codex CLI
- **Message capture**: Built-in logging via `tmux capture-pane`

**Alternative Considered**: Docker containers per instance
- **Rejected**: Too heavyweight, complex networking, slower spawn times

#### 2. Bidirectional Communication via Asyncio Queues

**Decision**: Use in-memory asyncio.Queue for message routing instead of database-backed queues.

**Rationale**:
- **Zero dependencies**: Standard library only (asyncio, uuid, datetime)
- **Fast**: Direct queue operations, no DB round-trips
- **Simple**: Ephemeral messaging matches use case (orchestration, not durable workflows)
- **Lightweight**: No SQLAlchemy, no Alembic, no migrations

**Alternative Considered**: PostgreSQL message queue (like Hephaestus)
- **Rejected**: Overkill for ephemeral orchestration, adds complexity

**Comparison**:
| Aspect | Hephaestus | Madrox |
|--------|------------|--------|
| Storage | PostgreSQL/SQLite | In-memory dict/Queue |
| Persistence | Survives restarts | Runtime only |
| Dependencies | SQLAlchemy, Alembic | Standard library |
| Use case | Long-running workflows | Ephemeral orchestration |

#### 3. Dual Transport (HTTP + Stdio Proxy)

**Decision**: Provide both HTTP and stdio transports, with stdio proxying to HTTP.

**Rationale**:
- **Codex requirement**: Codex CLI only supports stdio transport
- **Unified registry**: Single source of truth for all instances (HTTP server)
- **Compatibility**: Support both Claude (HTTP/stdio) and Codex (stdio only)
- **Network visibility**: All instances visible regardless of spawn source

**How It Works**:
```
Codex CLI (stdio) → Stdio Server (proxy) → HTTP Server (registry)
                                              ↑
Claude Code CLI (HTTP) ──────────────────────┘
```

#### 4. Role-Based Specialization

**Decision**: Provide 10 predefined expert roles with comprehensive system prompts (70-120 lines each).

**Rationale**:
- **Quality**: Expert-level prompts researched from 2025 industry standards
- **Convenience**: Quick spawn with `role="architect"` instead of writing prompts
- **Customizable**: Users can override with custom `system_prompt` parameter
- **Maintainable**: Prompts stored as text files in `resources/prompts/`

**Roles**:
- General, Frontend Developer, Backend Developer, Testing Specialist
- Documentation Writer, Code Reviewer, Architect, Debugger
- Security Analyst, Data Analyst

#### 5. Workspace Isolation

**Decision**: Each instance gets its own workspace directory (`/tmp/claude_orchestrator/{instance_id}/`).

**Rationale**:
- **File isolation**: Prevent conflicts between instances
- **Security**: Instances can't access each other's files
- **Clean separation**: Easy to identify which files belong to which instance
- **Easy cleanup**: Delete directory on termination

**Alternative Considered**: Shared workspace with subdirectories
- **Rejected**: Risk of path traversal, complex access control

#### 6. Hierarchical Networks with Parent-Child Relationships

**Decision**: Support recursive instance spawning with explicit parent_instance_id tracking.

**Rationale**:
- **Natural delegation**: Mirrors real-world organizational structures
- **Cascade termination**: Terminate parent → auto-terminate all children
- **Network visibility**: Query full tree with `get_instance_tree()`
- **Complex workflows**: Enable multi-level orchestration (e.g., reverse engineering with specialists spawning sub-specialists)

**Example**:
```
Coordinator (architect)
├── Research Instance → spawns → Paper Analyzer
├── Design Instance → spawns → Architecture Validator
└── Implementation Instance
    ├── Frontend Developer
    └── Backend Developer → spawns → Codex Optimizer
```

### Trade-offs

#### 1. In-Memory Message Queues vs Persistent Queues

**Trade-off**: Ephemeral messages (lost on restart) vs durable messages (survives restarts).

**Chosen**: Ephemeral (in-memory asyncio.Queue)

**Why**:
- Use case is orchestration, not long-running workflows
- Restart = new session (instances terminated)
- Simplicity and speed outweigh persistence needs

**Cost**:
- Server restart loses message history
- Cannot resume interrupted workflows across restarts

**Mitigation**:
- Audit logs preserve high-level event history
- Communication logs track message I/O per instance

#### 2. Tmux Sessions vs Separate Processes

**Trade-off**: Shared tmux multiplexer vs individual processes.

**Chosen**: Tmux sessions

**Why**:
- Lightweight (minimal resource overhead)
- Easy debugging (attach to session)
- Message capture built-in

**Cost**:
- Tmux dependency required
- Limited isolation compared to containers

**Mitigation**:
- Workspace isolation for file separation
- Process monitoring for health checks

#### 3. Single HTTP Server (Registry) vs Distributed Registries

**Trade-off**: Centralized registry vs distributed per-transport registries.

**Chosen**: Single HTTP server as source of truth

**Why**:
- Unified network visibility
- Consistent parent-child relationships
- Simplified debugging

**Cost**:
- HTTP server is single point of failure
- Stdio server depends on HTTP server availability

**Mitigation**:
- Health monitoring with automatic restart
- Graceful degradation (stdio returns errors if HTTP down)

#### 4. Dynamic MCP Server Configuration vs Static Configuration

**Trade-off**: Configure MCP servers at spawn time vs global configuration only.

**Chosen**: Dynamic configuration per instance

**Why**:
- Granular control (different tools for different roles)
- Security (instances only get tools they need)
- Flexibility (browser automation only for web-scraping instances)

**Cost**:
- Complexity (manage `mcp_servers` parameter)
- Startup time (run `claude mcp add` commands at spawn)

**Mitigation**:
- Helper functions (`get_mcp_servers()`) for common configs
- Prebuilt configurations in `resources/mcp_configs/`

#### 5. SQLite vs PostgreSQL

**Trade-off**: Lightweight embedded database vs robust client-server database.

**Chosen**: SQLite (default)

**Why**:
- Zero-configuration (no separate database service)
- Fast for single-server deployments
- Sufficient for orchestration metadata

**Cost**:
- No horizontal scaling
- Limited concurrent writes

**Mitigation**:
- PostgreSQL support planned (migration scripts needed)
- In-memory mode for ultra-fast testing

---

## Security Model

### Security Layers

#### 1. Container Security

**Non-Root User**:
```dockerfile
RUN useradd -m -u 1000 -s /bin/bash madrox
USER madrox
```

**Security Options**:
```yaml
security_opt:
  - no-new-privileges:true  # Prevent privilege escalation
```

**Read-Only Root Filesystem** (where applicable):
```yaml
read_only: true
tmpfs:
  - /tmp:mode=1777,size=1G
  - /run:mode=755,size=100M
```

#### 2. Workspace Isolation

**Per-Instance Directories**:
- Each instance operates in its own workspace
- No access to other instances' files
- Clean separation of concerns

**File Permissions**:
```python
# Workspace created with restricted permissions
workspace_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
```

#### 3. Resource Limits

**Prevent Resource Exhaustion**:
```python
config = OrchestratorConfig(
    max_concurrent_instances=10,
    max_tokens_per_instance=100000,
    max_total_cost=100.0,
    instance_timeout_minutes=60
)
```

**Enforcement**:
- Health monitor checks limits every 60 seconds
- Automatic termination when exceeded
- Audit log entries for violations

#### 4. API Key Security

**Best Practices**:
- Never commit API keys to version control
- Use `.env` file (excluded by .gitignore)
- Rotate keys regularly (every 90 days)
- Use read-only keys if possible
- Monitor API usage at provider console

**Secrets Management (Production)**:
```bash
# Docker Swarm Secrets
echo "sk-ant-key" | docker secret create anthropic_key -

# Kubernetes Secrets
kubectl create secret generic madrox-secrets \
  --from-literal=anthropic-api-key=sk-ant-key
```

#### 5. Network Security

**Restrict External Access**:
```yaml
# Local-only binding
ports:
  - "127.0.0.1:8001:8001"
```

**Reverse Proxy with TLS**:
```nginx
server {
    listen 443 ssl http2;
    server_name madrox.example.com;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://localhost:8001;
    }
}
```

#### 6. Input Validation

**Sanitization**:
- Validate all user inputs (instance names, messages)
- Escape special characters in tmux commands
- Validate API responses before processing

**Example**:
```python
def _sanitize_instance_name(name: str) -> str:
    """Remove potentially dangerous characters from instance names."""
    return re.sub(r'[^a-zA-Z0-9_-]', '', name)
```

### Security Boundaries

**Isolation Levels**:

| Boundary | Mechanism | Strength |
|----------|-----------|----------|
| **Instance ↔ Instance** | Workspace directories | Medium |
| **Instance ↔ Host** | Container isolation | Strong |
| **User ↔ Madrox** | API authentication (future) | TBD |
| **Network ↔ Madrox** | Firewall rules, TLS | Strong (optional) |

### Audit Trail

**Security Events Logged**:
- Instance spawn/terminate
- Message exchanges (with content truncation)
- Resource limit violations
- Health check failures
- API errors and exceptions

**Audit Log Format**:
```jsonl
{"timestamp":"2025-10-07T12:30:45","event":"instance_spawn","instance_id":"abc123","user":"system"}
{"timestamp":"2025-10-07T12:31:10","event":"resource_limit_exceeded","instance_id":"abc123","limit_type":"tokens"}
{"timestamp":"2025-10-07T12:35:20","event":"instance_terminate","instance_id":"abc123","reason":"limit_exceeded"}
```

---

## Scalability

### Current Scale

**Single-Server Limits**:
- **Concurrent instances**: 10 (configurable up to 50+)
- **Instances per hour**: 100+ (depends on spawn time)
- **Message throughput**: 1000+ messages/minute
- **Storage**: Scales with disk space (workspaces, logs)

### Horizontal Scaling

**Multi-Instance Deployment**:

Run multiple Madrox servers on different ports:

```yaml
# docker-compose-multi.yml
services:
  madrox-1:
    ports: ["8001:8001"]
    volumes: [madrox-data-1:/data, madrox-logs-1:/logs]

  madrox-2:
    ports: ["8002:8001"]
    volumes: [madrox-data-2:/data, madrox-logs-2:/logs]

  madrox-3:
    ports: ["8003:8001"]
    volumes: [madrox-data-3:/data, madrox-logs-3:/logs]
```

**Load Balancing**:

Use HAProxy or Nginx to distribute requests:

```
Frontend (HAProxy)
├─ Backend 1: madrox-server-1:8001
├─ Backend 2: madrox-server-2:8002
└─ Backend 3: madrox-server-3:8003
```

**Challenges**:
- No shared state between servers (sticky sessions required)
- Parent-child relationships tied to single server
- Network hierarchy fragmented across servers

**Future**: Distributed coordination layer (Redis, etcd)

### Vertical Scaling

**Resource Optimization**:

**CPU**:
- Increase CPU cores for parallel spawning
- Async I/O minimizes CPU blocking

**Memory**:
- Increase RAM for more concurrent instances
- Each instance: ~50-200MB depending on context

**Disk**:
- Fast SSD for workspaces and logs
- Log rotation to prevent disk exhaustion

**Configuration**:
```yaml
deploy:
  resources:
    limits:
      cpus: '8.0'    # 8 cores
      memory: 16G    # 16GB RAM
```

### Performance Optimization

**Parallel Operations**:
```python
# Spawn multiple instances in parallel
instance_ids = await manager.spawn_multiple_instances([
    {"name": "worker-1", "role": "general", "wait_for_ready": False},
    {"name": "worker-2", "role": "general", "wait_for_ready": False},
    {"name": "worker-3", "role": "general", "wait_for_ready": False}
])
# Returns immediately, instances initialize in background
```

**Non-Blocking Mode**:
```python
# Spawn without waiting for initialization
instance_id = await manager.spawn_instance(
    name="worker",
    role="general",
    wait_for_ready=False  # Return ID immediately
)
```

**Batch Messaging**:
```python
# Message multiple instances concurrently
await manager.send_to_multiple_instances([
    {"instance_id": id1, "message": "Task 1", "wait_for_response": False},
    {"instance_id": id2, "message": "Task 2", "wait_for_response": False},
    {"instance_id": id3, "message": "Task 3", "wait_for_response": False}
])
```

### Database Scaling

**Current**: SQLite (single file, limited concurrency)

**Future**: PostgreSQL migration
```python
config = OrchestratorConfig(
    database_url="postgresql://madrox:password@postgres:5432/madrox"
)
```

**Benefits**:
- Horizontal scaling (read replicas)
- Better concurrent write performance
- Connection pooling
- Advanced query optimization

### Monitoring & Metrics

**Performance Metrics**:
- Instance spawn time (target: <30s)
- Message response time (target: <5s)
- API endpoint latency (target: <100ms)
- Resource utilization (CPU, memory, disk)
- Error rates and health scores

**Monitoring Integration**:
```bash
# Prometheus exporter (future)
curl http://localhost:8001/metrics

# Grafana dashboard (future)
# - Active instances over time
# - Message throughput
# - Cost tracking
# - Error rates
```

---

## Summary

Madrox provides a production-ready, scalable architecture for hierarchical multi-agent orchestration with:

✅ **Hierarchical Networks**: 3+ levels of parent-child relationships
✅ **Multi-Model Support**: Claude + Codex + future models
✅ **Bidirectional Communication**: Parents ↔ children with message correlation
✅ **Dual Transport**: HTTP (primary) + stdio (Codex compatibility)
✅ **Workspace Isolation**: Per-instance directories
✅ **Comprehensive Logging**: Audit trails + per-instance logs
✅ **Resource Management**: Tokens, cost, timeout limits
✅ **Health Monitoring**: Automatic checks with cleanup
✅ **Security Hardening**: Non-root user, workspace isolation, resource limits
✅ **Containerization**: Docker + docker-compose with persistent volumes
✅ **Scalability**: Vertical (resource limits) + horizontal (multi-instance)

**Key Design Principles**:
- **Lightweight**: In-memory queues, tmux sessions, minimal dependencies
- **Flexible**: Dynamic MCP configuration, role-based specialization, custom prompts
- **Observable**: Full network visibility, comprehensive logging, audit trails
- **Resilient**: Health monitoring, graceful shutdown, error recovery
- **Secure**: Container isolation, workspace separation, resource limits

**Production-Ready**: Validated through comprehensive stress testing with 10+ instances across 3 hierarchical levels, 90+ MCP operations, and zero errors.
