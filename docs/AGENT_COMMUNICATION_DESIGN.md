# Agent Communication Design Document

**Status:** Living Document
**Last Updated:** 2026-03-10
**Scope:** Inter-agent communication architecture for spawned Madrox teams

---

## 1. Overview

Madrox orchestrates multiple Claude CLI instances as isolated processes, each running in its own tmux session. Communication between these agents follows a **message-passing architecture** built on top of two transport layers: in-process `asyncio.Queue` (HTTP mode) and cross-process `multiprocessing.Manager` proxies (STDIO mode).

This document describes the design patterns, message flow, and coordination mechanisms that enable spawned teams of agents to collaborate on complex tasks.

---

## 2. Core Design Patterns

### 2.1 Manager-Worker Pattern

The fundamental organizational pattern. A central `TmuxInstanceManager` acts as the message broker between all instances.

```
┌─────────────────────────────────────────┐
│           TmuxInstanceManager           │
│  (message broker + process supervisor)  │
├─────────────────────────────────────────┤
│  - Spawns/terminates tmux sessions      │
│  - Routes messages between instances    │
│  - Tracks message lifecycle (envelopes) │
│  - Manages response queues              │
│  - Enforces resource limits             │
└────┬──────────┬──────────┬──────────┬───┘
     │          │          │          │
   [tmux]    [tmux]    [tmux]    [tmux]
  Agent A   Agent B   Agent C   Agent D
```

**Key property:** Agents never communicate directly at the OS level. All messages are mediated through the `TmuxInstanceManager`, which writes to tmux panes (`send-keys`) and reads from them (`capture-pane`).

### 2.2 Hierarchical Delegation (Parent-Child)

Agents form trees. A parent spawns children with `parent_instance_id` set to its own ID, creating an explicit hierarchy.

```
         Supervisor (parent)
        /         |          \
  Engineer     Designer     QA Engineer
  (child)      (child)       (child)
```

**Source:** `src/orchestrator/instance_manager/hierarchy.py:127-188`

Children are discovered by filtering the instance registry for matching `parent_instance_id`. The hierarchy enables:

- **Downward communication:** Parent uses `send_to_instance(child_id, msg)` or `broadcast_to_children(parent_id, msg)` to send work to children.
- **Upward communication:** Children use `reply_to_caller(my_id, reply, correlation_id)` to send results back to their parent.
- **Status polling:** Parents call `get_pending_replies(my_id)` to collect queued responses from children.

### 2.3 Peer-to-Peer Discovery

Siblings (agents sharing the same parent) can discover each other and communicate directly without routing through the parent.

```
      Supervisor
     /     |     \
    A  ←──→ B ←──→ C    (peer-to-peer via get_peers + send_to_instance)
```

**Source:** `src/orchestrator/instance_manager/hierarchy.py:202-256`

An agent calls `get_peers(my_id)` to get a list of sibling instances (same `parent_instance_id`, excluding terminated and self). It can then use `send_to_instance(peer_id, msg)` for direct messaging.

### 2.4 Message Envelope / Correlation ID Pattern

Every message sent through the system is wrapped in a `MessageEnvelope` that tracks its full lifecycle.

```
MessageEnvelope
├── message_id      (UUID — the correlation ID)
├── sender_id       (instance ID or "coordinator")
├── recipient_id    (target instance ID)
├── content         (message text)
├── sent_at         (timestamp)
├── status          (SENT → DELIVERED → REPLIED | TIMEOUT | ERROR)
├── replied_at      (timestamp, set on reply)
└── reply_content   (response text, set on reply)
```

**Source:** `src/orchestrator/simple_models.py:19-72`

The correlation ID is embedded in the message sent to the tmux pane:

```
[MSG:{message_id}] {actual_message_content}
```

When a child replies with `reply_to_caller(my_id, reply, correlation_id)`, the correlation ID links the reply back to the original request, enabling the parent to match responses to requests.

### 2.5 Asynchronous Message Queue Pattern

Each instance has a dedicated response queue. Replies are deposited into the target's queue and consumed asynchronously.

**HTTP mode** — `asyncio.Queue` (in-process):
```python
response_queues: dict[str, asyncio.Queue]  # instance_id → Queue
```

**STDIO mode** — `multiprocessing.Manager().Queue()` (cross-process):
```python
shared_state.response_queues: DictProxy[str, Queue]  # shared across processes
```

**Source:** `src/orchestrator/shared_state_manager.py:43-62`

The dual-queue design allows the same messaging API to work across both transport modes transparently.

---

## 3. Communication Primitives (MCP Tools)

These are the MCP tools exposed to agents for inter-agent communication:

