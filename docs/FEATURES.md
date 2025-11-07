# Madrox Features & Usage

Comprehensive guide to Madrox's capabilities, usage patterns, and practical applications for hierarchical multi-agent orchestration.

## Core Features

### Automatic Instance Monitoring

MonitoringService provides real-time, LLM-powered monitoring of all active Claude instances. The service runs in the background, continuously tracking instance activity and generating intelligent activity summaries.

#### Features

**Automatic Activity Tracking**
- Monitors all active instances without manual intervention
- Tracks logs, outputs, and execution history
- Polls instance state at configurable intervals (default: 12 seconds)
- Persists summaries to disk for historical analysis

**LLM-Powered Summaries**
- Uses Claude via OpenRouter API to generate intelligent summaries
- Extracts key accomplishments from raw logs and outputs
- Provides contextual insights about instance performance
- Estimates completion percentage and next steps
- Caches summaries to reduce API calls

**Performance Metrics**
- Tracks tokens used per instance
- Measures execution time and task duration
- Calculates completion percentage for long-running tasks
- Aggregates metrics across entire team

**Team-Wide Monitoring**
- Get summary for single instance: `get_agent_summary(instance_id)`
- Get summaries for all instances: `get_all_agent_summaries()`
- Automatically aggregates insights across team
- Provides team-wide status and progress overview

#### How It Works

**Architecture Overview:**

```
TmuxInstanceManager
    ↓
MonitoringService (polls every 12s)
    ↓
Instance Logs & Outputs
    ↓
LLMSummarizer (with OpenRouter)
    ↓
Claude Analysis
    ↓
Summary Cache
    ↓
MCP Tools (get_agent_summary, get_all_agent_summaries)
```

**Process Flow:**

1. **Background Service**: MonitoringService starts with TmuxInstanceManager
2. **Polling**: Periodically polls instance logs and outputs (default: 12 seconds)
3. **LLM Summarization**: Sends logs to Claude via OpenRouter API
   - Claude analyzes instance activity
   - Extracts key accomplishments
   - Estimates progress and completion
   - Identifies next steps
4. **Storage**: Persists summaries to `/tmp/madrox_logs/summaries/` with timestamps
5. **Caching**: Caches recent summaries (default: 60 seconds) to reduce API calls
6. **MCP Tools**: Exposes tools for retrieving summaries programmatically

#### LLMSummarizer Component

The LLMSummarizer class handles all OpenRouter API integration:

**Initialization:**
- Validates OPENROUTER_API_KEY environment variable
- Initializes OpenRouter client with fallback model (claude-3.5-sonnet)
- Sets up retry logic for API failures

**Summarization Process:**
- Receives raw instance logs and outputs
- Constructs Claude prompt with contextual analysis instructions
- Sends request to OpenRouter API
- Parses structured response (JSON format)
- Returns:
  ```json
  {
    "activity_overview": "string",
    "key_accomplishments": ["string"],
    "next_steps": ["string"],
    "completion_percentage": 0-100,
    "tokens_used": number
  }
  ```

**Error Handling:**
- Gracefully falls back to generic summaries if API fails
- Logs all API errors and retries
- Implements exponential backoff for rate limiting
- Never stops monitoring if OpenRouter is unavailable

**Configuration:**
```python
LLMSummarizer(
    api_key="sk-or-v1-xxx",        # From OPENROUTER_API_KEY
    model="claude-3.5-sonnet",      # Configurable via OPENROUTER_MODEL
    timeout=30,                     # Request timeout
    cache_ttl=60                    # Cache freshness (seconds)
)
```

#### Usage Examples

**Monitor Single Instance Progress**

```python
# Check what a data analyst has accomplished
summary = await get_agent_summary(instance_id="analyst-1")

print(f"Overview: {summary['summary']['activity_overview']}")
print(f"Accomplishments: {summary['summary']['key_accomplishments']}")
print(f"Next Steps: {summary['summary']['next_steps']}")
print(f"Completion: {summary['summary']['completion_percentage']}%")
```

**Monitor Team Progress**

```python
# Get status of entire team
result = await get_all_agent_summaries()

# Check team-wide insights
print(f"Team Status: {result['aggregated_insights']['team_status']}")
print(f"Total Tokens: {result['aggregated_insights']['total_tokens_used']}")
print(f"Avg Completion: {result['aggregated_insights']['average_completion_percentage']}%")

# List each member's accomplishments
for summary in result['summaries']:
    print(f"\n{summary['instance_name']}:")
    for acc in summary['summary']['key_accomplishments']:
        print(f"  ✓ {acc}")
```

**Monitor During Long-Running Tasks**

```python
# Start long-running analysis task
await send_to_instance(analyst_id, "Analyze large dataset...")

# Check progress periodically
for i in range(10):
    summary = await get_agent_summary(analyst_id)
    percent = summary['summary']['completion_percentage']
    print(f"Progress: {percent}%")
    await asyncio.sleep(30)  # Check every 30 seconds
```

#### Configuration

**Environment Variables**

- `OPENROUTER_API_KEY` (optional) - Enables LLM-powered summaries
  - Get key from https://openrouter.ai
  - Without this, summaries fall back to generic format

**Monitoring Parameters**

- `poll_interval` (default: 12 seconds) - How often to check instances
- `storage_path` (default: `/tmp/madrox_logs/summaries`) - Where to store summaries
- `summary_cache_age` (default: 60 seconds) - Cache freshness threshold

#### Requirements

- **Optional**: `OPENROUTER_API_KEY` environment variable for enhanced summaries
- Without this key, MonitoringService provides generic summaries
- No additional dependencies beyond base Madrox installation

---

### Instance Management

#### Spawning Instances

Madrox provides multiple methods for creating specialized AI instances:

**Single Instance Creation**
```python
# Spawn a specialized instance with a predefined role
instance_id = await manager.spawn_instance(
    name="frontend-expert",
    role="frontend_developer",
    system_prompt="You are a React expert specializing in TypeScript and modern UI patterns."
)

# Spawn with custom expertise (overrides role)
instance_id = await manager.spawn_instance(
    name="rust-expert",
    system_prompt="""You are a Rust systems programming expert with deep knowledge of:
    - Embedded systems and bare-metal programming
    - async/await and tokio runtime internals
    - Zero-cost abstractions and compiler optimizations"""
)
```

