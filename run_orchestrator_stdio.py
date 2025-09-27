#!/usr/bin/env python3
"""Launch the Claude Orchestrator MCP server over stdio."""

import asyncio
import os
import sys
from pathlib import Path

# Ensure `src` is importable when run from outside the project root.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mcp.server import stdio
from mcp.server.lowlevel.server import NotificationOptions
from mcp.server.models import InitializationOptions

from src.orchestrator.mcp_server import OrchestrationMCPServer
from src.orchestrator.simple_models import OrchestratorConfig


async def main() -> None:
    """Configure and run the orchestrator MCP server via stdio."""
    config = OrchestratorConfig(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        server_host=os.getenv("ORCHESTRATOR_HOST", "localhost"),
        server_port=int(os.getenv("ORCHESTRATOR_PORT", "8001")),
        max_concurrent_instances=int(os.getenv("MAX_INSTANCES", "10")),
        workspace_base_dir=os.getenv("WORKSPACE_DIR", "/tmp/claude_orchestrator"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )

    orchestrator = OrchestrationMCPServer(config)
    notification_options = NotificationOptions()
    init_options = InitializationOptions(
        server_name="claude-orchestrator",
        server_version="1.0.0",
        capabilities=orchestrator.server.get_capabilities(
            notification_options=notification_options,
            experimental_capabilities={},
        ),
    )

    async with stdio.stdio_server() as (read_stream, write_stream):
        await orchestrator.server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