| Tool | Direction | Description |
|------|-----------|-------------|
| `send_to_instance` | Any → Any | Send a message to a specific instance by ID |
| `send_to_multiple_instances` | One → Many | Send same message to multiple instances in parallel |
| `broadcast_to_children` | Parent → All Children | Fan-out message to all children of a parent |
| `reply_to_caller` | Child → Parent | Send a reply back to the caller/parent |
| `get_pending_replies` | Parent (poll) | Poll for queued replies from children |
| `get_peers` | Agent (discovery) | Discover sibling instances for peer messaging |
| `get_children` | Parent (discovery) | List all child instances |
| `get_instance_output` | Any (read) | Read message history of an instance |
| `coordinate_instances` | Coordinator → Participants | Structured multi-instance coordination |

**Source:** `src/orchestrator/instance_manager/messaging.py`

---

## 4. Message Flow Diagrams

### 4.1 Parent-Child Request/Reply

```
Parent                    TmuxInstanceManager               Child (tmux)
  │                              │                              │
  │  send_to_instance(child_id,  │                              │
  │    msg, wait=True)           │                              │
  │─────────────────────────────>│                              │
  │                              │  Create MessageEnvelope      │
  │                              │  Format: [MSG:{id}] msg      │
  │                              │  tmux send-keys ────────────>│
  │                              │                              │
  │         (waiting on          │                              │  (processing)
  │       response queue)        │                              │
  │                              │                              │
  │                              │  reply_to_caller(id, reply,  │
  │                              │    correlation_id)           │
  │                              │<─────────────────────────────│
  │                              │                              │
  │                              │  Queue reply in parent's     │
  │                              │  response_queue              │
  │                              │                              │
  │  ← response dequeued         │                              │
  │<─────────────────────────────│                              │
  │                              │                              │
```

### 4.2 Broadcast + Collect

```
Supervisor                  TmuxInstanceManager          Child A    Child B    Child C
  │                                │                        │          │          │
  │  broadcast_to_children(        │                        │          │          │
  │    parent_id, msg)             │                        │          │          │
  │───────────────────────────────>│                        │          │          │
  │                                │  asyncio.gather(       │          │          │
  │                                │    send A, send B,     │          │          │
  │                                │    send C)             │          │          │
  │                                │───────────────────────>│          │          │
  │                                │──────────────────────────────────>│          │
  │                                │─────────────────────────────────────────────>│
  │                                │                        │          │          │
  │  (later)                       │                        │          │          │
  │  get_pending_replies(my_id,    │   reply_to_caller ─────┘          │          │
  │    wait_timeout=10)            │   reply_to_caller ────────────────┘          │
  │───────────────────────────────>│   reply_to_caller ───────────────────────────┘
  │                                │
  │  ← [reply_A, reply_B, reply_C]│
  │<───────────────────────────────│
```

### 4.3 Peer-to-Peer

```
Agent A                     TmuxInstanceManager              Agent B
  │                                │                            │
  │  get_peers(my_id)              │                            │
  │───────────────────────────────>│                            │
  │  ← [{id: B, name: ..., ...}]  │                            │
  │<───────────────────────────────│                            │
  │                                │                            │
  │  send_to_instance(B, msg)      │                            │
  │───────────────────────────────>│  tmux send-keys ──────────>│
  │                                │                            │
  │                                │  reply_to_caller(B, reply) │
  │                                │<───────────────────────────│
  │                                │                            │
  │  (Agent A polls or the reply   │                            │
  │   is returned synchronously    │                            │
  │   if wait_for_response=True)   │                            │
  │<───────────────────────────────│                            │
```

---

## 5. Coordination Patterns

### 5.1 Parallel Coordination

All participants receive the task simultaneously. Results are collected asynchronously.

```python
# Supervisor spawns team, then broadcasts
broadcast_to_children(supervisor_id, "Implement your assigned module")

# Later, collect results
replies = get_pending_replies(supervisor_id, wait_timeout=30)
```

**Use case:** Independent subtasks — e.g., frontend, backend, and tests developed in parallel.

### 5.2 Sequential (Pipeline) Coordination

Participants process the task one after another. Each step's output feeds into the next.

```python
coordinate_instances(
    coordinator_id=supervisor_id,
    participant_ids=[architect_id, engineer_id, qa_id],
    task_description="Design, implement, then test the feature",
    coordination_type="sequential"
)
```

**Source:** `src/orchestrator/instance_manager/lifecycle.py:144-217`

Internally, `_execute_coordination` sends the task to each participant in order:

```
Architect → (designs) → Engineer → (implements) → QA → (tests)
```

**Use case:** Dependent workflow stages where output flows downstream.

### 5.3 Hierarchical Delegation