**Parallel Spawning**
```python
# Spawn multiple instances concurrently for faster setup
instances = await manager.spawn_multiple_instances([
    {"name": "architect", "role": "architect"},
    {"name": "backend-dev", "role": "backend_developer"},
    {"name": "tester", "role": "testing_specialist"}
])
```

**Non-Blocking Mode**
```python
# Return IDs immediately while instances initialize in background
instance_ids = await manager.spawn_multiple_instances([
    {"name": "worker-1", "role": "general", "wait_for_ready": False},
    {"name": "worker-2", "role": "general", "wait_for_ready": False},
])
# Use IDs immediately, instances become ready asynchronously
```

**Multi-Model Support**
```python
# Mix Claude and Codex instances in the same network
claude_id = await manager.spawn_instance(
    name="claude-architect",
    role="architect"
)

codex_id = await manager.spawn_codex_instance(
    name="codex-optimizer",
    sandbox_mode="workspace-write"
)
```

#### Terminating Instances

**Single Termination**
```python
# Gracefully shut down with proper cleanup
await manager.terminate_instance(instance_id)
```

**Cascade Termination**
```python
# Terminate parent and all descendants automatically
await manager.terminate_instance(parent_id)
# All children and grandchildren are cleaned up recursively
```

**Batch Termination**
```python
# Terminate multiple instances in parallel
await manager.terminate_multiple_instances([id1, id2, id3])
```

### Automatic Parent Instance Detection

Madrox automatically manages parent-child relationships in instance hierarchies through intelligent parent instance ID detection. This eliminates manual tracking and ensures proper hierarchical structure formation.

#### How It Works

When you spawn a new instance, Madrox uses a two-tier detection system to automatically assign the correct parent:

**Tier 1: Explicit Parent (Highest Priority)**
If you provide `parent_instance_id` explicitly, it's always used:

```python
# You specify the parent explicitly
supervisor = await spawn_instance(name="supervisor", role="architect")
worker = await spawn_instance(
    name="worker",
    role="developer",
    parent_instance_id=supervisor  # ✅ Uses this parent
)
```

**Tier 2: Auto-Detected Caller**
If `parent_instance_id` is omitted, Madrox detects which instance is making the spawn call:

```python
# Supervisor sends instruction to spawn child
await send_to_instance(
    supervisor_id,
    """Spawn a worker:
    spawn_claude(name="worker", role="developer")
    # Madrox auto-detects supervisor as parent ✅
    """
)
```

#### Detection Strategies

The auto-detection uses two complementary strategies:

**Strategy 1: Busy State Detection (Primary)**
- Detects instances currently executing (in "busy" state)
- Examines instance state flags and activity timestamps
- Highest reliability when supervisor is actively processing

**Strategy 2: Activity-Based Detection (Fallback)**
- Detects most recently active instance with request history
- Examines request count and last activity timestamp
- Provides coverage when busy state not available

#### Exception Cases

The only exception to the parent requirement is the **main orchestrator**:

```python
# ✅ Main orchestrator allowed without parent
main = await spawn_instance(name="main-orchestrator", role="general")
# parent_instance_id = None (allowed)

# ❌ All other instances require parent
worker = await spawn_instance(name="worker", role="developer")
# ❌ ValueError: parent_instance_id required but could not be determined
```

#### When Auto-Detection Works

| Scenario | Auto-Detection | How to Fix |
|----------|---|---|
| Child spawns from message handler | ✅ Works | Call from `send_to_instance` task |
| Supervisor spawns child internally | ✅ Works | Instance automatically detected |
| External API client spawns | ❌ Fails | Provide explicit `parent_instance_id` |
| Batch spawn from manager | ✅ Works | All instances get same parent |

#### Benefits

1. **Eliminates Manual Tracking**: No need to manually pass parent IDs around
2. **Ensures Hierarchy Formation**: Automatic parent linkage creates proper tree structures
3. **Simplifies Multi-Level Coordination**: Team members can spawn their own sub-teams
4. **Reduces Errors**: Missing parent IDs detected immediately with clear guidance

#### Use Cases

**Hierarchical Team Structure:**
```python
# Supervisor spawns team members
await send_to_instance(
    supervisor_id,
    """Spawn 3 developers:
    spawn_claude(name="dev-1", role="backend_developer")  # Auto-parent: supervisor
    spawn_claude(name="dev-2", role="frontend_developer") # Auto-parent: supervisor
    spawn_claude(name="dev-3", role="qa_engineer")        # Auto-parent: supervisor
    """
)
```

**Multi-Level Delegation:**
```python
# CTO spawns team leads
# Each lead spawns their team members
# Automatic parent detection creates proper 3-level hierarchy
```

**Batch Spawning with Auto-Detection:**
```python
# All get same auto-detected parent
instances = await spawn_multiple_instances([
    {"name": "worker-1", "role": "developer"},
    {"name": "worker-2", "role": "developer"},
    {"name": "worker-3", "role": "developer"}
])
# All have same parent (auto-detected from caller)
```

### Communication

#### Coordination Patterns

Madrox supports two distinct coordination patterns, each suited for different use cases:

##### 1. Independent Instances (Parallel Coordination)

**When to Use:**
- Parallel, independent tasks without inter-instance coordination
- Simple task execution where workers don't need to communicate
- One-way communication (orchestrator → workers only)
- No hierarchical structure needed

**Characteristics:**
- ✅ No `parent_instance_id` specified
- ✅ Madrox is enabled by default for all instances
- ✅ Instances work independently in parallel
- ✅ Main orchestrator sends tasks and collects results
- ❌ Workers cannot communicate with each other
- ❌ Workers cannot use `reply_to_caller`

