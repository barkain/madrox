"""Instance messaging MCP tools and helpers."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from ..compat import UTC
from ._mcp import mcp

logger = logging.getLogger(__name__)


class MessagingMixin:
    """MCP tools for inter-instance communication."""

    # Declared by InstanceManager; present here for type checking only
    instances: dict[str, dict[str, Any]]
    tmux_manager: Any
    shared_state_manager: Any
    _get_children_internal: Any

    @mcp.tool
    async def send_to_instance(
        self,
        instance_id: str,
        message: str,
        wait_for_response: bool = False,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        """Send a message to a specific Claude instance (non-blocking by default).

        Args:
            instance_id: ID of the target instance
            message: Message to send
            wait_for_response: Set to true to wait for response
            timeout_seconds: Timeout in seconds (default 180)

        Returns:
            Dictionary with response or status
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        if instance.get("instance_type") in ["claude", "codex"]:
            result = await self.tmux_manager.send_message(
                instance_id=instance_id,
                message=message,
                wait_for_response=wait_for_response,
                timeout_seconds=timeout_seconds,
            )
            return result or {"status": "message_sent"}

        raise ValueError(f"Unsupported instance type: {instance.get('instance_type')}")

    @mcp.tool
    async def send_to_multiple_instances(
        self,
        instance_ids: list[str],
        message: str,
        wait_for_responses: bool = False,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        """Send the same message to multiple instances in parallel.

        Args:
            instance_ids: List of instance IDs to send to
            message: Message to send
            wait_for_responses: Wait for responses from all instances
            timeout_seconds: Timeout in seconds

        Returns:
            Dictionary with results for each instance
        """
        results: dict[str, list[Any]] = {"sent": [], "errors": []}
        tasks = []
        for instance_id in instance_ids:
            tasks.append(
                self.send_to_instance(
                    instance_id=instance_id,
                    message=message,
                    wait_for_response=wait_for_responses,
                    timeout_seconds=timeout_seconds,
                )
            )

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for i, instance_id in enumerate(instance_ids):
            response = responses[i]
            if isinstance(response, Exception):
                results["errors"].append({"instance_id": instance_id, "error": str(response)})
            else:
                results["sent"].append({"instance_id": instance_id, "response": response})

        return results

    @mcp.tool
    async def get_instance_output(
        self,
        instance_id: str,
        limit: int = 100,
        since: str | None = None,
    ) -> dict[str, Any]:
        """Get recent output from a Claude instance.

        Args:
            instance_id: ID of the instance
            limit: Maximum number of messages to retrieve
            since: ISO timestamp filter

        Returns:
            Dictionary with output messages
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        if instance_id not in self.tmux_manager.message_history:
            return {"instance_id": instance_id, "output": []}

        messages = self.tmux_manager.message_history[instance_id]

        output_messages = []
        for i, msg in enumerate(messages):
            output_messages.append(
                {
                    "instance_id": instance_id,
                    "timestamp": instance["last_activity"],
                    "type": "user" if msg["role"] == "user" else "response",
                    "content": msg["content"],
                    "message_index": i,
                }
            )

        if since:
            since_dt = datetime.fromisoformat(since)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=UTC)
            last_activity = datetime.fromisoformat(instance["last_activity"])
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=UTC)
            if last_activity < since_dt:
                return {"instance_id": instance_id, "output": []}

        if len(output_messages) > limit:
            output_messages = output_messages[-limit:]

        return {"instance_id": instance_id, "output": output_messages}

    async def _get_output_messages(
        self, instance_id: str, limit: int = 100, since: str | None = None
    ) -> list[dict[str, Any]]:
        """Internal helper to get output messages for an instance."""
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        if instance_id not in self.tmux_manager.message_history:
            return []

        messages = self.tmux_manager.message_history[instance_id]

        output_messages = []
        for i, msg in enumerate(messages):
            output_messages.append(
                {
                    "instance_id": instance_id,
                    "timestamp": instance["last_activity"],
                    "type": "user" if msg["role"] == "user" else "response",
                    "content": msg["content"],
                    "message_index": i,
                }
            )

        if since:
            since_dt = datetime.fromisoformat(since)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=UTC)
            last_activity = datetime.fromisoformat(instance["last_activity"])
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=UTC)
            if last_activity < since_dt:
                return []

        if len(output_messages) > limit:
            output_messages = output_messages[-limit:]

        return output_messages

    @mcp.tool
    async def get_multiple_instance_outputs(
        self,
        instance_ids: list[str],
        limit: int = 100,
        since: str | None = None,
    ) -> dict[str, Any]:
        """Get recent output from multiple instances.

        Args:
            instance_ids: List of instance IDs
            limit: Maximum number of messages per instance
            since: ISO timestamp filter

        Returns:
            Dictionary with outputs for each instance
        """
        results: dict[str, list[Any]] = {"outputs": [], "errors": []}
        for instance_id in instance_ids:
            try:
                output = await self._get_output_messages(instance_id, limit, since)
                results["outputs"].append({"instance_id": instance_id, "output": output})
            except Exception as e:
                results["errors"].append({"instance_id": instance_id, "error": str(e)})
        return results

    @mcp.tool
    async def reply_to_caller(
        self,
        instance_id: str,
        reply_message: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Reply back to the instance/coordinator that sent you a message.

        Args:
            instance_id: Your instance ID (the responder)
            reply_message: Your reply content
            correlation_id: Message ID from the incoming message (optional)

        Returns:
            Dictionary with reply status
        """
        return await self.handle_reply_to_caller(
            instance_id=instance_id,
            reply_message=reply_message,
            correlation_id=correlation_id,
        )

    async def _get_pending_replies_internal(
        self,
        instance_id: str,
        wait_timeout: int = 0,
    ) -> list[dict[str, Any]]:
        """Internal method to check for pending replies."""
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        replies = []

        if self.tmux_manager.shared_state:
            if wait_timeout > 0:
                try:
                    first_reply = await self.tmux_manager._get_from_shared_queue(
                        instance_id, timeout=wait_timeout
                    )
                    replies.append(first_reply)
                except TimeoutError:
                    return []

            while True:
                try:
                    reply = await self.tmux_manager._get_from_shared_queue(instance_id, timeout=0)
                    replies.append(reply)
                except (TimeoutError, Exception):
                    break
        else:
            if instance_id not in self.tmux_manager.response_queues:
                return []

            queue = self.tmux_manager.response_queues[instance_id]

            if wait_timeout > 0:
                try:
                    first_reply = await asyncio.wait_for(queue.get(), timeout=wait_timeout)
                    replies.append(first_reply)
                except TimeoutError:
                    return []

            while not queue.empty():
                try:
                    reply = queue.get_nowait()
                    replies.append(reply)
                except asyncio.QueueEmpty:
                    break

        return replies

    @mcp.tool
    async def get_pending_replies(
        self,
        instance_id: str,
        wait_timeout: int = 0,
    ) -> list[dict[str, Any]]:
        """Check for pending replies from children or other instances.

        When children use reply_to_caller, their replies are queued in the parent's
        response queue. This tool allows the parent to poll for these queued replies.

        Args:
            instance_id: Your instance ID (to check your inbox)
            wait_timeout: Seconds to wait for at least one reply (0 = non-blocking)

        Returns:
            List of pending reply messages from children
        """
        return await self._get_pending_replies_internal(instance_id, wait_timeout)

    async def handle_reply_to_caller(
        self,
        instance_id: str,
        reply_message: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Handle reply from instance back to its caller."""
        if not self.shared_state_manager and instance_id not in self.instances:
            return {"success": False, "error": f"Instance {instance_id} not found"}

        return await self.tmux_manager.handle_reply_to_caller(
            instance_id=instance_id,
            reply_message=reply_message,
            correlation_id=correlation_id,
        )

    @mcp.tool
    async def broadcast_to_children(
        self, parent_id: str, message: str, wait_for_responses: bool = False
    ) -> dict[str, Any]:
        """Broadcast a message to all children of a parent.

        Args:
            parent_id: Parent instance ID
            message: Message to broadcast
            wait_for_responses: Wait for responses from all children

        Returns:
            Dictionary with results for each child
        """
        children = self._get_children_internal(parent_id)

        if not children:
            return {"children_count": 0, "results": []}

        tasks = []
        for child in children:
            tasks.append(
                self.send_to_instance(
                    instance_id=child["id"],
                    message=message,
                    wait_for_response=wait_for_responses,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        formatted_results = []
        for i, child in enumerate(children):
            result = results[i]
            if isinstance(result, Exception):
                formatted_results.append(
                    {
                        "child_id": child["id"],
                        "child_name": child["name"],
                        "status": "error",
                        "error": str(result),
                    }
                )
            else:
                formatted_results.append(
                    {
                        "child_id": child["id"],
                        "child_name": child["name"],
                        "status": "sent" if not wait_for_responses else "completed",
                        "response": result if wait_for_responses else None,
                    }
                )

        return {
            "children_count": len(children),
            "results": formatted_results,
        }