A supervisor spawns sub-supervisors, each managing their own sub-teams. This creates multi-level trees.

```
          Lead Architect
         /              \
   Frontend Lead      Backend Lead
   /    |    \        /    |    \
  UI   State  CSS   API  DB   Auth
```

Each level uses the same parent-child primitives (`send_to_instance`, `reply_to_caller`, `get_pending_replies`), composing naturally into deeper hierarchies.

**Use case:** Large projects decomposed into subsystems, each managed by a specialized lead.

### 5.4 Consensus Coordination

The `coordinate_instances` tool supports a `"consensus"` coordination type, where all participants are consulted and results are aggregated.

**Use case:** Code review, architecture decisions requiring input from multiple specialists.

---

## 6. Transport Layer Abstraction

The communication system operates identically across two transport modes, abstracted behind the `TmuxInstanceManager` and `SharedStateManager`.

### 6.1 HTTP/SSE Mode (Claude Code clients)

```
┌──────────────────────────────────────────┐
│        Single Python Process             │
│                                          │
│  TmuxInstanceManager                     │
│    └── response_queues: asyncio.Queue    │
│    └── message_history: dict             │
│                                          │
│  FastAPI Server (port 8001)              │
│    └── MCP tools via SSE                 │
└──────────────────────────────────────────┘
         │            │            │
       [tmux]       [tmux]      [tmux]
      Agent A      Agent B     Agent C
```

All queues are `asyncio.Queue` — lightweight, in-process, zero serialization overhead.

### 6.2 STDIO Mode (Codex CLI clients)

```
┌──────────────────────────────────────────┐
│        Parent Process                    │
│                                          │
│  TmuxInstanceManager                     │
│    └── SharedStateManager                │
│         └── Manager daemon (IPC)         │
│         └── response_queues: mp.Queue    │
│         └── message_registry: DictProxy  │
│         └── instance_metadata: DictProxy │
└──────────────────────────────────────────┘
         │            │            │
       [tmux]       [tmux]      [tmux]
      Agent A      Agent B     Agent C
         │            │            │
     (connects to Manager daemon via
      MADROX_MANAGER_HOST/PORT/AUTHKEY
      or MADROX_MANAGER_SOCKET env vars)
```

**Source:** `src/orchestrator/shared_state_manager.py`

Child processes inherit Manager connection credentials via environment variables:
- `MADROX_MANAGER_HOST` / `MADROX_MANAGER_PORT` (TCP)
- `MADROX_MANAGER_SOCKET` (Unix domain socket)
- `MADROX_MANAGER_AUTHKEY` (base64-encoded authentication key)

The `SharedStateManager.__init__()` detects these variables and connects to the parent's Manager daemon rather than creating a new one.

---

## 7. Message Lifecycle State Machine

```
         ┌──────┐
         │ SENT │  (envelope created, message formatted)
         └──┬───┘
            │  tmux send-keys delivers to pane
            v
       ┌──────────┐
       │ DELIVERED │  (confirmed written to tmux pane)
       └────┬─────┘
            │
     ┌──────┴──────┐
     │             │
     v             v
┌─────────┐  ┌─────────┐
│ REPLIED │  │ TIMEOUT │  (no response within timeout_seconds)
└─────────┘  └─────────┘
                  │
                  v
             ┌─────────┐
             │  ERROR  │  (delivery or processing failure)
             └─────────┘
```

**Source:** `src/orchestrator/simple_models.py:9-17`

Each state transition is tracked on the `MessageEnvelope` with timestamps, enabling monitoring and debugging of message flow.

---

## 8. Team Spawning via Templates

Templates encode pre-defined team structures as markdown files. The `spawn_team_from_template` tool automates the full team creation workflow.

**Source:** `src/orchestrator/instance_manager/templates.py:20-127`

### Spawn Flow

```
1. Parse template markdown → extract team structure, workflow phases, communication protocols
2. Build instruction prompt for supervisor (includes team blueprint + task description)
3. Spawn supervisor instance with initial_prompt containing full instructions
4. Supervisor autonomously:
   a. Reads the team blueprint from its initial prompt
   b. Calls spawn_claude() for each team member (with parent_instance_id = self)
   c. Sends tasks to team members via send_to_instance()
   d. Collects results via get_pending_replies()
   e. Coordinates workflow phases sequentially
   f. Reports final deliverables
```

### Critical Execution Instructions (embedded in supervisor prompt)

From `templates.py:213-222`:

1. Spawn team members with `parent_instance_id` set to the supervisor's ID
2. Use `broadcast_to_children` for team-wide announcements
3. Use `send_to_instance` for 1-on-1 coordination
4. Workers MUST use `reply_to_caller` to report back
5. Poll `get_pending_replies` every 5-15 minutes to collect responses
6. Follow workflow phases sequentially
7. Report final deliverables when complete