**Example:**
```python
# Spawn 3 independent data analyzers
analyzer_ids = await manager.spawn_multiple_instances([
    {"name": "analyzer-1", "role": "data_analyst"},
    {"name": "analyzer-2", "role": "data_analyst"},
    {"name": "analyzer-3", "role": "data_analyst"}
])

# Delegate independent tasks
for analyzer_id in analyzer_ids:
    await manager.send_to_instance(
        analyzer_id,
        "Analyze dataset partition and report findings"
    )

# Collect results from each worker independently
# Workers complete tasks in parallel without coordination
```

##### 2. Supervised Instances (Hierarchical Coordination)

**When to Use:**
- Hierarchical task delegation with supervisor coordination
- Workers need to report progress/results back to supervisor
- Complex multi-stage workflows requiring orchestration
- Supervisor needs to monitor and coordinate multiple workers
- Bidirectional communication required

**Characteristics:**
- ✅ Has `parent_instance_id` set to supervisor's ID
- ✅ Madrox is always enabled, providing bidirectional communication
- ✅ Workers can use `reply_to_caller()` to send results to supervisor
- ✅ Supervisor can use `send_to_instance()`, `broadcast_to_children()`
- ✅ Hierarchical coordination and monitoring
- ✅ Full bidirectional communication

**Example:**
```python
# Spawn supervisor (needs madrox to spawn its own workers)
supervisor_id = await manager.spawn_instance(
    name="repo-cleanup-supervisor",
    role="general"
)

# Supervisor spawns workers with parent_instance_id
await manager.send_to_instance(
    supervisor_id,
    """Spawn 3 specialized workers:
    1. Documentation analyst (parent_instance_id=YOUR_ID)
    2. Script analyst (parent_instance_id=YOUR_ID)
    3. Configuration analyst (parent_instance_id=YOUR_ID)

    Coordinate their work and report aggregated results back."""
)

# Workers use reply_to_caller to report to supervisor
# Supervisor aggregates results and reports to main orchestrator
```

**Note:**

Madrox MCP server is now always enabled for all instances by default. This ensures:
- All instances have access to bidirectional communication tools
- Supervised workers can use `reply_to_caller()` to communicate with their supervisor
- Any instance can spawn sub-instances when needed
- `send_to_instance()` and other coordination tools work seamlessly
- No configuration is needed to enable these capabilities

##### Decision Matrix

| Scenario | Pattern | parent_instance_id | Tools Available |
|----------|---------|-------------------|-----------------|
| Parallel data processing | Independent | ❌ Not set | send_to_instance only |
| Simple task execution | Independent | ❌ Not set | send_to_instance only |
| Supervisor coordinates workers | Supervised | ✅ Set | reply_to_caller, send_to_instance, broadcast |
| Multi-tier delegation | Supervised | ✅ Set | Full bidirectional communication |
| Workers report findings | Supervised | ✅ Set | reply_to_caller, send_to_instance |
| Monitor existing instances | Independent | ❌ Not set | send_to_instance only |

##### Pattern Comparison

| Aspect | Independent | Supervised |
|--------|------------|------------|
| **Complexity** | Simple | Advanced |
| **Communication** | One-way (orchestrator → worker) | Bidirectional (supervisor ↔ worker) |
| **Coordination** | Orchestrator manages all | Supervisor coordinates workers |
| **Worker Autonomy** | Full (no reporting required) | Structured (reports to supervisor) |
| **Use Case** | Parallel independent tasks | Hierarchical delegation |
| **Setup Overhead** | Low (spawn and delegate) | Medium (spawn supervisor first) |
| **Scalability** | Limited (orchestrator bottleneck) | High (delegated coordination) |

#### Messaging Patterns

**Direct Messaging**
```python
# Send message and wait for response
response = await manager.send_to_instance(
    instance_id,
    "Create a responsive navigation component with dropdown menus"
)

# Send without waiting (fire-and-forget)
await manager.send_to_instance(
    instance_id,
    "Start processing the dataset",
    wait_for_response=False
)
```

**Broadcast Messaging**
```python
# Message all children of a parent
responses = await manager.broadcast_to_children(
    parent_id=coordinator_id,
    message="Start working on the authentication feature",
    wait_for_responses=True
)
```

**Parallel Messaging**
```python
# Send different messages to multiple instances concurrently
await manager.send_to_multiple_instances([
    {
        "instance_id": architect_id,
        "message": "Design the microservices architecture"
    },
    {
        "instance_id": developer_id,
        "message": "Generate boilerplate code for user service"
    }
])
```

#### Bidirectional Communication

Child instances automatically reply directly to their parent or coordinator using the mandatory `reply_to_caller` mechanism:

**Automatic Reply Behavior (Required)**

When a supervised instance (with `parent_instance_id`) receives a message, it MUST use `reply_to_caller` instead of outputting text:

```python
# ✅ Correct: Worker uses reply_to_caller (mandatory)
reply_to_caller(
    instance_id="worker-abc123",
    reply_message="Architecture design completed. Here are the components...",
    correlation_id="2ea0e30e-7ec3-4537-8f38-c059018a3f95"  # From parent's message
)

# ❌ Incorrect: Just outputting text (polling fallback, deprecated)
# "Architecture design completed..."  # Parent won't receive this efficiently
```

**How It Works**

1. **Parent Sends Message**: Parent uses `send_to_instance()` with `wait_for_response=True`
   ```python
   response = await manager.send_to_instance(
       worker_id,
       "[MSG:2ea0e30e-7ec3-4537-8f38-c059018a3f95] Analyze this code",
       wait_for_response=True  # Parent waits on response queue
   )
   ```

2. **Worker Receives & Processes**: Worker instance automatically extracts correlation ID from message

3. **Worker Replies**: Worker MUST use `reply_to_caller` tool
   ```python
   reply_to_caller(
       instance_id="worker-abc123",
       reply_message="Analysis complete: found 3 security issues, 2 performance bottlenecks",
       correlation_id="2ea0e30e-7ec3-4537-8f38-c059018a3f95"
   )
   ```

4. **Parent Receives**: Reply queued in parent's response queue, `send_to_instance()` returns immediately

**Response Queue Lifecycle**

Response queues are initialized at spawn time (not just when sending messages):

