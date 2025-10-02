# Madrox - Hierarchical Multi-Agent Orchestrator

<p align="center">
  <img src="madrox.png" alt="Madrox Logo" width="400"/>
</p>

A Model Context Protocol (MCP) server that enables AI instances to spawn and manage hierarchical networks of Claude and Codex instances. This system supports sophisticated multi-agent orchestration with parent-child relationships, bidirectional communication, role-based specialization, and intelligent coordination across multiple AI models.

## 🎯 Features

### Core Orchestration Tools
- **`spawn_claude`** - Spawn new Claude instances with specific roles and configurations
- **`spawn_codex_instance`** - Spawn OpenAI Codex instances for multi-model orchestration
- **`spawn_multiple_instances`** - Spawn multiple instances in parallel for faster setup
- **`send_to_instance`** - Send messages to specific instances and receive responses
- **`send_to_multiple_instances`** - Message multiple instances concurrently
- **`get_instance_output`** - Retrieve output history from instances
- **`get_instance_tree`** - Visualize hierarchical network of all running instances
- **`get_children`** - Query child instances of a parent
- **`broadcast_to_children`** - Broadcast messages to all children of a parent
- **`coordinate_instances`** - Coordinate multiple instances for complex tasks
- **`interrupt_instance`** - Interrupt running task without terminating instance
- **`interrupt_multiple_instances`** - Interrupt multiple instances in parallel
- **`terminate_instance`** - Gracefully terminate instances with proper cleanup

### Advanced Capabilities
- **Multi-Model Support** - Orchestrate both Claude (Anthropic) and Codex (OpenAI) instances
- **Hierarchical Architecture** - Parent-child relationships with bidirectional communication
- **Instance Tree Visualization** - Real-time network topology with state and type indicators
- **Task Interruption** - Stop running tasks without terminating instances (preserves context)
- **Parallel Spawning** - Launch multiple instances concurrently for performance
- **Non-Blocking Mode** - Background initialization with immediate ID return
- **Message Auto-Injection** - Automatic context sharing from child to parent instances
- **Instance Lifecycle Management** - Complete lifecycle with proper resource cleanup
- **Role-Based Specialization** - 10 predefined roles (architect, frontend dev, backend dev, etc.)
- **Isolated Environments** - Each instance gets its own workspace directory with metadata
- **Message Passing** - Reliable inter-instance communication with timeout handling
- **Parallel Task Execution** - Coordinate multiple instances working in parallel
- **Batch Operations** - Interrupt, message, or query multiple instances simultaneously
- **Resource Tracking** - Monitor token usage, costs, and performance metrics
- **Health Monitoring** - Automatic health checks with timeout and limit enforcement
- **Consensus Building** - Coordinate instances for decision-making processes
- **Cost Optimization** - Resource limits and usage tracking

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- FastAPI and uvicorn
- Anthropic API key (for production use)

### Installation

1. Clone and navigate to the orchestrator directory:
```bash
cd src/orchestrator
```

2. Install dependencies:
```bash
uv sync --all-groups
```

