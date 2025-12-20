"""Claude Orchestrator MCP Server."""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

from fastapi import (  # type: ignore[import-untyped]
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware  # type: ignore[import-untyped]

from .instance_manager import InstanceManager
from .logging_manager import LoggingManager, get_audit_log_stream_handler, get_log_stream_handler
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

        # Initialize artifacts configuration (base directory, session subdirectory added later)
        self.artifacts_base_dir = os.getenv("ARTIFACTS_DIR", "/tmp/madrox_logs/artifacts")
        self.preserve_artifacts = os.getenv("PRESERVE_ARTIFACTS", "true").lower() == "true"
        # Default: collect common source code, docs, config, and data files
        # Excludes: compiled binaries, dependencies, caches, OS files
        artifact_patterns_str = os.getenv(
            "ARTIFACT_PATTERNS",
            "*.py,*.rs,*.js,*.ts,*.tsx,*.jsx,*.java,*.cpp,*.c,*.h,*.go,*.rb,*.php,*.swift,*.kt,"
            "*.md,*.txt,*.pdf,*.csv,*.json,*.yaml,*.yml,*.toml,*.xml,*.html,*.css,*.sql,*.sh,"
            "Cargo.toml,Cargo.lock,package.json,requirements.txt,Dockerfile,Makefile,README,LICENSE",
        )
        self.artifact_patterns = [p.strip() for p in artifact_patterns_str.split(",")]

        # Initialize logging manager
        log_dir = os.getenv("MADROX_LOG_DIR", "/tmp/madrox_logs")
        log_level = os.getenv("LOG_LEVEL", "INFO")
        self.logging_manager = LoggingManager(log_dir=log_dir, log_level=log_level)

        # Test logging immediately after LoggingManager initialization
        self.logging_manager.orchestrator_logger.info("LoggingManager initialized successfully")
        self.logging_manager.orchestrator_logger.debug("DEBUG logging test")

        # Reconfigure module-level logger to use orchestrator logger's handlers
        # The module-level logger was created at import time, before LoggingManager setup
        # We need to get the exact same logger object and reconfigure it
        server_logger = logging.getLogger("orchestrator.server")
        server_logger.handlers.clear()  # Remove any default handlers
        server_logger.propagate = (
            True  # Propagate to "orchestrator" parent which has configured handlers
        )
        server_logger.setLevel(logging.DEBUG)  # Let parent handlers do the filtering

        # Test the reconfigured module-level logger
        server_logger.info("Module-level logger reconfigured successfully")

        # Generate session ID for artifact organization (before instance manager init)
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Use session artifacts directory as workspace - instances work directly in final location
        session_workspace_dir = os.path.join(self.artifacts_base_dir, self.session_id)

        # Initialize instance manager with logging and artifacts config
        instance_manager_config = config.to_dict()
        instance_manager_config.update(
            {
                "workspace_base_dir": session_workspace_dir,  # Instances work in artifacts dir
                "artifacts_dir": session_workspace_dir,  # Same location
                "preserve_artifacts": self.preserve_artifacts,
                "artifact_patterns": self.artifact_patterns,
                "session_id": self.session_id,
            }
        )
        self.instance_manager = InstanceManager(instance_manager_config)

        # Clean up orphaned tmux sessions from previous server runs
        self._cleanup_orphaned_tmux_sessions()

        # Track server start time for session-only audit logs (use local time to match audit log timestamps)
        self.server_start_time = datetime.now().isoformat()

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
            # Get available tools from MCP adapter dynamically
            tools_list = [tool["name"] for tool in await self.mcp_adapter.get_available_tools()]

            return {
                "name": "Claude Conversational Orchestrator",
                "version": "1.0.0",
                "description": "MCP server for managing multiple Claude instances",
                "tools": tools_list,
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

        @self.app.websocket("/ws/monitor")
        async def monitor_websocket(websocket: WebSocket):
            """WebSocket endpoint for real-time monitoring."""
            await websocket.accept()
            logger.info("WebSocket client connected to /ws/monitor")

            try:
                # Send initial state with instances (exclude terminated)
                # Use _get_instance_status_internal to include tmux-discovered instances
                status_data = self.instance_manager._get_instance_status_internal()
                instances_data = []
                for instance_id, instance in status_data.get("instances", {}).items():
                    # Skip terminated instances
                    if instance.get("state") == "terminated":
                        continue

                    instances_data.append(
                        {
                            "id": instance_id,
                            "name": instance.get("name", instance_id),
                            "type": instance.get("instance_type", "claude"),
                            "status": instance.get("state", "unknown"),
                            "role": instance.get("role", "general"),
                            "parentId": instance.get("parent_instance_id"),
                            "createdAt": instance.get("created_at", datetime.utcnow().isoformat()),
                            "lastActivity": instance.get(
                                "last_activity", datetime.utcnow().isoformat()
                            ),
                            "totalTokens": instance.get("total_tokens_used", 0),
                            "totalCost": instance.get("total_cost", 0.0),
                        }
                    )

                await websocket.send_json(
                    {
                        "type": "initial_state",
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {"instances": instances_data},
                    }
                )

                # Send initial audit logs (only from current session)
                audit_logs = await self.instance_manager.get_audit_logs(
                    since=self.server_start_time, limit=100
                )
                for log in audit_logs:
                    # Generate human-readable message from event
                    event_type = log.get("event_type", "")
                    details = log.get("details", {})
                    instance_name = details.get("instance_name", log.get("instance_id", ""))

                    if event_type == "instance_spawn":
                        message = (
                            f"Spawned instance '{instance_name}' ({details.get('role', 'general')})"
                        )
                    elif event_type == "message_exchange":
                        message = f"Message sent to '{instance_name}'"
                    elif event_type == "instance_terminate":
                        message = f"Terminated instance '{instance_name}'"
                    else:
                        message = event_type.replace("_", " ").title()

                    # Use timestamp + instance_id + event_type for unique ID
                    log_id = f"{log.get('timestamp', '')}_{log.get('instance_id', '')}_{log.get('event_type', '')}"

                    await websocket.send_json(
                        {
                            "type": "audit_log",
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": {
                                "log": {
                                    "id": log_id,
                                    "timestamp": log.get("timestamp", ""),
                                    "type": log.get("event_type", ""),
                                    "message": message,
                                    "instanceId": log.get("instance_id"),
                                }
                            },
                        }
                    )

                # Track last known audit log timestamp (use local time to match audit logs)
                last_audit_check = datetime.now().isoformat()

                # Keep connection alive and send updates
                while True:
                    # Wait for ping from client (heartbeat)
                    try:
                        message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    except TimeoutError:
                        # Send periodic updates even without client ping
                        pass

                    # Send current instance state (exclude terminated)
                    # Use _get_instance_status_internal to include tmux-discovered instances
                    status_data = self.instance_manager._get_instance_status_internal()
                    instances_data = []
                    for instance_id, instance in status_data.get("instances", {}).items():
                        # Skip terminated instances
                        if instance.get("state") == "terminated":
                            continue

                        instances_data.append(
                            {
                                "id": instance_id,
                                "name": instance.get("name", instance_id),
                                "type": instance.get("instance_type", "claude"),
                                "status": instance.get("state", "unknown"),
                                "role": instance.get("role", "general"),
                                "parentId": instance.get("parent_instance_id"),
                                "createdAt": instance.get(
                                    "created_at", datetime.utcnow().isoformat()
                                ),
                                "lastActivity": instance.get(
                                    "last_activity", datetime.utcnow().isoformat()
                                ),
                                "totalTokens": instance.get("total_tokens_used", 0),
                                "totalCost": instance.get("total_cost", 0.0),
                            }
                        )

                    await websocket.send_json(
                        {
                            "type": "instance_update",
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": {"instances": instances_data},
                        }
                    )

                    # Send new audit logs since last check
                    new_audit_logs = await self.instance_manager.get_audit_logs(
                        since=last_audit_check, limit=100
                    )
                    if new_audit_logs:
                        for log in new_audit_logs:
                            # Generate human-readable message from event
                            event_type = log.get("event_type", "")
                            details = log.get("details", {})
                            instance_name = details.get("instance_name", log.get("instance_id", ""))

                            if event_type == "instance_spawn":
                                message = f"Spawned instance '{instance_name}' ({details.get('role', 'general')})"
                            elif event_type == "message_exchange":
                                message = f"Message sent to '{instance_name}'"
                            elif event_type == "instance_terminate":
                                message = f"Terminated instance '{instance_name}'"
                            else:
                                message = event_type.replace("_", " ").title()

                            # Use timestamp + instance_id + event_type for unique ID
                            log_id = f"{log.get('timestamp', '')}_{log.get('instance_id', '')}_{log.get('event_type', '')}"

                            await websocket.send_json(
                                {
                                    "type": "audit_log",
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "data": {
                                        "log": {
                                            "id": log_id,
                                            "timestamp": log.get("timestamp", ""),
                                            "type": log.get("event_type", ""),
                                            "message": message,
                                            "instanceId": log.get("instance_id"),
                                        }
                                    },
                                }
                            )
                        # Update last check timestamp to the newest log
                        last_audit_check = new_audit_logs[-1].get("timestamp", last_audit_check)

                    await asyncio.sleep(2)  # Update every 2 seconds

            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected from /ws/monitor")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                try:
                    await websocket.close()
                except Exception:
                    pass

        def transform_audit_log(audit_entry: dict[str, Any]) -> dict[str, Any]:
            """Transform backend audit log format to frontend format."""
            return {
                "timestamp": audit_entry.get("timestamp", ""),
                "level": audit_entry.get("level", "INFO"),
                "logger": audit_entry.get("logger", "orchestrator.audit"),
                "message": audit_entry.get("event", ""),  # Map 'event' to 'message'
                "action": audit_entry.get("event_type", ""),  # Map 'event_type' to 'action'
                "metadata": audit_entry.get("details", {}),  # Map 'details' to 'metadata'
            }

        @self.app.websocket("/ws/logs")
        async def logs_websocket(websocket: WebSocket):
            """WebSocket endpoint for dual-panel logging system (system + audit logs)."""
            await websocket.accept()
            logger.info("WebSocket client connected to /ws/logs")

            # Register this client with both system and audit log stream handlers
            log_handler = get_log_stream_handler()
            log_handler.add_client(websocket)

            audit_log_handler = get_audit_log_stream_handler()
            audit_log_handler.add_client(websocket)

            try:
                # Send recent system logs on initial connection
                log_file = self.logging_manager.log_dir / "orchestrator.log"
                if log_file.exists():
                    try:
                        with log_file.open("r") as f:
                            lines = f.readlines()
                            # Send last 100 system log lines
                            for line in lines[-100:]:
                                try:
                                    import json

                                    log_entry = json.loads(line.strip())
                                    await websocket.send_json(
                                        {"type": "system_log", "data": log_entry}
                                    )
                                except json.JSONDecodeError:
                                    continue
                    except Exception as e:
                        logger.error(f"Failed to load historical system logs: {e}")

                # Send recent audit logs on initial connection
                audit_logs = await self.instance_manager.get_audit_logs(limit=100)
                for audit_entry in audit_logs:
                    transformed_audit = transform_audit_log(audit_entry)
                    await websocket.send_json({"type": "audit_log", "data": transformed_audit})

                # Keep connection alive and handle client pings
                last_audit_check = datetime.now().isoformat()

                while True:
                    # Check for new audit logs periodically
                    new_audit_logs = await self.instance_manager.get_audit_logs(
                        since=last_audit_check, limit=50
                    )

                    if new_audit_logs:
                        for audit_entry in new_audit_logs:
                            transformed_audit = transform_audit_log(audit_entry)
                            await websocket.send_json(
                                {"type": "audit_log", "data": transformed_audit}
                            )
                        # Update timestamp to the newest audit log
                        last_audit_check = new_audit_logs[-1].get("timestamp", last_audit_check)

                    # Send ping to keep connection alive
                    try:
                        await websocket.send_json({"type": "ping"})
                    except Exception:
                        break

                    await asyncio.sleep(2)  # Check every 2 seconds

            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected from /ws/logs")
            except Exception as e:
                logger.error(f"WebSocket error in /ws/logs: {e}")
                try:
                    await websocket.close()
                except Exception:
                    pass
            finally:
                log_handler.remove_client(websocket)
                audit_log_handler.remove_client(websocket)

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
            return self.instance_manager._get_instance_status_internal()

        @self.app.get("/instances/{instance_id}")
        async def get_instance(instance_id: str):
            """Get specific instance details."""
            try:
                return self.instance_manager._get_instance_status_internal(instance_id)
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

        @self.app.get("/instances/{instance_id}/live_status")
        async def get_live_status(instance_id: str):
            """Get real-time execution status for an instance.

            NOTE: current_tool and tools_executed are not available in interactive mode.
            Use get_tmux_pane_content for detailed terminal output with tool execution info.
            """
            try:
                # Get basic instance status
                instance = self.instance_manager.get_instance_status(instance_id)

                # Get event statistics from tmux_manager
                event_stats = self.instance_manager.tmux_manager.get_event_statistics(instance_id)

                # Get most recent assistant output from message history
                last_output = None
                message_history = self.instance_manager.tmux_manager.message_history.get(
                    instance_id, []
                )
                if message_history:
                    # Get the last assistant message as last_output
                    for event in reversed(message_history):
                        if event.get("role") == "assistant":
                            content = event.get("content", "")
                            last_output = content[:200] + "..." if len(content) > 200 else content
                            break

                # Calculate execution time (uptime)
                created_at = datetime.fromisoformat(instance["created_at"])
                now = datetime.now(created_at.tzinfo) if created_at.tzinfo else datetime.utcnow()
                execution_time = (now - created_at).total_seconds()

                return {
                    "instance_id": instance_id,
                    "state": instance["state"],
                    "current_tool": None,  # Not available in interactive mode
                    "execution_time": execution_time,
                    "tools_executed": 0,  # Not available in interactive mode
                    "last_output": last_output,
                    "last_activity": instance["last_activity"],
                    "tools_breakdown": {},  # Not available in interactive mode
                    "event_counts": event_stats.get("event_counts", {}),
                    "note": "Tool tracking not available in interactive mode. Use get_tmux_pane_content for detailed output.",
                }
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e)) from e

        @self.app.get("/logs/audit")
        async def get_audit_logs(
            limit: int = 100, since: str | None = None, root_instance_id: str | None = None
        ):
            """Get audit logs with optional filtering.

            Args:
                limit: Maximum number of logs to return
                since: Filter logs after this timestamp
                root_instance_id: Optional root instance ID to filter logs by specific network
            """
            return await self._get_audit_logs(
                limit=limit, since=since, root_instance_id=root_instance_id
            )

        @self.app.get("/logs/instances/{instance_id}")
        async def get_instance_logs(instance_id: str, limit: int = 100, since: str | None = None):
            """Get logs for a specific instance."""
            return await self._get_instance_logs(instance_id=instance_id, limit=limit, since=since)

        @self.app.get("/logs/communication/{instance_id}")
        async def get_communication_logs(
            instance_id: str, limit: int = 100, since: str | None = None
        ):
            """Get communication logs for a specific instance."""
            return await self._get_communication_logs(
                instance_id=instance_id, limit=limit, since=since
            )

        @self.app.get("/network/hierarchy")
        async def get_network_hierarchy(root_instance_id: str | None = None):
            """Get complete network hierarchy with all instances.

            Args:
                root_instance_id: Optional root instance ID to filter hierarchy by specific network
            """
            return await self._get_network_hierarchy(root_instance_id=root_instance_id)

        # ============================================================================
        # Summary/Monitoring API Endpoints
        # ============================================================================

        @self.app.get("/api/monitoring/sessions")
        async def list_summary_sessions():
            """List all available summary sessions."""
            from pathlib import Path

            summaries_base = Path("/tmp/madrox_logs/summaries")
            if not summaries_base.exists():
                return {"sessions": []}

            sessions = []
            for session_dir in sorted(summaries_base.iterdir(), reverse=True):
                if session_dir.is_dir() and session_dir.name.startswith("session_"):
                    # Count summaries in this session
                    instance_count = len([d for d in session_dir.iterdir() if d.is_dir()])
                    summary_count = len(list(session_dir.rglob("summary_*.json")))

                    sessions.append(
                        {
                            "session_id": session_dir.name,
                            "path": str(session_dir),
                            "instance_count": instance_count,
                            "summary_count": summary_count,
                            "created_at": datetime.fromtimestamp(
                                session_dir.stat().st_ctime
                            ).isoformat(),
                        }
                    )

            # Get current session from MonitoringService
            current_session = None
            if hasattr(self.instance_manager, "tmux_manager"):
                monitoring_service = getattr(
                    self.instance_manager.tmux_manager, "monitoring_service", None
                )
                if monitoring_service:
                    current_session = monitoring_service.session_id

            return {
                "current_session": current_session,
                "total_sessions": len(sessions),
                "sessions": sessions,
            }

        @self.app.get("/api/monitoring/sessions/{session_id}/summaries")
        async def get_session_summaries(session_id: str):
            """Get all summaries for a specific session."""
            import json
            from pathlib import Path
            from uuid import UUID

            # Validate session_id is a valid UUID to prevent path traversal
            try:
                UUID(session_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid session_id format") from None

            session_path = Path("/tmp/madrox_logs/summaries") / session_id
            if not session_path.exists():
                raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

            summaries = {}
            for instance_dir in session_path.iterdir():
                if instance_dir.is_dir():
                    instance_id = instance_dir.name
                    latest_file = instance_dir / "latest.json"

                    if latest_file.exists():
                        with open(latest_file) as f:
                            summaries[instance_id] = json.load(f)

            return {
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "instance_count": len(summaries),
                "summaries": summaries,
            }

        @self.app.get("/api/monitoring/sessions/{session_id}/instances/{instance_id}")
        async def get_instance_summary_history(session_id: str, instance_id: str):
            """Get summary history for a specific instance in a session."""
            import json
            from pathlib import Path
            from uuid import UUID

            # Validate session_id and instance_id are valid UUIDs to prevent path traversal
            try:
                UUID(session_id)
                UUID(instance_id)
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid session_id or instance_id format"
                ) from None

            instance_path = Path("/tmp/madrox_logs/summaries") / session_id / instance_id
            if not instance_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"Instance {instance_id} not found in session {session_id}",
                )

            summaries = []
            for summary_file in sorted(instance_path.glob("summary_*.json")):
                with open(summary_file) as f:
                    summaries.append(json.load(f))

            return {
                "session_id": session_id,
                "instance_id": instance_id,
                "summary_count": len(summaries),
                "summaries": summaries,
            }

        @self.app.get("/api/monitoring/current")
        async def get_current_session_summaries():
            """Get summaries for the current active session."""
            # Get current session from MonitoringService
            if hasattr(self.instance_manager, "tmux_manager"):
                monitoring_service = getattr(
                    self.instance_manager.tmux_manager, "monitoring_service", None
                )
                if monitoring_service:
                    session_id = monitoring_service.session_id
                    return await get_session_summaries(session_id)

            raise HTTPException(status_code=503, detail="MonitoringService not available")

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
            # Note: priority parameter is accepted but not used by instance_manager
            response = await self.instance_manager.send_to_instance(
                instance_id=instance_id,
                message=message,
                wait_for_response=wait_for_response,
                timeout_seconds=timeout_seconds,
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
            import uvicorn  # type: ignore[import-untyped]
        except ImportError:
            # Fallback for type checking
            class _Config:
                def __init__(self, *args: Any, **kwargs: Any) -> None:
                    pass

            class _Server:
                def __init__(self, *args: Any, **kwargs: Any) -> None:
                    pass

                async def serve(self) -> None:
                    pass

            class _UvicornModule:
                Config = _Config
                Server = _Server

            uvicorn = _UvicornModule()  # type: ignore[assignment]

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

    async def _get_audit_logs(
        self, limit: int = 100, since: str | None = None, root_instance_id: str | None = None
    ) -> dict[str, Any]:
        """Get audit logs from the logging system.

        Args:
            limit: Maximum number of logs to return
            since: Filter logs after this timestamp
            root_instance_id: Optional root instance ID to filter logs by specific network
        """
        import json
        from pathlib import Path

        log_dir = Path(self.config.log_dir) / "audit"
        today = datetime.utcnow().strftime("%Y%m%d")
        audit_file = log_dir / f"audit_{today}.jsonl"

        # Get network instance IDs if filtering by root
        network_instance_ids = None
        if root_instance_id:
            active_instances = {
                instance_id: instance_data
                for instance_id, instance_data in self.instance_manager.instances.items()
                if instance_data.get("state") != "terminated"
            }
            network_instance_ids = self._get_network_instances(active_instances, root_instance_id)

        logs = []
        if audit_file.exists():
            with open(audit_file) as f:
                for line in f:
                    if line.strip():
                        log_entry = json.loads(line)

                        # Filter by network if specified
                        if network_instance_ids is not None:
                            log_instance_id = log_entry.get("instance_id")
                            if log_instance_id and log_instance_id not in network_instance_ids:
                                continue

                        # Filter by timestamp
                        if since:
                            if log_entry["timestamp"] >= since:
                                logs.append(log_entry)
                        else:
                            logs.append(log_entry)

        return {
            "logs": logs[-limit:] if logs else [],
            "total": len(logs),
            "file": str(audit_file),
            "filtered_by_network": root_instance_id is not None,
        }

    async def _get_instance_logs(
        self, instance_id: str, limit: int = 100, since: str | None = None
    ) -> dict[str, Any]:
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
            "file": str(instance_log),
        }

    async def _get_communication_logs(
        self, instance_id: str, limit: int = 100, since: str | None = None
    ) -> dict[str, Any]:
        """Get communication logs for an instance."""
        import json
        from pathlib import Path

        log_dir = Path(self.config.log_dir) / "instances" / instance_id
        comm_log = log_dir / "communication.jsonl"

        if not comm_log.exists():
            raise HTTPException(
                status_code=404, detail=f"No communication logs found for instance {instance_id}"
            )

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
            "file": str(comm_log),
        }

    async def _get_network_hierarchy(self, root_instance_id: str | None = None) -> dict[str, Any]:
        """Get complete network hierarchy with parent-child relationships.

        Args:
            root_instance_id: Optional root instance ID to filter hierarchy by specific network
        """
        instances = self.instance_manager.instances

        # Filter out terminated instances
        active_instances = {
            instance_id: instance_data
            for instance_id, instance_data in instances.items()
            if instance_data.get("state") != "terminated"
        }

        # If root_instance_id specified, filter to only that network
        if root_instance_id:
            network_instances = self._get_network_instances(active_instances, root_instance_id)
            active_instances = {
                instance_id: instance_data
                for instance_id, instance_data in active_instances.items()
                if instance_id in network_instances
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
                "created_at": instance_data.get("created_at"),
                "total_tokens": instance_data.get("total_tokens_used", 0),
                "total_cost": instance_data.get("total_cost", 0.0),
                "request_count": instance_data.get("request_count", 0),
                "children": [],
            }
            instance_map[instance_id] = instance_info

        # Build parent-child relationships and identify roots
        root_instances = []
        for _instance_id, instance_info in instance_map.items():
            parent_id = instance_info["parent_id"]
            if parent_id and parent_id in instance_map:
                # Add to parent's children
                instance_map[parent_id]["children"].append(instance_info)
            else:
                # Root instance (no parent or parent not found)
                root_instances.append(instance_info)

        # Return only hierarchical tree (roots with nested children)
        return {"total_instances": len(active_instances), "instances": root_instances}

    def _get_network_instances(self, instances: dict[str, dict], root_id: str) -> set[str]:
        """Get all instance IDs in a network (root + all descendants).

        Args:
            instances: Dictionary of instance_id -> instance_data
            root_id: Root instance ID to start from

        Returns:
            Set of instance IDs in the network
        """
        if root_id not in instances:
            return set()

        network = {root_id}
        to_process = [root_id]

        while to_process:
            current_id = to_process.pop()
            # Find all children of current instance
            for instance_id, instance_data in instances.items():
                if instance_data.get("parent_instance_id") == current_id:
                    if instance_id not in network:
                        network.add(instance_id)
                        to_process.append(instance_id)

        return network

    async def _health_check_loop(self):
        """Background health check loop."""
        while True:
            try:
                await self.instance_manager.health_check()
                await asyncio.sleep(60)  # Health check every minute
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(10)  # Retry in 10 seconds on error

    def _cleanup_orphaned_tmux_sessions(self):
        """Clean up tmux sessions from previous server runs.

        Kills all madrox-* tmux sessions to ensure UI shows only current session instances.
        """
        import subprocess

        try:
            # Get all madrox tmux sessions
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                session_count = 0
                for line in result.stdout.strip().split("\n"):
                    if line.startswith("madrox-"):
                        # Kill the session
                        subprocess.run(
                            ["tmux", "kill-session", "-t", line], capture_output=True, check=False
                        )
                        session_count += 1

                if session_count > 0:
                    logger.info(
                        f"Cleaned up {session_count} orphaned tmux sessions from previous runs"
                    )
        except Exception as e:
            logger.warning(f"Failed to cleanup orphaned tmux sessions: {e}")


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