```python
# Response queue created immediately at spawn
supervisor_id = await manager.spawn_instance(
    name="supervisor",
    role="general",
)
# self.response_queues[supervisor_id] = asyncio.Queue()  ✅ Created now

# Supervisor can receive replies from children even before sending any messages
worker_id = await manager.spawn_instance(
    name="worker",
    parent_instance_id=supervisor_id,  # Worker knows its parent
    role="backend_developer"
)

# Worker can immediately use reply_to_caller to supervisor
# Supervisor's response queue already exists ✅
```

**Message Correlation Protocol**

Messages use unique IDs for tracking request-response pairs:

```python
# Format: [MSG:correlation-id] message content

# Parent sends with correlation ID:
# [MSG:2ea0e30e-7ec3-4537-8f38-c059018a3f95] Analyze this code for security issues

# Child extracts correlation ID and replies:
reply_to_caller(
    instance_id="child-abc123",
    reply_message="Security analysis complete:\n- SQL injection risk in line 42\n- XSS vulnerability in template",
    correlation_id="2ea0e30e-7ec3-4537-8f38-c059018a3f95"  # Same ID from parent's message
)

# Parent's send_to_instance() receives the correlated reply immediately
```

**Benefits Over Polling**

| Aspect | Bidirectional (reply_to_caller) | Polling (deprecated) |
|--------|--------------------------------|---------------------|
| **Latency** | Instant (queued immediately) | Delayed (periodic checks) |
| **Efficiency** | Single queue operation | Multiple tmux pane reads |
| **Correlation** | Explicit correlation IDs | Heuristic matching |
| **Reliability** | Guaranteed delivery | May miss rapid outputs |
| **Scalability** | O(1) per message | O(n) polling overhead |

**System Prompt Enforcement**

All supervised instances receive mandatory instructions in their system prompt:

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

**Why Mandatory?**

1. **Performance**: Queue-based delivery is 10-100x faster than tmux pane polling
2. **Reliability**: Explicit message correlation prevents missed replies
3. **Scalability**: Supports hierarchical networks with multiple coordination layers
4. **Debugging**: Communication events logged with full correlation chains

#### Polling for Replies

When children use `reply_to_caller`, their replies are **queued in the parent's response queue**. Parents must actively poll to retrieve these replies using `get_pending_replies`.

**How It Works:**

1. **Child sends reply**: `reply_to_caller()` queues message in `parent.response_queue`
2. **Parent polls**: `get_pending_replies()` drains messages from the queue
3. **Processing**: Parent processes all collected replies

**Two Polling Modes:**

**Non-blocking (wait_timeout=0):**
```python
# Returns immediately with whatever is queued
replies = await get_pending_replies(
    instance_id="supervisor-abc123",
    wait_timeout=0  # Don't wait
)
# Returns [] if queue is empty
```

**Blocking (wait_timeout > 0):**
```python
# Waits up to N seconds for first reply, then drains queue
replies = await get_pending_replies(
    instance_id="supervisor-abc123",
    wait_timeout=30  # Wait up to 30 seconds
)
# Returns [] if timeout expires with no replies
```

**Practical Pattern: Broadcast + Poll**

```python
# 1. Supervisor broadcasts task to all children
await broadcast_to_children(
    parent_id="supervisor-abc123",
    message="Analyze your assigned dataset partition and report findings"
)

# 2. Poll periodically for replies
all_replies = []
timeout = 60
start_time = time.time()

while time.time() - start_time < timeout:
    # Non-blocking poll
    new_replies = await get_pending_replies(
        instance_id="supervisor-abc123",
        wait_timeout=0
    )

    all_replies.extend(new_replies)

    # Check if all children responded
    if len(all_replies) >= 3:  # Expecting 3 children
        break

    await asyncio.sleep(2)  # Poll every 2 seconds

# 3. Process collected replies
for reply in all_replies:
    child_id = reply['sender_id']
    message = reply['reply_message']
    correlation = reply['correlation_id']

    print(f"Child {child_id}: {message}")
```

**When to Poll:**

- **After broadcasting**: Always poll after `broadcast_to_children`
- **Periodic checks**: Poll every few seconds to collect progress updates
- **Completion waiting**: Poll until all expected children have replied
- **Event-driven**: Poll when you expect replies based on coordination logic

**Reply Queue Lifecycle:**

Response queues are created at spawn time and persist until instance termination:

```python
# Queue created when supervisor spawns
supervisor_id = await spawn_instance(name="supervisor", enable_madrox=True)
# self.response_queues[supervisor_id] = asyncio.Queue()  ✅ Created

# Children can immediately send replies
worker_id = await spawn_instance(
    name="worker",
    parent_instance_id=supervisor_id
)

# Worker uses reply_to_caller - queues in supervisor's response queue
# Supervisor polls to retrieve - drains from response queue
```

### File Operations

#### Workspace Isolation

Every instance gets its own isolated directory:

```
/tmp/claude_orchestrator/
├── abc123-instance-id/
│   ├── metadata.json          # Instance configuration
│   ├── workspace/             # Working directory for the instance
│   └── outputs/               # Generated files and artifacts
├── def456-instance-id/
│   └── ...
```

**Benefits:**
- No file conflicts between instances
- Clean separation of concerns
- Easy debugging (inspect per-instance directories)
- Automatic cleanup on termination

#### File Sharing

**Parent-Child Context Sharing**
```python
# Child can read parent's workspace
child_id = await manager.spawn_instance(
    name="child",
    parent_instance_id=parent_id,
)
# Child automatically knows parent's workspace location
```

**Explicit File Paths**
```python
# Pass file paths in messages
await manager.send_to_instance(
    instance_id,
    f"Review the code in {parent_workspace}/src/main.py"
)
```

### Roles & Configuration

#### Predefined Expert Roles

Madrox includes 10 comprehensive role templates (70-120 line prompts each):