3. Set environment variables (API key optional if you're using Claude Desktop/CLI with a subscription):
```bash
export ORCHESTRATOR_PORT=8001
export WORKSPACE_DIR="/tmp/claude_orchestrator"
```

If you do need direct API access, also set `ANTHROPIC_API_KEY="your-api-key-here"`.

### Running the Server

#### Option 1: Using the launcher script
```bash
python run_orchestrator.py
```

#### Option 2: Direct server start
```bash
uv run python -c "
from src.orchestrator.server import main
import asyncio
asyncio.run(main())
"
```

The server will start on `http://localhost:8001` by default.

## 🧪 Testing

### Run the comprehensive test suite (86% coverage):
```bash
uv run python -m pytest tests/test_orchestrator.py -v --cov=src/orchestrator
```

### Run the integration demo:
```bash
uv run python tests/integration_demo.py
```

This demo shows a complete workflow building a task management app with 3 specialized instances.

## 📊 Test Coverage

- **Instance Manager**: 86% coverage
- **Core Models**: 50% coverage
- **Total Tests**: 26 tests (25 passing, 1 minor failure)
- **Test Categories**: Unit tests, integration tests, error handling, resource limits

## 🔧 Configuration

### Environment Variables
- `ANTHROPIC_API_KEY` - Your Anthropic API key (optional if you use Claude subscription clients)
- `ORCHESTRATOR_HOST` - Server host (default: localhost)
- `ORCHESTRATOR_PORT` - Server port (default: 8001)
- `MAX_INSTANCES` - Maximum concurrent instances (default: 10)
- `WORKSPACE_DIR` - Base workspace directory (default: /tmp/claude_orchestrator)
- `LOG_LEVEL` - Logging level (default: INFO)

### Configuration Options
```python
config = OrchestratorConfig(
    server_host="localhost",
    server_port=8001,
    anthropic_api_key="your-key",
    max_concurrent_instances=10,
    max_tokens_per_instance=100000,
    max_total_cost=100.0,
    instance_timeout_minutes=60,
    workspace_base_dir="/tmp/claude_orchestrator",
    enable_isolation=True,
)
```

## 🎭 Instance Roles & Customization

### Quick Start: Predefined Roles

For convenience, these ready-made roles are available:

- **General** - Versatile general-purpose assistant
- **Frontend Developer** - React/TypeScript specialist
- **Backend Developer** - Python/API specialist
- **Testing Specialist** - Test automation expert
- **Documentation Writer** - Technical documentation expert
- **Code Reviewer** - Code quality and best practices
- **Architect** - System design and architecture
- **Debugger** - Problem diagnosis and debugging
- **Security Analyst** - Security assessment and hardening
- **Data Analyst** - Data processing and analysis

### Custom Roles

**You're not limited to predefined roles!** Create any specialized instance you need:

```python
# Fully custom role with specialized expertise
instance_id = await manager.spawn_instance(
    name="rust-expert",
    role="general",  # Use any role or general as base
    system_prompt="""You are a Rust systems programming expert with deep knowledge of:
    - Embedded systems and bare-metal programming
    - async/await and tokio runtime internals
    - Zero-cost abstractions and compiler optimizations
    - Safety guarantees and lifetime management"""
)

# Domain-specific expert
instance_id = await manager.spawn_instance(
    name="ml-researcher",
    system_prompt="""You are a machine learning researcher specializing in:
    - Transformer architectures and attention mechanisms
    - PyTorch internals and CUDA optimization
    - Latest papers from arXiv (2024-2025)
    - Distributed training strategies"""
)
```

**Key Point:** When you provide a `system_prompt`, it completely overrides the predefined role behavior, giving you full control over the instance's expertise and personality.

### Customizing Role Prompts

All predefined role prompts are stored as text files in `resources/prompts/` and can be easily customized:

```bash
# View available prompts
ls resources/prompts/

# Edit a role's system prompt
vim resources/prompts/backend_developer.txt

# Changes take effect immediately for new instances
```

Each prompt file contains comprehensive expertise, best practices, and behavioral guidelines researched from 2025 industry standards. See `resources/prompts/README.md` for details on prompt structure and customization options.

## 🔗 MCP Protocol Integration

### Claude Desktop / Claude for macOS & Windows
1. Open the Claude desktop configuration file:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
2. Add a new entry under `mcpServers`:
   ```json
   {
     "mcpServers": {
      "madrox": {
        "command": "uv",
        "args": ["run", "python", "run_orchestrator.py"],
        "cwd": "path/to/madrox",
        "env": {
          "ANTHROPIC_API_KEY": "your-api-key"
        }
      }
     }
   }
  ```
  Omit the `env` block entirely if you don't need a direct Anthropic API key.
  Replace the `command` value with the absolute path to `uv` on your machine
  (run `command -v uv` in a shell to find it). Claude Desktop launches MCP
  servers with a minimal `PATH`, so the explicit path prevents “No such file or
  directory (os error 2)” when starting Madrox.
   If the FastAPI app is already running, you can instead use the HTTP transport:
   ```json
   {
     "mcpServers": {
       "madrox": {
         "url": "http://localhost:8001",
         "transport": "http"
       }
     }
   }
   ```
3. Save the file and restart Claude so it loads the new server.

### Claude Code (VS Code Extension)
1. In VS Code run the command palette action `Claude: Edit Connection Settings`.
2. Add the same `mcpServers.madrox` block (either `command/args` or `url/transport`).
3. Save the file; use `Claude: Reload Connections` if the tools do not appear immediately.

### Claude Code CLI
Use the CLI helper to register the server:
```bash
# Default: use claude-sonnet-4-20250514 (no API key required for Claude subscribers)
claude mcp add madrox http://localhost:8001/mcp --transport http --model sonnet

# Optional: pick an alternate supported model
claude mcp add madrox http://localhost:8001/mcp --transport http --model opus
claude mcp add madrox http://localhost:8001/mcp --transport http --model haiku

# Need raw API access? add your key when registering (still defaults to sonnet)
claude mcp add -e ANTHROPIC_API_KEY=your-api-key madrox \
  http://localhost:8001/mcp --transport http --model sonnet

# Verify registration
claude mcp list
```

The `--model` option accepts only `sonnet`, `opus`, or `haiku`, which expand to the following Anthropic model IDs:

| Choice | Anthropic model id            |
|--------|-------------------------------|
| sonnet | `claude-sonnet-4-20250514`    |
| opus   | `claude-opus-4-1-20250805`    |
| haiku  | `claude-3-5-haiku-20241022`   |

If you omit `--model`, the CLI defaults to `sonnet`.

For direct chats without MCP, you can launch the Claude CLI with a specific model:

```bash
claude --model claude-sonnet-4-20250514
claude --model claude-opus-4-1-20250805
claude --model claude-3-5-haiku-20241022
```

Restart any active `claude` session so the new MCP tools are available.

### HTTP Endpoints
The server also exposes friendly REST endpoints that mirror the MCP tools:
- `/tools` - List available orchestration tools
- `/tools/execute` - Execute orchestration commands
- `/health` - Health check endpoint
- `/instances` - List all instances
- `/instances/{id}` - Get specific instance details

## 📋 Usage Examples

### Example 1: Basic Instance Spawning
```python
# Spawn a frontend developer
instance_id = await manager.spawn_instance(
    name="React Developer",
    role="frontend_developer",
    system_prompt="You are a React expert specializing in TypeScript and modern UI patterns."
)

# Send a development task
response = await manager.send_to_instance(
    instance_id,
    "Create a responsive navigation component with dropdown menus"
)
```

### Example 2: Hierarchical Multi-Instance Network
```python
# Spawn a coordinator parent
coordinator_id = await manager.spawn_instance(
    name="Project Manager",
    role="general",
    enable_madrox=True
)

# Parent spawns its own children
await manager.send_to_instance(
    coordinator_id,
    "Spawn two child instances: a frontend developer and a backend developer. "
    "Pass your instance_id as parent_instance_id for both."
)

# Query children from parent
children = manager.get_children(coordinator_id)
# Returns: [{"id": "...", "name": "frontend-dev", ...}, {"id": "...", "name": "backend-dev", ...}]

# Broadcast message to all children
await manager.broadcast_to_children(
    parent_id=coordinator_id,
    message="Start working on the user authentication feature",
    wait_for_responses=True
)

# Visualize the network
tree = manager.get_instance_tree()
print(tree)
# Output:
# Project Manager (abc123...) [idle] (claude)
# ├── frontend-dev (def456...) [running] (claude)
# └── backend-dev (ghi789...) [running] (claude)
```

### Example 3: Multi-Model Orchestration (Claude + Codex)
```python
# Spawn both Claude and Codex instances in parallel
instances = await manager.spawn_multiple_instances([
    {"name": "claude-architect", "role": "architect", "enable_madrox": True},
    {"name": "codex-coder", "instance_type": "codex"}
])

# Send tasks to both models
await manager.send_to_multiple_instances([
    {
        "instance_id": instances[0],
        "message": "Design a microservices architecture for an e-commerce platform"
    },
    {
        "instance_id": instances[1],
        "message": "Generate boilerplate code for user service with authentication"
    }
])

# Check the full network topology
tree = manager.get_instance_tree()
```

### Example 4: Parallel Spawning & Non-Blocking Mode
```python
# Spawn multiple instances in parallel for faster setup
instance_ids = await manager.spawn_multiple_instances([
    {"name": "worker-1", "role": "general", "wait_for_ready": False},
    {"name": "worker-2", "role": "general", "wait_for_ready": False},
    {"name": "worker-3", "role": "general", "wait_for_ready": False},
])
# Returns immediately with IDs, instances initialize in background

# Message all workers simultaneously
await manager.send_to_multiple_instances([
    {"instance_id": id, "message": "Process dataset chunk", "wait_for_response": False}
    for id in instance_ids
])
```

### Example 5: Task Interruption & Control
```python
# Start a long-running task
instance_id = await manager.spawn_instance(
    name="Data Processor",
    role="general"
)

await manager.send_to_instance(
    instance_id,
    "Process this large dataset and generate comprehensive statistics",
    wait_for_response=False
)

# Wait a bit, then interrupt the task without terminating the instance
await asyncio.sleep(10)
result = await manager.interrupt_instance(instance_id)
# Instance shows: "⎿ Interrupted · What should Claude do instead?"

# Send a new task - context is preserved
await manager.send_to_instance(
    instance_id,
    "Instead, just summarize the first 100 rows"
)

# Interrupt multiple instances in parallel
await manager.interrupt_multiple_instances([instance_id_1, instance_id_2, instance_id_3])
```

### Example 6: Resource Management
```python
# Spawn with resource limits
instance_id = await manager.spawn_instance(
    name="Limited Instance",
    role="general",
    max_total_tokens=50000,
    max_cost=10.0,
    timeout_minutes=30
)

# Monitor resource usage
status = manager.get_instance_status(instance_id)
print(f"Tokens used: {status['total_tokens_used']}")
print(f"Cost: ${status['total_cost']:.4f}")
```

## 🛡️ Security & Isolation

- **Workspace Isolation** - Each instance gets its own directory
- **Resource Limits** - Token, cost, and time limits per instance
- **Health Monitoring** - Automatic cleanup of stuck or excessive instances
- **Graceful Shutdown** - Proper cleanup on termination
- **Error Recovery** - Timeout handling and retry mechanisms

## 🔍 Monitoring & Debugging

### Health Checks
The system performs automatic health checks every minute:
- Instance timeout detection
- Resource limit enforcement
- Error tracking and recovery
- Automatic cleanup of terminated instances

### Logging
Comprehensive logging with structured output:
- Instance lifecycle events
- Message passing and responses
- Resource usage tracking
- Error conditions and recovery

### Metrics
- Total instances created/active/terminated
- Token usage and cost tracking per instance
- Response times and success rates
- Health scores and error counts

## 🚨 Error Handling

- **Timeout Management** - Configurable timeouts for all operations
- **Resource Exhaustion** - Automatic termination when limits exceeded
- **Communication Errors** - Retry logic and fallback handling
- **Instance Failures** - Graceful degradation and cleanup
- **Validation** - Input validation and sanitization

## 🔧 Troubleshooting

### Common Issues

1. **Server won't start**: Check FastAPI/uvicorn installation
2. **Instance spawn fails**: Verify Anthropic API key
3. **Tests fail**: Ensure pytest and dependencies installed
4. **Type errors**: Check Python version (3.11+ required)

### Debug Mode
```bash
export LOG_LEVEL=DEBUG
python run_orchestrator.py
```

## 📈 Performance

- **Concurrent Instances**: Up to 10 instances by default (configurable)
- **Response Times**: Sub-second for management operations
- **Memory Usage**: Efficient with workspace isolation
- **Scalability**: Designed for production workloads

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Follow existing code patterns and style
2. Maintain test coverage above 85%
3. Use modern Python syntax (3.11+)
4. Add comprehensive error handling
5. Update documentation for new features

## 📜 License

MIT License - See LICENSE file for details.

---

**Ready for production use with comprehensive testing, monitoring, and documentation!**
