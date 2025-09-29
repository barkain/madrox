# Madrox Stdio MCP Server for OpenAI Codex CLI

This document describes how to set up and use the Madrox MCP server with OpenAI's Codex CLI via the stdio transport protocol.

## Overview

The stdio MCP server (`run_stdio_server.py`) implements the Model Context Protocol (MCP) using JSON-RPC 2.0 over standard input/output streams. This allows Codex CLI to spawn and manage multiple Claude instances through Madrox.

## Features

- **JSON-RPC 2.0 Protocol**: Full compliance with MCP specification
- **Stdio Transport**: Communicates via stdin/stdout for local integration
- **Six Core Tools**:
  - `spawn_claude`: Create new Claude instances with specific roles
  - `send_to_instance`: Send messages to running instances
  - `get_instance_output`: Retrieve instance outputs
  - `coordinate_instances`: Orchestrate multiple instances for complex tasks
  - `terminate_instance`: Clean up instances
  - `get_instance_status`: Monitor instance states

## Installation

### 1. Prerequisites

Ensure you have the Madrox dependencies installed:

```bash
cd /path/to/madrox
uv sync --all-groups
```

### 2. Configure Codex CLI

Copy the provided configuration to your Codex config directory:

```bash
# Create Codex config directory if it doesn't exist
mkdir -p ~/.codex

# Copy or merge the configuration
cp codex-config.toml ~/.codex/config.toml
# Or if you have an existing config, merge the [mcp_servers.madrox] section
```

### 3. Update Configuration Path

Edit `~/.codex/config.toml` and update the path to your Madrox installation:

```toml
[mcp_servers.madrox]
command = "python"
args = ["/YOUR/PATH/TO/madrox/run_stdio_server.py"]  # Update this path
```

## Usage

### Testing the Server Standalone

You can test the server directly using JSON-RPC commands:

```bash
# Test initialization
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python run_stdio_server.py

# List available tools
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | python run_stdio_server.py

# Get instance status
echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_instance_status","arguments":{}}}' | python run_stdio_server.py
```

### Using with Codex CLI

Once configured, you can use natural language commands in Codex:

```bash
# Start Codex
codex

# Example commands:
"Spawn a Claude instance named 'analyzer' with role 'data_scientist'"
"Send 'analyze the sales data trends' to the analyzer instance"
"Spawn another instance called 'visualizer' with role 'frontend_developer'"
"Coordinate analyzer and visualizer to create a data dashboard"
```

## Configuration Options

Environment variables can be set in the config file or when running directly:

- `MAX_INSTANCES`: Maximum concurrent Claude instances (default: 10)
- `WORKSPACE_DIR`: Base directory for instance workspaces (default: /tmp/claude_orchestrator)
- `LOG_LEVEL`: Logging verbosity (default: INFO)

## Architecture

```
Codex CLI <--> JSON-RPC/stdio <--> Madrox Stdio Server <--> Instance Manager <--> Claude CLI Processes
```

The stdio server:
1. Reads JSON-RPC requests from stdin
2. Processes them through the Instance Manager
3. Returns JSON-RPC responses via stdout
4. Logs to stderr to avoid interfering with the protocol

## Available Roles

When spawning instances, you can specify these predefined roles:

- `general`: General purpose assistant
- `architect`: System design and architecture
- `frontend_developer`: React/Vue/Angular expertise
- `backend_developer`: API and server development
- `testing_specialist`: Testing and quality assurance
- `documentation_writer`: Technical documentation
- `code_reviewer`: Code review and best practices
- `debugger`: Bug fixing and troubleshooting
- `security_analyst`: Security analysis
- `data_analyst`: Data analysis and visualization

## Troubleshooting

### Server not responding
- Check that Python can find the Madrox modules
- Ensure the virtual environment is activated or dependencies are installed
- Check stderr output for error messages: `python run_stdio_server.py 2>error.log`

### Codex can't find the server
- Verify the path in `~/.codex/config.toml` is absolute and correct
- Ensure the script is executable: `chmod +x run_stdio_server.py`
- Check Codex logs for MCP server initialization errors

### Instance spawn failures
- Verify Claude CLI is installed and authenticated
- Check that the workspace directory is writable
- Monitor the Instance Manager logs in stderr output

## Protocol Details

The server implements the following MCP methods:

- `initialize`: Establishes server capabilities
- `initialized`: Acknowledges initialization (notification)
- `tools/list`: Returns available tools with schemas
- `tools/call`: Executes a specific tool with arguments

Each tool returns structured JSON responses with success status and relevant data.

## Example Session

```json
// Request: Initialize
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}

// Response: Server info and capabilities
{"jsonrpc":"2.0","id":1,"result":{"capabilities":{"tools":{"listChanged":true}},"serverInfo":{"name":"madrox","version":"1.0.0"}}}

// Request: Spawn instance
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"spawn_claude","arguments":{"name":"helper","role":"general"}}}

// Response: Instance created
{"jsonrpc":"2.0","id":2,"result":[{"type":"text","text":"{\"success\":true,\"instance_id\":\"inst_123\",\"name\":\"helper\"}"}]}
```

## Security Considerations

- The server runs with the permissions of the user executing it
- Instance workspaces are isolated in separate directories
- All Claude CLI processes are properly terminated on server shutdown
- Logging to stderr prevents protocol contamination

## Performance

- Supports up to 10 concurrent instances by default (configurable)
- Each instance runs as a separate Claude CLI process
- JSON-RPC requests are processed sequentially
- Async operations allow non-blocking instance management