| Role | Specialization | Key Capabilities |
|------|----------------|------------------|
| **general** | Versatile assistant | Wide-ranging general knowledge |
| **frontend_developer** | React/TypeScript | UI components, modern web patterns |
| **backend_developer** | Python/FastAPI | APIs, databases, microservices |
| **testing_specialist** | Test automation | Unit tests, integration tests, QA |
| **documentation_writer** | Technical docs | API docs, tutorials, README files |
| **code_reviewer** | Code quality | Best practices, security, maintainability |
| **architect** | System design | Architecture patterns, scalability |
| **debugger** | Problem diagnosis | Root cause analysis, debugging |
| **security_analyst** | Security assessment | Vulnerability scanning, hardening |
| **data_analyst** | Data processing | Analysis, visualization, insights |

**Using Roles**
```python
# Use predefined role
instance_id = await manager.spawn_instance(
    name="backend-expert",
    role="backend_developer"  # Loads comprehensive backend dev prompt
)
```

#### Custom Configuration

**Complete Customization**
```python
# Provide custom system prompt to override role
instance_id = await manager.spawn_instance(
    name="ml-researcher",
    role="general",  # Base role (optional)
    system_prompt="""You are a machine learning researcher specializing in:
    - Transformer architectures and attention mechanisms
    - PyTorch internals and CUDA optimization
    - Latest papers from arXiv (2024-2025)
    - Distributed training strategies"""
)
```

**Modifying Role Prompts**
```bash
# All role prompts stored as text files
ls resources/prompts/

# Edit any role's system prompt
vim resources/prompts/backend_developer.txt

# Changes take effect immediately for new instances
```

#### MCP Server Configuration

Dynamically load tools and capabilities per instance:

**Quick Start with Prebuilt Configs**
```python
from orchestrator.mcp_loader import get_mcp_servers

# Load multiple prebuilt MCP server configs
mcp_servers = get_mcp_servers("playwright", "github", "memory")

instance_id = await manager.spawn_instance(
    name="web-agent",
    role="data_analyst",
    mcp_servers=mcp_servers
)
```

**Available Prebuilt Configs:**
- `playwright` - Browser automation (headless)
- `puppeteer` - Alternative browser automation
- `github` - GitHub API operations
- `filesystem` - File system access
- `sqlite` / `postgres` - Database operations
- `brave-search` - Web search
- `google-drive` - Cloud storage
- `slack` - Team communication
- `memory` - Persistent key-value storage

**Custom MCP Configuration**
```python
mcp_servers = {
    "filesystem": {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
    },
    "database": {
        "transport": "http",
        "url": "http://localhost:5432/mcp"
    }
}

instance_id = await manager.spawn_instance(
    name="data-processor",
    role="data_analyst",
    mcp_servers=mcp_servers
)
```

**Browser Automation Example**
```python
# Spawn instance with Playwright for web scraping
browser_agent = await manager.spawn_instance(
    name="web-scraper",
    role="data_analyst",
    mcp_servers=get_mcp_servers("playwright")
)

# Agent now has browser automation capabilities
await manager.send_to_instance(
    browser_agent,
    "Navigate to https://example.com and extract all article titles"
)
```

## Usage Patterns

### Basic Workflows

#### Single Coordinator Pattern

Use one main instance to coordinate specialized workers:

```python
# Spawn coordinator
coordinator_id = await manager.spawn_instance(
    name="Project Manager",
    role="general",
)

# Coordinator spawns its own team
await manager.send_to_instance(
    coordinator_id,
    """Spawn three specialized instances:
    1. Frontend developer for UI components
    2. Backend developer for API implementation
    3. Testing specialist for test suite

    Pass your instance_id as parent_instance_id for all children."""
)

# Query the network topology
tree = manager.get_instance_tree()
print(tree)
# Output:
# Project Manager (abc123) [idle] (claude)
# ├── frontend-dev (def456) [running] (claude)
# ├── backend-dev (ghi789) [running] (claude)
# └── tester (jkl012) [running] (claude)
```

#### Parallel Task Execution

Execute independent tasks simultaneously:

```python
# Spawn multiple workers
workers = await manager.spawn_multiple_instances([
    {"name": "worker-1", "role": "general"},
    {"name": "worker-2", "role": "general"},
    {"name": "worker-3", "role": "general"}
])

# Assign tasks in parallel
await manager.send_to_multiple_instances([
    {"instance_id": workers[0], "message": "Process dataset chunk 1"},
    {"instance_id": workers[1], "message": "Process dataset chunk 2"},
    {"instance_id": workers[2], "message": "Process dataset chunk 3"}
])
```

#### Sequential Pipeline

Chain tasks through multiple specialized instances:

```python
# Step 1: Research
research_id = await manager.spawn_instance(name="researcher", role="general")
research_result = await manager.send_to_instance(
    research_id,
    "Research best practices for authentication systems"
)

# Step 2: Design (uses research output)
architect_id = await manager.spawn_instance(name="architect", role="architect")
design = await manager.send_to_instance(
    architect_id,
    f"Design an auth system based on this research: {research_result}"
)

# Step 3: Implementation
developer_id = await manager.spawn_instance(name="dev", role="backend_developer")
code = await manager.send_to_instance(
    developer_id,
    f"Implement this design: {design}"
)

# Step 4: Testing
tester_id = await manager.spawn_instance(name="tester", role="testing_specialist")
tests = await manager.send_to_instance(
    tester_id,
    f"Write comprehensive tests for this code: {code}"
)
```

### Advanced Patterns

#### Hierarchical Delegation

Create multi-level organizational structures:

```python
# Level 1: Top coordinator
coordinator_id = await manager.spawn_instance(
    name="CTO",
    role="architect",
)

# Level 2: Team leads (spawned by coordinator)
await manager.send_to_instance(
    coordinator_id,
    """Spawn three team leads:
    1. Frontend Lead - will manage UI developers
    2. Backend Lead - will manage API developers
    3. QA Lead - will manage testers

    Enable Madrox for all leads so they can spawn their own teams."""
)

# Level 3: Individual contributors (spawned by team leads)
# Each lead spawns their own specialized team members

# Result: 3-level hierarchy
# CTO (coordinator)
# ├── Frontend Lead
# │   ├── UI Developer 1
# │   ├── UI Developer 2
# │   └── UX Designer
# ├── Backend Lead
# │   ├── API Developer 1
# │   ├── Database Developer
# │   └── DevOps Engineer
# └── QA Lead
#     ├── Unit Tester
#     └── Integration Tester
```

