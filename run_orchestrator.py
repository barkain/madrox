#!/usr/bin/env python3
"""Launcher script for Claude Orchestrator MCP Server."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def main():
    """Main entry point."""
    try:
        from src.orchestrator.server import ClaudeOrchestratorServer
        from src.orchestrator.simple_models import OrchestratorConfig

        # Load configuration from environment
        config = OrchestratorConfig(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            server_host=os.getenv("ORCHESTRATOR_HOST", "localhost"),
            server_port=int(os.getenv("ORCHESTRATOR_PORT", "8001")),
            max_concurrent_instances=int(os.getenv("MAX_INSTANCES", "10")),
            workspace_base_dir=os.getenv("WORKSPACE_DIR", "/tmp/claude_orchestrator"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

        print(f"Starting Claude Orchestrator on {config.server_host}:{config.server_port}")
        print(f"Workspace: {config.workspace_base_dir}")
        print(f"Max instances: {config.max_concurrent_instances}")

        # Create and start server
        server = ClaudeOrchestratorServer(config)
        asyncio.run(server.start_server())

    except ImportError as e:
        print(f"Import error: {e}")
        print("Please ensure FastAPI and uvicorn are installed:")
        print("pip install fastapi uvicorn")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
