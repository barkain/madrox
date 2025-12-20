# Quick Setup for Codex CLI

## One-Command Installation

To add Madrox MCP server to your Codex CLI configuration, simply run from the Madrox directory:

```bash
codex mcp add madrox $(pwd)/madrox-mcp
```

Or with the full path:

```bash
codex mcp add madrox /path/to/madrox/madrox-mcp
```

This uses a wrapper script that handles the proper environment setup.

## Verify Installation

After adding, you can verify the server is available:

```bash
codex mcp list
```

You should see `madrox` in the list of available MCP servers.

## Usage

Once added, you can use Madrox commands in Codex:

```
"Spawn a Claude instance named 'helper' with role 'general'"
"Send 'hello world' to instance helper"
"Get status of all instances"
"Terminate instance helper"
```

## Environment Variables (Optional)

If you need to customize settings, you can set environment variables before running Codex:

```bash
export MAX_INSTANCES=20
export WORKSPACE_DIR=/custom/path/to/workspaces
export LOG_LEVEL=DEBUG
codex
```

## Troubleshooting

If the server doesn't work:

1. Ensure uv is installed: `uv --version` (or check `~/.local/bin/uv --version`)
2. Ensure dependencies are installed: `cd /path/to/madrox && uv sync`
3. Test the server directly from the Madrox directory:
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | \
   ./madrox-mcp
   ```

## Remove Server

To remove the Madrox server from Codex:

```bash
codex mcp remove madrox
```