#### Consensus Building

Get multiple perspectives and synthesize recommendations:

```python
# Spawn multiple experts
experts = await manager.spawn_multiple_instances([
    {"name": "architect-1", "role": "architect"},
    {"name": "architect-2", "role": "architect"},
    {"name": "architect-3", "role": "architect"}
])

# Ask all for opinions
question = "Should we use microservices or a modular monolith?"
responses = await manager.send_to_multiple_instances([
    {"instance_id": expert_id, "message": question}
    for expert_id in experts
])

# Synthesize with coordinator
coordinator_id = await manager.spawn_instance(name="synthesizer", role="architect")
synthesis = await manager.send_to_instance(
    coordinator_id,
    f"""Three experts provided these opinions on architecture:

    Expert 1: {responses[0]}
    Expert 2: {responses[1]}
    Expert 3: {responses[2]}

    Synthesize a balanced recommendation incorporating the best ideas."""
)
```

#### Dynamic Task Interruption & Redirection

Interrupt long-running tasks and redirect without losing context:

```python
# Start expensive task
instance_id = await manager.spawn_instance(name="analyst", role="data_analyst")
await manager.send_to_instance(
    instance_id,
    "Analyze this 10GB dataset in comprehensive detail",
    wait_for_response=False
)

# Realize it's taking too long
await asyncio.sleep(10)

# Interrupt without terminating
result = await manager.interrupt_instance(instance_id)
# Instance shows: "⎿ Interrupted · What should Claude do instead?"

# Redirect to simpler task - context preserved
await manager.send_to_instance(
    instance_id,
    "Instead, just summarize the first 1000 rows"
)
```

#### Multi-Model Orchestration

Combine strengths of different AI models:

```python
# Spawn mixed model network
claude_architect = await manager.spawn_instance(
    name="claude-architect",
    role="architect",
)

codex_coder = await manager.spawn_codex_instance(
    name="codex-optimizer",
    sandbox_mode="workspace-write"
)

# Use Claude for high-level design
architecture = await manager.send_to_instance(
    claude_architect,
    "Design a high-performance data processing pipeline"
)

# Use Codex for implementation
implementation = await manager.send_to_instance(
    codex_coder,
    f"Implement this architecture with optimized code: {architecture}"
)
```

## Use Cases

### Development Scenarios

#### 1. Feature Implementation from Research Paper

**Scenario:** Implement a new algorithm from an academic paper

```python
# Spawn coordinator
coordinator = await manager.spawn_instance(
    name="coordinator",
    role="architect",
)

await manager.send_to_instance(
    coordinator,
    """Implement transformer attention mechanism from this paper.

    Break this down into:
    1. Research instance - analyze paper and extract algorithm details
    2. Design instance - create system architecture
    3. Frontend dev - build visualization UI
    4. Backend dev - implement core algorithm
    5. Codex instance - optimize performance-critical sections
    6. Tester - create comprehensive test suite
    7. Doc writer - generate API documentation

    Coordinate their work and aggregate the final result."""
)
```

**Network Topology:**
```
Coordinator (Architect)
├── Research Instance → analyzes paper
├── Design Instance → creates architecture spec
├── Frontend Dev → builds UI components
├── Backend Dev → implements algorithm
├── Codex Instance → optimizes code
├── Testing Specialist → writes tests
└── Documentation Writer → creates docs
```

#### 2. Reverse Engineering & Keygen Creation

**Scenario:** Analyze a binary and create a working key generator

```python
coordinator = await manager.spawn_instance(
    name="coordinator",
    role="debugger",
)

await manager.send_to_instance(
    coordinator,
    """Reverse engineer this KeygenMe challenge and create a working keygen.

    Orchestrate:
    1. Static Analyzer - strings, imports, symbols
    2. Disassembler - spawns Control Flow + Register Ops specialists
    3. Crypto Analyst - spawns Hash Expert + LCG Expert + Constant Matcher
    4. Algorithm Reconstructor - spawns Math Validator
    5. Python Developer - spawns Code Reviewer
    6. Tester - spawns 3 parallel test runners + fuzzer
    7. Documentation Writer - spawns Technical Writer + Tutorial Writer + Diagram Creator

    Result: Working keygen + 1000+ test validations + comprehensive writeup"""
)
```

**Hierarchical Network (21 instances, 3 levels):**
```
Coordinator (Debugger)
├── Static Analyzer
├── Disassembler
│   ├── Control Flow Analyzer
│   └── Register Operations Tracker
├── Crypto Analyst
│   ├── Hash Function Expert
│   ├── LCG/PRNG Specialist
│   └── Constant Pattern Matcher
├── Algorithm Reconstructor
│   └── Mathematical Validator
├── Python Developer
│   └── Code Reviewer
├── Testing Specialist
│   ├── Test Runner 1
│   ├── Test Runner 2
│   └── Fuzzer
└── Documentation Writer
    ├── Technical Writer
    ├── Tutorial Writer
    └── Diagram Creator
```

#### 3. Codebase Migration

**Scenario:** Migrate a Python codebase to Rust

```python
# Parallel analysis
instances = await manager.spawn_multiple_instances([
    {"name": "python-auditor", "role": "code_reviewer"},
    {"name": "rust-expert", "system_prompt": "Rust systems programming expert"},
    {"name": "migration-planner", "role": "architect"}
])

# Step 1: Audit Python codebase
audit = await manager.send_to_instance(
    instances[0],
    "Audit this Python codebase: architecture, patterns, dependencies"
)

# Step 2: Plan migration strategy
plan = await manager.send_to_instance(
    instances[2],
    f"Create migration plan from Python to Rust: {audit}"
)

# Step 3: Implement in Rust
rust_code = await manager.send_to_instance(
    instances[1],
    f"Implement this Python code in idiomatic Rust: {plan}"
)
```

#### 4. Security Audit & Remediation

**Scenario:** Comprehensive security assessment