---

## 9. Message Queuing (Busy Instance Handling)

When a message is sent to an instance that is currently busy (state = `"busy"`), the message is not dropped. Instead, it is queued in a bounded in-memory deque.

```python
# From shared_state_manager.py
MAX_INCOMING_QUEUE_SIZE = 100  # Max queued messages per busy instance

_incoming_queues: dict[str, deque]  # instance_id → deque(maxlen=100)
```

When the instance transitions back to idle, `_process_queued_messages()` drains the queue and delivers messages in order.

**Source:** `src/orchestrator/shared_state_manager.py:20-23`, `src/orchestrator/tmux_instance_manager/core.py:719-750`

---

## 10. Tmux as the Communication Channel

Each agent runs as an interactive Claude/Codex CLI session inside a tmux pane. The `TmuxInstanceManager` uses tmux primitives for I/O:

| Operation | tmux Command | Purpose |
|-----------|-------------|---------|
| Send message | `send-keys` | Write text to the agent's terminal |
| Read output | `capture-pane` | Read the agent's terminal buffer |
| Interrupt | `send-keys C-c` | Send Ctrl+C to stop current work |
| Create session | `new-session -d -s madrox-{id}` | Spawn isolated agent environment |
| Kill session | `kill-session -t madrox-{id}` | Terminate agent process |

### Multiline Message Optimization

Messages are sent with size-based timing to prevent tmux buffer overflow:

| Message Size | Strategy |
|-------------|----------|
| ≤ 5 KB | Single `send-keys` call, no delay |
| 5-20 KB | Line-by-line with 15ms delay |
| > 20 KB | Line-by-line with 10ms delay |

**Source:** `src/orchestrator/tmux_instance_manager/core.py:1750-1830`

---

## 11. Resource Management and Cleanup

### Cascade Termination

When a parent is terminated, all children are recursively terminated first:

```
terminate_instance(supervisor_id)
  → find children where parent_instance_id == supervisor_id
    → terminate_instance(child_1_id)  (recursive)
    → terminate_instance(child_2_id)  (recursive)
  → kill tmux session
  → clean up shared state (queues, metadata, message registry)
```

**Source:** `src/orchestrator/tmux_instance_manager/core.py:1204-1320`

### Message Retention Policy

To prevent unbounded memory growth:

- Messages retained for **24 hours** maximum
- **1000 messages** max per instance
- **100 queued messages** max per busy instance

**Source:** `src/orchestrator/shared_state_manager.py:20-23`

---

## 12. Design Trade-offs

| Decision | Trade-off | Rationale |
|----------|-----------|-----------|
| tmux-based I/O vs JSON streaming | Loses structured tool events; gains bidirectional interactive sessions | Claude CLI's `--output-format stream-json` only works with `--print` (non-interactive). Madrox needs interactive mode for ongoing conversations. |
| Centralized message broker vs direct IPC | Single point of routing; simpler security model | All message flow is observable and controllable by the orchestrator. No need for agents to manage network connections. |
| asyncio.Queue + mp.Queue dual system | Code complexity; transparent transport switching | HTTP mode needs zero-overhead async queues; STDIO mode needs cross-process IPC. The abstraction keeps the MCP tool layer identical for both. |
| Polling-based reply collection | Latency vs simplicity | `get_pending_replies(wait_timeout=N)` is simple to reason about. Push-based would require callback registration complexity. |
| Bounded message queues | Messages dropped when queue full (100) | Prevents memory exhaustion from runaway producers. The limit of 100 is generous for normal operation. |
| Correlation IDs in message text | Couples transport format to protocol | Simple to implement, no separate metadata channel needed. The `[MSG:{id}]` prefix is stripped before display. |

---

## 13. Summary

The Madrox agent communication system is built on these core principles:

1. **Message-passing over shared memory** — Agents communicate exclusively through queued messages, never through shared mutable state.
2. **Hierarchical organization** — Parent-child relationships provide natural delegation and result collection patterns.
3. **Peer discovery** — Siblings can find and message each other directly, enabling lateral collaboration without parent bottlenecks.
4. **Envelope-based tracking** — Every message has a lifecycle tracked from SENT through DELIVERED to REPLIED/TIMEOUT/ERROR.
5. **Transport transparency** — The same MCP tools work identically whether the orchestrator runs in HTTP or STDIO mode.
6. **tmux as the universal I/O layer** — All agent interaction happens through terminal I/O, making the system CLI-agnostic and debuggable via standard terminal tools.
