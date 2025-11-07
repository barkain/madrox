#!/usr/bin/env python3
"""Launcher script for Claude Orchestrator MCP Server.

Supports two transport modes:
1. HTTP (SSE): For Claude Code clients - starts FastAPI server on port 8001
2. STDIO: For Codex CLI clients - communicates via stdin/stdout

Transport auto-detection:
- If stdin is a terminal (isatty), start HTTP server
- If stdin is piped, start STDIO server
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def detect_transport_mode() -> str:
    """Detect which transport mode to use.

    Returns:
        "http" for terminal input (Claude Code), "stdio" for piped input (Codex CLI)
    """
    # Environment variable takes precedence
    env_transport = os.getenv("MADROX_TRANSPORT")
    if env_transport:
        return env_transport.lower()

    # Check if stdin is a terminal
    # Terminal (isatty=True) -> HTTP server
    # Piped (isatty=False) -> STDIO server
    if sys.stdin.isatty():
        return "http"
    else:
        return "stdio"


async def start_http_server(config):
    """Start HTTP/SSE server for Claude Code clients."""
    from src.orchestrator.server import ClaudeOrchestratorServer

    print(f"Starting Claude Orchestrator (HTTP) on {config.server_host}:{config.server_port}")
    print(f"Workspace: {config.workspace_base_dir}")
    print(f"Max instances: {config.max_concurrent_instances}")
    print("Transport: HTTP/SSE (Claude Code)")

    server = ClaudeOrchestratorServer(config)
    await server.start_server()


async def start_stdio_server(config):
    """Start STDIO server for Codex CLI clients."""
    from src.orchestrator.mcp_server import OrchestrationMCPServer

    print("Starting Claude Orchestrator (STDIO)", file=sys.stderr)
    print(f"Workspace: {config.workspace_base_dir}", file=sys.stderr)
    print(f"Max instances: {config.max_concurrent_instances}", file=sys.stderr)
    print("Transport: STDIO (Codex CLI)", file=sys.stderr)

    # Create MCP server instance
    mcp_server = OrchestrationMCPServer(config)

    try:
        # Get FastMCP instance and run with STDIO transport
        mcp_instance = await mcp_server.run()

        # Use FastMCP's built-in stdio transport
        await mcp_instance.run_stdio_async()
    finally:
        # Clean up shared resources on exit
        if hasattr(mcp_server, "manager"):
            await mcp_server.manager.shutdown()


def main():
    """Main entry point with transport auto-detection."""
    try:
        from src.orchestrator.simple_models import OrchestratorConfig

        # Load configuration from environment
        config = OrchestratorConfig(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            server_host=os.getenv("ORCHESTRATOR_HOST", "localhost"),
            server_port=int(os.getenv("ORCHESTRATOR_PORT", "8001")),
            max_concurrent_instances=int(os.getenv("MAX_INSTANCES", "10")),
            workspace_base_dir=os.getenv("WORKSPACE_DIR", "/tmp/claude_orchestrator"),
            log_dir=os.getenv("LOG_DIR", "/tmp/madrox_logs"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            artifacts_dir=os.getenv("ARTIFACTS_DIR", "/tmp/madrox_logs/artifacts"),
            preserve_artifacts=os.getenv("PRESERVE_ARTIFACTS", "true").lower() == "true",
        )

        # Detect transport mode (environment variable checked inside detect_transport_mode)
        transport = detect_transport_mode()

        if transport == "stdio":
            asyncio.run(start_stdio_server(config))
        else:
            asyncio.run(start_http_server(config))

    except ImportError as e:
        print(f"Import error: {e}", file=sys.stderr)
        print("Please ensure dependencies are installed:", file=sys.stderr)
        print("uv sync --all-groups", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error starting server: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