```python
security_lead = await manager.spawn_instance(
    name="security-lead",
    role="security_analyst",
)

await manager.send_to_instance(
    security_lead,
    """Perform comprehensive security audit:

    Spawn specialists:
    1. SAST Scanner - static analysis for vulnerabilities
    2. Dependency Auditor - check for vulnerable packages
    3. Auth Specialist - review authentication/authorization
    4. API Security - review REST API endpoints
    5. Data Protection - check for sensitive data exposure
    6. Report Generator - compile findings and remediation steps"""
)
```

### Real-World Examples

#### Example: E-Commerce System Design

```python
# Spawn architect coordinator
architect = await manager.spawn_instance(
    name="System Architect",
    role="architect",
)

await manager.send_to_instance(
    architect,
    """Design a complete e-commerce system.

    Spawn specialist instances:
    1. Backend Developer - User Service (auth + profiles)
    2. Backend Developer - Product Catalog (inventory)
    3. Backend Developer - Order Service (processing)
    4. Backend Developer - Payment Gateway
    5. Frontend Developer - Customer Portal (React)
    6. Frontend Developer - Admin Dashboard (Next.js)
    7. Database Designer - Schema design
    8. Security Analyst - Security assessment
    9. DevOps Engineer - Deployment strategy

    Coordinate their work and produce comprehensive system design."""
)
```

#### Example: API Integration Project

```python
# Spawn integration specialist
specialist = await manager.spawn_instance(
    name="integration-specialist",
    role="backend_developer",
    mcp_servers=get_mcp_servers("playwright", "memory")
)

await manager.send_to_instance(
    specialist,
    """Integrate with Stripe payment API:

    1. Use Playwright to explore Stripe documentation
    2. Design client wrapper with error handling
    3. Implement payment processing endpoints
    4. Create comprehensive test suite
    5. Document integration steps"""
)
```

#### Example: Bug Investigation Workflow

```python
# Spawn debugger coordinator
debugger = await manager.spawn_instance(
    name="bug-hunter",
    role="debugger",
)

await manager.send_to_instance(
    debugger,
    """Investigate intermittent 500 errors in production:

    Spawn specialists:
    1. Log Analyzer - parse and analyze error logs
    2. Code Reviewer - review error-prone endpoints
    3. Database Specialist - check for connection issues
    4. Systems Analyst - review architecture for race conditions
    5. Tester - reproduce the bug reliably

    Coordinate investigation and produce root cause analysis + fix."""
)
```

## Best Practices

### Performance

#### Optimize Spawning

```python
# ❌ Avoid: Sequential spawning
for i in range(5):
    id = await manager.spawn_instance(name=f"worker-{i}")  # Slow

# ✅ Better: Parallel spawning
instances = await manager.spawn_multiple_instances([
    {"name": f"worker-{i}"} for i in range(5)
])  # Fast

# ✅ Best: Non-blocking parallel spawning
instances = await manager.spawn_multiple_instances([
    {"name": f"worker-{i}", "wait_for_ready": False} for i in range(5)
])  # Fastest - returns IDs immediately
```

#### Batch Operations

```python
# ❌ Avoid: Sequential messaging
for instance_id in instances:
    await manager.send_to_instance(instance_id, message)  # Slow

# ✅ Better: Parallel messaging
await manager.send_to_multiple_instances([
    {"instance_id": id, "message": message} for id in instances
])  # Fast

# ✅ Best: Broadcast for common message
await manager.broadcast_to_children(
    parent_id=parent_id,
    message=message
)  # Fastest for parent-child messaging
```

#### Resource Management

```python
# Set resource limits to prevent runaway costs
instance_id = await manager.spawn_instance(
    name="limited-instance",
    role="general",
    max_total_tokens=50000,      # Token limit
    max_cost=10.0,               # Dollar limit
    timeout_minutes=30           # Time limit
)

# Monitor usage
status = manager.get_instance_status(instance_id)
print(f"Tokens: {status['total_tokens_used']}")
print(f"Cost: ${status['total_cost']:.4f}")
print(f"Uptime: {status['uptime_seconds']}s")
```

### Reliability

#### Error Handling

```python
# Always wrap instance operations in try-except
try:
    response = await manager.send_to_instance(
        instance_id,
        message,
        timeout_seconds=60
    )
except asyncio.TimeoutError:
    # Handle timeout
    await manager.interrupt_instance(instance_id)
    response = await manager.send_to_instance(
        instance_id,
        "Provide a quick summary instead"
    )
except ValueError as e:
    # Handle instance not found
    print(f"Instance error: {e}")
```

#### Health Monitoring

```python
# Check instance health before sending tasks
status = manager.get_instance_status(instance_id)

if status["state"] == "terminated":
    # Respawn if needed
    instance_id = await manager.spawn_instance(name="new-instance")
elif status["state"] == "busy":
    # Wait or interrupt
    await manager.interrupt_instance(instance_id)
```

#### Graceful Cleanup

```python
# Always clean up instances when done
try:
    # Do work
    result = await manager.send_to_instance(instance_id, task)
finally:
    # Ensure cleanup even if error occurs
    await manager.terminate_instance(instance_id)
```

### Coordination

#### Clear Role Assignment

```python
# ✅ Good: Specific roles and instructions
architect = await manager.spawn_instance(
    name="System Architect",
    role="architect",
    system_prompt="Focus on microservices design patterns"
)

# ❌ Avoid: Vague general instances
instance = await manager.spawn_instance(name="worker")  # Unclear purpose
```

#### Structured Communication

```python
# ✅ Good: Clear, actionable messages with context
await manager.send_to_instance(
    instance_id,
    """Design a user authentication system with these requirements:
    - OAuth 2.0 + JWT tokens
    - Multi-factor authentication support
    - Session management with Redis

    Provide: architecture diagram, API endpoints, security considerations"""
)

# ❌ Avoid: Vague requests
await manager.send_to_instance(instance_id, "Design auth")  # Too vague
```

#### Network Topology Awareness

```python
# Query network structure before making decisions
tree = manager.get_instance_tree()
print(tree)

# Check parent-child relationships
children = manager.get_children(parent_id)

# Broadcast to appropriate level
if len(children) > 0:
    await manager.broadcast_to_children(parent_id, message)
else:
    # No children yet, spawn some first
    await manager.send_to_instance(parent_id, "Spawn 3 workers")
```

