"""Claude Orchestrator MCP Server."""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    # Fallback for type checking
    class FastAPI:
        def __init__(self, *args, **kwargs):
            pass

        def add_middleware(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def post(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code
            self.detail = detail

    class CORSMiddleware:
        pass


from .instance_manager import InstanceManager
from .mcp_adapter import MCPAdapter
from .simple_models import (
    InstanceRole,
    OrchestratorConfig,
)

logger = logging.getLogger(__name__)


class ClaudeOrchestratorServer:
    """MCP Server for Claude Orchestrator."""

    def __init__(self, config: OrchestratorConfig):
        """Initialize the orchestrator server.

        Args:
            config: Configuration for the orchestrator
        """
        self.config = config
        self.instance_manager = InstanceManager(config.to_dict())

        # Initialize FastAPI app
        self.app = FastAPI(
            title="Claude Conversational Orchestrator",
            description="MCP server for spawning and managing multiple Claude instances",
            version="1.0.0",
        )

        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Mount MCP adapter before registering additional routes
        self.mcp_adapter = MCPAdapter(self.instance_manager)
        self.app.include_router(self.mcp_adapter.router)

        # Setup routes
        self._setup_routes()

        logger.info("Claude Orchestrator Server initialized")

    def _setup_routes(self):
        """Setup FastAPI routes for MCP tools."""

        @self.app.get("/")
        async def root():
            """Root endpoint with server info."""
            return {
                "name": "Claude Conversational Orchestrator",
                "version": "1.0.0",
                "description": "MCP server for managing multiple Claude instances",
                "tools": [
                    "spawn_claude",
                    "send_to_instance",
                    "get_instance_output",
                    "coordinate_instances",
                    "terminate_instance",
                    "get_instance_status",
                ],
                "active_instances": len(self.instance_manager.instances),
                "server_time": datetime.utcnow().isoformat(),
            }

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0",
                "instances": {
                    "total": len(self.instance_manager.instances),
                    "running": len(
                        [
                            i
                            for i in self.instance_manager.instances.values()
                            if i["state"] in ["running", "idle", "busy"]
                        ]
                    ),
                },
            }

        # MCP Protocol endpoints
        @self.app.get("/tools")
        async def list_tools():
            """List available MCP tools."""
            return {
                "tools": [
                    {
                        "name": "spawn_claude",
                        "description": "Spawn a new Claude instance with specific role and configuration",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Optional custom name (auto-generates funny name if not provided)",
                                },
                                "auto_generate_name": {
                                    "type": "boolean",
                                    "description": "Force funny name generation even if name is provided",
                                    "default": False,
                                },
                                "role": {
                                    "type": "string",
                                    "enum": [role.value for role in InstanceRole],
                                    "description": "Predefined role for the instance",
                                },
                                "system_prompt": {
                                    "type": "string",
                                    "description": "Custom system prompt",
                                },
                                "model": {"type": "string", "description": "Claude model to use"},
                                "max_tokens": {
                                    "type": "integer",
                                    "description": "Max tokens per request",
                                },
                                "temperature": {
                                    "type": "number",
                                    "description": "Temperature setting",
                                },
                                "workspace_dir": {
                                    "type": "string",
                                    "description": "Working directory",
                                },
                                "parent_instance_id": {
                                    "type": "string",
                                    "description": "Parent instance ID",
                                },
                            },
                            "required": [],
                        },
                    },
                    {
                        "name": "send_to_instance",
                        "description": "Send a message to a specific Claude instance",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "instance_id": {
                                    "type": "string",
                                    "description": "Target instance ID",
                                },
                                "message": {"type": "string", "description": "Message to send"},
                                "wait_for_response": {
                                    "type": "boolean",
                                    "description": "Wait for response",
                                },
                                "timeout_seconds": {
                                    "type": "integer",
                                    "description": "Response timeout",
                                },
                                "priority": {"type": "integer", "description": "Message priority"},
                            },
                            "required": ["instance_id", "message"],
                        },
                    },
                    {
                        "name": "get_instance_output",
                        "description": "Get recent output from a Claude instance",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "instance_id": {"type": "string", "description": "Instance ID"},
                                "since": {
                                    "type": "string",
                                    "description": "ISO timestamp to get messages since",
                                },
                                "limit": {
                                    "type": "integer",
                                    "description": "Maximum number of messages",
                                },
                            },
                            "required": ["instance_id"],
                        },
                    },
                    {
                        "name": "coordinate_instances",
                        "description": "Coordinate multiple instances for a complex task",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "coordinator_id": {
                                    "type": "string",
                                    "description": "Coordinating instance ID",
                                },
                                "participant_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Participating instance IDs",
                                },
                                "task_description": {
                                    "type": "string",
                                    "description": "Task description",
                                },
                                "coordination_type": {
                                    "type": "string",
                                    "enum": ["sequential", "parallel", "consensus"],
                                    "description": "Type of coordination",
                                },
                            },
                            "required": ["coordinator_id", "participant_ids", "task_description"],
                        },
                    },
                    {
                        "name": "terminate_instance",
                        "description": "Terminate a Claude instance",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "instance_id": {
                                    "type": "string",
                                    "description": "Instance ID to terminate",
                                },
                                "force": {
                                    "type": "boolean",
                                    "description": "Force termination even if busy",
                                },
                            },
                            "required": ["instance_id"],
                        },
                    },
                    {
                        "name": "get_instance_status",
                        "description": "Get status for a single instance or all instances",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "instance_id": {
                                    "type": "string",
                                    "description": "Optional instance ID (omit for all instances)",
                                },
                            },
                        },
                    },
                ]
            }

        @self.app.post("/tools/execute")
        async def execute_tool(request: dict[str, Any]):
            """Execute an MCP tool."""
            tool_name = request.get("tool")
            arguments = request.get("arguments", {})

            try:
                if tool_name == "spawn_claude":
                    return await self._spawn_claude(**arguments)
                elif tool_name == "send_to_instance":
                    return await self._send_to_instance(**arguments)
                elif tool_name == "get_instance_output":
                    return await self._get_instance_output(**arguments)
                elif tool_name == "coordinate_instances":
                    return await self._coordinate_instances(**arguments)
                elif tool_name == "terminate_instance":
                    return await self._terminate_instance(**arguments)
                elif tool_name == "get_instance_status":
                    return await self._get_instance_status(**arguments)
                else:
                    raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")

            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}")
                raise HTTPException(status_code=500, detail=str(e)) from e

        @self.app.get("/instances")
        async def list_instances():
            """List all instances."""
            return self.instance_manager.get_instance_status()

        @self.app.get("/instances/{instance_id}")
        async def get_instance(instance_id: str):
            """Get specific instance details."""
            try:
                return self.instance_manager.get_instance_status(instance_id)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e)) from e

        @self.app.post("/instances/{instance_id}/health")
        async def instance_health_check(instance_id: str):
            """Perform health check on specific instance."""
            try:
                instance = self.instance_manager.get_instance_status(instance_id)
                # Perform actual health check here
                return {
                    "instance_id": instance_id,
                    "healthy": instance["state"] in ["running", "idle"],
                    "last_activity": instance["last_activity"],
                    "uptime_seconds": (
                        datetime.utcnow() - datetime.fromisoformat(instance["created_at"])
                    ).total_seconds(),
                }
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e)) from e

        @self.app.get("/logs/audit")
        async def get_audit_logs(limit: int = 100, since: str | None = None):
            """Get audit logs with optional filtering."""
            return await self._get_audit_logs(limit=limit, since=since)

        @self.app.get("/logs/instances/{instance_id}")
        async def get_instance_logs(instance_id: str, limit: int = 100, since: str | None = None):
            """Get logs for a specific instance."""
            return await self._get_instance_logs(instance_id=instance_id, limit=limit, since=since)

        @self.app.get("/logs/communication/{instance_id}")
        async def get_communication_logs(instance_id: str, limit: int = 100, since: str | None = None):
            """Get communication logs for a specific instance."""
            return await self._get_communication_logs(instance_id=instance_id, limit=limit, since=since)

        @self.app.get("/network/hierarchy")
        async def get_network_hierarchy():
            """Get complete network hierarchy with all instances."""
            return await self._get_network_hierarchy()

    async def _spawn_claude(
        self,
        name: str | None = None,
        auto_generate_name: bool = False,
        role: str = "general",
        system_prompt: str | None = None,
        model: str = "claude-4-sonnet-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        workspace_dir: str | None = None,
        parent_instance_id: str | None = None,
        use_pty: bool = False,  # Back to subprocess for reliability
        **kwargs,
    ) -> dict[str, Any]:
        """Spawn a new Claude instance."""
        # Force funny name generation if requested or if name is empty/generic
        generic_names = [
            "unnamed",
            "assistant",
            "claude_assistant",
            "auto_instance",
            "assistant-1",
            "assistant-2",
            "assistant-3",
            "assistant-4",
            "madrox-instance",
            "instance",
        ]
        if (
            auto_generate_name
            or not name
            or name == ""
            or any(name and name.lower().startswith(g) for g in generic_names)
        ):
            name = None
        logger.info(
            f"Spawning Claude instance: {name if name else 'auto-generated funny name'} with role {role}"
        )

        try:
            # Validate role
            if role not in [r.value for r in InstanceRole]:
                role = InstanceRole.GENERAL.value

            instance_id = await self.instance_manager.spawn_instance(
                name=name,
                role=role,
                system_prompt=system_prompt,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                workspace_dir=workspace_dir,
                parent_instance_id=parent_instance_id,
                use_pty=use_pty,
                **kwargs,
            )

            # Get the actual instance to get the generated name
            instance = self.instance_manager.instances[instance_id]
            actual_name = instance["name"]

            return {
                "success": True,
                "instance_id": instance_id,
                "name": actual_name,
                "role": role,
                "model": model,
                "message": f"Successfully spawned Claude instance '{actual_name}' with role '{role}'",
            }

        except Exception as e:
            logger.error(f"Failed to spawn instance: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to spawn Claude instance: {e}",
            }

    async def _send_to_instance(
        self,
        instance_id: str,
        message: str,
        wait_for_response: bool = True,
        timeout_seconds: int = 30,
        priority: int = 0,
    ) -> dict[str, Any]:
        """Send message to Claude instance."""
        logger.info(f"Sending message to instance {instance_id}: {message[:100]}...")

        try:
            response = await self.instance_manager.send_to_instance(
                instance_id=instance_id,
                message=message,
                wait_for_response=wait_for_response,
                timeout_seconds=timeout_seconds,
                priority=priority,
            )

            if response:
                return {
                    "success": True,
                    "instance_id": instance_id,
                    "response": response,
                    "message": "Message sent and response received",
                }
            else:
                return {
                    "success": True,
                    "instance_id": instance_id,
                    "message": "Message sent"
                    + (" (no response requested)" if not wait_for_response else " (timeout)"),
                }

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to send message: {e}",
            }

    async def _get_instance_output(
        self,
        instance_id: str,
        since: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get instance output."""
        logger.info(f"Getting output for instance {instance_id}")

        try:
            output = await self.instance_manager.get_instance_output(
                instance_id=instance_id,
                since=since,
                limit=limit,
            )

            return {
                "success": True,
                "instance_id": instance_id,
                "output": output,
                "count": len(output),
                "message": f"Retrieved {len(output)} output messages",
            }

        except Exception as e:
            logger.error(f"Failed to get output: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to get output: {e}",
            }

    async def _get_instance_status(
        self,
        instance_id: str | None = None,
    ) -> dict[str, Any]:
        """Get status for a single instance or all instances."""
        logger.info("Fetching instance status", extra={"instance_id": instance_id})

        try:
            status = self.instance_manager.get_instance_status(instance_id)
            return {
                "success": True,
                "status": status,
                "message": "Retrieved instance status",
            }

        except Exception as e:
            logger.error(f"Failed to get instance status: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to fetch instance status: {e}",
            }

    async def _coordinate_instances(
        self,
        coordinator_id: str,
        participant_ids: list[str],
        task_description: str,
        coordination_type: str = "sequential",
    ) -> dict[str, Any]:
        """Coordinate multiple instances."""
        logger.info(f"Starting coordination with {len(participant_ids)} participants")

        try:
            task_id = await self.instance_manager.coordinate_instances(
                coordinator_id=coordinator_id,
                participant_ids=participant_ids,
                task_description=task_description,
                coordination_type=coordination_type,
            )

            return {
                "success": True,
                "task_id": task_id,
                "coordinator_id": coordinator_id,
                "participant_ids": participant_ids,
                "coordination_type": coordination_type,
                "message": f"Started coordination task {task_id}",
            }

        except Exception as e:
            logger.error(f"Failed to start coordination: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to start coordination: {e}",
            }

    async def _terminate_instance(
        self,
        instance_id: str,
        force: bool = False,
    ) -> dict[str, Any]:
        """Terminate Claude instance."""
        logger.info(f"Terminating instance {instance_id} (force={force})")

        try:
            success = await self.instance_manager.terminate_instance(
                instance_id=instance_id,
                force=force,
            )

            if success:
                return {
                    "success": True,
                    "instance_id": instance_id,
                    "message": f"Successfully terminated instance {instance_id}",
                }
            else:
                return {
                    "success": False,
                    "instance_id": instance_id,
                    "message": f"Failed to terminate instance {instance_id} (try with force=true)",
                }

        except Exception as e:
            logger.error(f"Failed to terminate instance: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to terminate instance: {e}",
            }

    async def start_server(self):
        """Start the MCP server."""
        try:
            import uvicorn
        except ImportError:
            # Fallback for type checking
            class Config:
                def __init__(self, *args, **kwargs):
                    pass

            class Server:
                def __init__(self, *args, **kwargs):
                    pass

                async def serve(self):
                    pass

            uvicorn = type("uvicorn", (), {"Config": Config, "Server": Server})()

        logger.info(
            f"Starting Claude Orchestrator Server on {self.config.server_host}:{self.config.server_port}"
        )

        # Start health check background task
        asyncio.create_task(self._health_check_loop())

        # Start the server
        config = uvicorn.Config(
            self.app,
            host=self.config.server_host,
            port=self.config.server_port,
            log_level=self.config.log_level.lower(),
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def _get_audit_logs(self, limit: int = 100, since: str | None = None) -> dict[str, Any]:
        """Get audit logs from the logging system."""
        from pathlib import Path
        import json

        log_dir = Path(self.config.log_dir) / "audit"
        today = datetime.utcnow().strftime("%Y%m%d")
        audit_file = log_dir / f"audit_{today}.jsonl"

        logs = []
        if audit_file.exists():
            with open(audit_file) as f:
                for line in f:
                    if line.strip():
                        log_entry = json.loads(line)
                        if since:
                            if log_entry["timestamp"] >= since:
                                logs.append(log_entry)
                        else:
                            logs.append(log_entry)

        return {
            "logs": logs[-limit:] if logs else [],
            "total": len(logs),
            "file": str(audit_file)
        }

    async def _get_instance_logs(self, instance_id: str, limit: int = 100, since: str | None = None) -> dict[str, Any]:
        """Get instance logs."""
        from pathlib import Path

        log_dir = Path(self.config.log_dir) / "instances" / instance_id
        instance_log = log_dir / "instance.log"

        if not instance_log.exists():
            raise HTTPException(status_code=404, detail=f"No logs found for instance {instance_id}")

        logs = []
        with open(instance_log) as f:
            for line in f:
                if line.strip():
                    logs.append(line.strip())

        return {
            "logs": logs[-limit:] if logs else [],
            "total": len(logs),
            "instance_id": instance_id,
            "file": str(instance_log)
        }

    async def _get_communication_logs(self, instance_id: str, limit: int = 100, since: str | None = None) -> dict[str, Any]:
        """Get communication logs for an instance."""
        from pathlib import Path
        import json

        log_dir = Path(self.config.log_dir) / "instances" / instance_id
        comm_log = log_dir / "communication.jsonl"

        if not comm_log.exists():
            raise HTTPException(status_code=404, detail=f"No communication logs found for instance {instance_id}")

        logs = []
        with open(comm_log) as f:
            for line in f:
                if line.strip():
                    log_entry = json.loads(line)
                    if since:
                        if log_entry["timestamp"] >= since:
                            logs.append(log_entry)
                    else:
                        logs.append(log_entry)

        return {
            "logs": logs[-limit:] if logs else [],
            "total": len(logs),
            "instance_id": instance_id,
            "file": str(comm_log)
        }

    async def _get_network_hierarchy(self) -> dict[str, Any]:
        """Get complete network hierarchy with parent-child relationships."""
        instances = self.instance_manager.instances

        # Filter out terminated instances
        active_instances = {
            instance_id: instance_data
            for instance_id, instance_data in instances.items()
            if instance_data.get("state") != "terminated"
        }

        # Build hierarchy structure
        hierarchy = {
            "total_instances": len(active_instances),
            "root_instances": [],
            "all_instances": []
        }

        # Create instance info map
        instance_map = {}
        for instance_id, instance_data in active_instances.items():
            instance_info = {
                "id": instance_id,
                "name": instance_data.get("name", "unknown"),
                "type": instance_data.get("instance_type", "unknown"),
                "role": instance_data.get("role", "unknown"),
                "state": instance_data.get("state", "unknown"),
                "parent_id": instance_data.get("parent_instance_id"),
                "children": [],
                "created_at": instance_data.get("created_at"),
                "total_tokens": instance_data.get("total_tokens_used", 0),
                "total_cost": instance_data.get("total_cost", 0.0),
                "request_count": instance_data.get("request_count", 0)
            }
            instance_map[instance_id] = instance_info
            hierarchy["all_instances"].append(instance_info)

        # Build parent-child relationships
        for instance_id, instance_info in instance_map.items():
            parent_id = instance_info["parent_id"]
            if parent_id and parent_id in instance_map:
                # Add to parent's children
                instance_map[parent_id]["children"].append(instance_info)
            else:
                # Root instance (no parent or parent not found)
                hierarchy["root_instances"].append(instance_info)

        return hierarchy

    async def _health_check_loop(self):
        """Background health check loop."""
        while True:
            try:
                await self.instance_manager.health_check()
                await asyncio.sleep(60)  # Health check every minute
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(10)  # Retry in 10 seconds on error


async def main():
    """Main entry point for the server."""
    # Load configuration from environment
    config = OrchestratorConfig(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        server_host=os.getenv("ORCHESTRATOR_HOST", "localhost"),
        server_port=int(os.getenv("ORCHESTRATOR_PORT", "8001")),
        max_concurrent_instances=int(os.getenv("MAX_INSTANCES", "10")),
        workspace_base_dir=os.getenv("WORKSPACE_DIR", "/tmp/claude_orchestrator"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create and start server
    server = ClaudeOrchestratorServer(config)
    await server.start_server()


if __name__ == "__main__":
    asyncio.run(main())
