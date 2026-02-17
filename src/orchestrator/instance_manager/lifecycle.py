"""Instance lifecycle management MCP tools (terminate, interrupt, coordinate)."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from ..compat import UTC
from ._mcp import mcp

logger = logging.getLogger(__name__)


class LifecycleMixin:
    """MCP tools for termination, interruption, and coordination."""

    # Declared by InstanceManager; present here for type checking only
    instances: dict[str, dict[str, Any]]
    tmux_manager: Any
    jobs: dict[str, dict[str, Any]]
    send_to_instance: Any

    async def _interrupt_instance_internal(self, instance_id: str) -> dict[str, Any]:
        """Internal method to interrupt an instance."""
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        if instance.get("instance_type") in ["claude", "codex"]:
            result = await self.tmux_manager.interrupt_instance(instance_id)
            self.instances[instance_id] = self.tmux_manager.instances[instance_id]
            return result

        raise ValueError(f"Unsupported instance type: {instance.get('instance_type')}")

    @mcp.tool
    async def interrupt_instance(self, instance_id: str) -> dict[str, Any]:
        """Send interrupt signal (Ctrl+C) to a running instance.

        Args:
            instance_id: Instance ID to interrupt

        Returns:
            Status dict with success/failure info
        """
        return await self._interrupt_instance_internal(instance_id)

    @mcp.tool
    async def interrupt_multiple_instances(
        self,
        instance_ids: list[str],
    ) -> dict[str, Any]:
        """Send interrupt signal (Ctrl+C) to multiple running instances.

        Args:
            instance_ids: List of instance IDs to interrupt

        Returns:
            Dictionary with interrupt results for each instance
        """
        results: dict[str, list[Any]] = {"interrupted": [], "failed": []}
        for instance_id in instance_ids:
            try:
                result = await self._interrupt_instance_internal(instance_id)
                if result.get("success"):
                    results["interrupted"].append(instance_id)
                else:
                    results["failed"].append(
                        {"instance_id": instance_id, "error": "Failed to interrupt"}
                    )
            except Exception as e:
                results["failed"].append({"instance_id": instance_id, "error": str(e)})
        return results

    async def _terminate_instance_internal(self, instance_id: str, force: bool = False) -> bool:
        """Internal method to terminate a Claude or Codex instance."""
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        if instance.get("instance_type") in ["claude", "codex"]:
            result = await self.tmux_manager.terminate_instance(instance_id, force)
            if result:
                self.instances[instance_id] = self.tmux_manager.instances[instance_id]
            return result

        raise ValueError(f"Unsupported instance type: {instance.get('instance_type')}")

    @mcp.tool
    async def terminate_instance(
        self,
        instance_id: str,
        force: bool = False,
    ) -> dict[str, Any]:
        """Terminate a Claude instance.

        Args:
            instance_id: ID of the instance to terminate
            force: Force termination even if busy

        Returns:
            Dictionary with termination status
        """
        success = await self._terminate_instance_internal(
            instance_id=instance_id,
            force=force,
        )
        return {
            "instance_id": instance_id,
            "status": "terminated" if success else "failed",
            "success": success,
        }

    @mcp.tool
    async def terminate_multiple_instances(
        self,
        instance_ids: list[str],
        force: bool = False,
    ) -> dict[str, Any]:
        """Terminate multiple Claude instances in parallel.

        Args:
            instance_ids: List of instance IDs to terminate
            force: Force termination for all instances

        Returns:
            Dictionary with termination results
        """
        results: dict[str, list[Any]] = {"terminated": [], "failed": []}
        for iid in instance_ids:
            try:
                success = await self._terminate_instance_internal(iid, force=force)
                if success:
                    results["terminated"].append(iid)
                else:
                    results["failed"].append(iid)
            except Exception as e:
                results["failed"].append({"instance_id": iid, "error": str(e)})
        return results

    @mcp.tool
    async def coordinate_instances(
        self,
        coordinator_id: str,
        participant_ids: list[str],
        task_description: str,
        coordination_type: str = "sequential",
    ) -> dict[str, Any]:
        """Coordinate multiple instances for a complex task.

        Args:
            coordinator_id: Coordinating instance ID
            participant_ids: Participant instance IDs
            task_description: Description of the task
            coordination_type: How to coordinate (sequential, parallel, consensus)

        Returns:
            Dictionary with coordination results
        """
        task_id = str(uuid.uuid4())

        all_ids = [coordinator_id] + participant_ids
        for iid in all_ids:
            if iid not in self.instances:
                raise ValueError(f"Instance {iid} not found")
            if self.instances[iid]["state"] not in ["running", "idle"]:
                raise RuntimeError(f"Instance {iid} is not available")

        coordination_task = {
            "task_id": task_id,
            "description": task_description,
            "coordinator_id": coordinator_id,
            "participant_ids": participant_ids,
            "coordination_type": coordination_type,
            "status": "running",
            "started_at": datetime.now(UTC).isoformat(),
            "steps": [],
            "results": {},
        }

        self.jobs[task_id] = coordination_task

        logger.info(f"Started coordination task {task_id} with {len(participant_ids)} participants")

        asyncio.create_task(self._execute_coordination(coordination_task))

        return {"task_id": task_id, "status": "started"}

    async def _execute_coordination(self, coordination_task: dict[str, Any]):
        """Execute a coordination task."""
        task_id = coordination_task["task_id"]
        participant_ids = coordination_task["participant_ids"]

        try:
            logger.info(f"Executing coordination task {task_id}")

            if coordination_task["coordination_type"] == "sequential":
                for i, participant_id in enumerate(participant_ids):
                    step_result = await self.send_to_instance(
                        participant_id,
                        f"Please work on step {i + 1} of the coordination task: {coordination_task['description']}",
                    )
                    coordination_task["results"][participant_id] = step_result

            coordination_task["status"] = "completed"
            coordination_task["completed_at"] = datetime.now(UTC).isoformat()

            logger.info(f"Completed coordination task {task_id}")

        except Exception as e:
            logger.error(f"Error in coordination task {task_id}: {e}")
            coordination_task["status"] = "failed"
            coordination_task["error"] = str(e)

    @mcp.tool
    async def get_job_status(
        self, job_id: str, wait_for_completion: bool = True, max_wait: int = 120
    ) -> dict[str, Any] | None:
        """Get the status of a job.

        Args:
            job_id: Job ID to check
            wait_for_completion: If True, wait for job to complete
            max_wait: Maximum seconds to wait for completion

        Returns:
            Job status dict or None if not found
        """
        if job_id not in self.jobs:
            return None

        job = self.jobs[job_id]
        if not wait_for_completion or job["status"] in ["completed", "failed", "timeout"]:
            return job

        loop = asyncio.get_running_loop()
        start_time = loop.time()
        while loop.time() - start_time < max_wait:
            job = self.jobs[job_id]
            if job["status"] in ["completed", "failed", "timeout"]:
                return job
            await asyncio.sleep(1)

        return self.jobs[job_id]