#### Cost-Effective Model Selection

```python
# Use Claude for complex reasoning
architect = await manager.spawn_instance(
    name="architect",
    role="architect"  # Uses Claude Sonnet/Opus
)

# Use Codex for pure implementation
coder = await manager.spawn_codex_instance(
    name="coder",
    sandbox_mode="workspace-write"  # Codex is faster/cheaper for code
)

# Match model to task complexity
await manager.send_to_instance(
    architect,
    "Design the entire system architecture"  # Complex reasoning
)

await manager.send_to_instance(
    coder,
    "Implement these 10 CRUD endpoints"  # Straightforward implementation
)
```

## Examples

### Complete Workflow: Task Management App

```python
import asyncio
from orchestrator.instance_manager import TmuxInstanceManager

async def build_task_app():
    manager = TmuxInstanceManager()

    # Phase 1: Architecture
    architect = await manager.spawn_instance(
        name="architect",
        role="architect"
    )

    architecture = await manager.send_to_instance(
        architect,
        """Design a task management application with:
        - User authentication
        - Task CRUD operations
        - Task categories and tags
        - Due date tracking
        - RESTful API

        Provide: data models, API endpoints, tech stack"""
    )

    # Phase 2: Parallel Development
    developers = await manager.spawn_multiple_instances([
        {"name": "frontend-dev", "role": "frontend_developer"},
        {"name": "backend-dev", "role": "backend_developer"},
        {"name": "db-designer", "role": "data_analyst"}
    ])

    results = await manager.send_to_multiple_instances([
        {
            "instance_id": developers[0],
            "message": f"Build React UI based on: {architecture}"
        },
        {
            "instance_id": developers[1],
            "message": f"Implement FastAPI backend: {architecture}"
        },
        {
            "instance_id": developers[2],
            "message": f"Design PostgreSQL schema: {architecture}"
        }
    ])

    # Phase 3: Testing
    tester = await manager.spawn_instance(
        name="tester",
        role="testing_specialist"
    )

    tests = await manager.send_to_instance(
        tester,
        f"""Create comprehensive test suite:
        - Unit tests for all endpoints
        - Integration tests for user flows
        - UI component tests

        Based on: {results}"""
    )

    # Phase 4: Documentation
    doc_writer = await manager.spawn_instance(
        name="doc-writer",
        role="documentation_writer"
    )

    docs = await manager.send_to_instance(
        doc_writer,
        f"""Generate complete documentation:
        - API reference
        - Setup guide
        - User manual

        Based on: {results}"""
    )

    # Cleanup
    for instance_id in [architect, *developers, tester, doc_writer]:
        await manager.terminate_instance(instance_id)

    return {
        "architecture": architecture,
        "implementation": results,
        "tests": tests,
        "documentation": docs
    }

# Run the workflow
result = asyncio.run(build_task_app())
```

### Network Visualization

```python
# Get complete instance network topology
tree = manager.get_instance_tree()

# Output:
"""
Project Manager (abc123-def456) [idle] (claude)
├── Frontend Lead (def456-abc123) [running] (claude)
│   ├── UI Developer 1 (ghi789-jkl012) [busy] (claude)
│   ├── UI Developer 2 (mno345-pqr678) [idle] (claude)
│   └── UX Designer (stu901-vwx234) [running] (claude)
├── Backend Lead (yza567-bcd890) [idle] (claude)
│   ├── API Developer (efg123-hij456) [busy] (claude)
│   ├── Database Developer (klm789-nop012) [running] (codex)
│   └── DevOps Engineer (qrs345-tuv678) [idle] (claude)
└── QA Lead (wxy901-zab234) [busy] (claude)
    ├── Unit Tester (cde567-fgh890) [running] (claude)
    └── Integration Tester (ijk123-lmn456) [running] (claude)
"""
```

### Interrupt & Redirect Pattern

```python
# Start long task
worker = await manager.spawn_instance(name="worker", role="general")

await manager.send_to_instance(
    worker,
    "Count slowly to 1000, one number at a time",
    wait_for_response=False
)

# Wait for some progress
await asyncio.sleep(5)

# Interrupt mid-task
await manager.interrupt_instance(worker)
# Worker shows: "⎿ Interrupted · What should Claude do instead?"

# Verify context preserved
response = await manager.send_to_instance(
    worker,
    "What number did you reach before interruption?"
)
# Worker correctly recalls counting task

# New task with full context
await manager.send_to_instance(
    worker,
    "Now count backwards from that number to zero"
)
```

### Multi-Model Coordination

```python
# Architecture decision (Claude - better reasoning)
claude_architect = await manager.spawn_instance(
    name="architect",
    role="architect"
)

design = await manager.send_to_instance(
    claude_architect,
    "Design a high-performance caching layer"
)

# Implementation (Codex - faster for boilerplate)
codex_dev = await manager.spawn_codex_instance(
    name="coder",
    sandbox_mode="workspace-write"
)

implementation = await manager.send_to_instance(
    codex_dev,
    f"Implement this caching design in Python: {design}"
)

# Code review (Claude - better judgment)
claude_reviewer = await manager.spawn_instance(
    name="reviewer",
    role="code_reviewer"
)

review = await manager.send_to_instance(
    claude_reviewer,
    f"Review this implementation for best practices: {implementation}"
)
```

---

## Related Documentation

- [System Architecture](DESIGN.md) - Technical design and MCP protocol details
- [API Reference](API_ENDPOINTS.md) - HTTP REST API endpoints
- [Logging & Audit](LOGGING.md) - Monitoring and debugging
- [Interruption Feature](INTERRUPT_FEATURE.md) - Task interruption details
- [Bidirectional Messaging](BIDIRECTIONAL_MESSAGING_DESIGN.md) - Communication protocol
- [MCP Configuration](MCP_SERVER_CONFIGURATION.md) - Custom tool loading
- [Stress Testing](STRESS_TESTING.md) - Production validation scenarios

---

**Madrox enables enterprise-grade multi-agent orchestration with hierarchical coordination, multi-model support, and production-ready monitoring.**
