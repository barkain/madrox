"""Shared state manager for cross-process IPC using multiprocessing.Manager.

This module provides the SharedStateManager class that enables communication
between isolated Claude instances running in separate processes via STDIO transport.

The implementation uses multiprocessing.Manager to create proxy objects (queues,
dicts, locks) that can be safely shared across process boundaries, solving the
limitation of asyncio.Queue which is local to a single process.
"""

import logging
from datetime import datetime
from multiprocessing import Lock, Manager, Queue
from multiprocessing.managers import DictProxy
from typing import Any

logger = logging.getLogger(__name__)


class SharedStateManager:
    """Manages shared state using multiprocessing.Manager for IPC.

    This class provides a centralized interface for managing cross-process
    communication state, including:
    - Response queues for bidirectional messaging
    - Message registry for tracking message lifecycle
    - Instance metadata for coordination
    - Locks for thread-safe operations

    The Manager daemon runs in a separate process and provides proxy objects
    that can be safely accessed from multiple processes.

    Attributes:
        manager: The multiprocessing.Manager instance (daemon process)
        response_queues: Dict mapping instance_id to response Queue
        message_registry: Shared dict for storing message envelopes
        instance_metadata: Shared dict for storing instance information
        queue_locks: Dict mapping instance_id to Lock for synchronization
    """

    def __init__(self) -> None:
        """Initialize the SharedStateManager and start the Manager daemon.

        Creates the multiprocessing.Manager and initializes shared data structures.
        The Manager daemon will run until shutdown() is called.
        """
        try:
            self.manager: Manager = Manager()
            logger.info("Multiprocessing Manager daemon started")

            # Shared queues for message passing (instance_id -> Queue)
            self.response_queues: dict[str, Queue] = {}

            # Shared dicts for state synchronization
            self.message_registry: DictProxy = self.manager.dict()
            self.instance_metadata: DictProxy = self.manager.dict()

            # Locks for thread-safe operations (instance_id -> Lock)
            self.queue_locks: dict[str, Lock] = {}

            logger.info("SharedStateManager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize SharedStateManager: {e}")
            raise

    def create_response_queue(self, instance_id: str, maxsize: int = 100) -> Queue:
        """Create a new response queue for an instance.

        This method should be called when spawning a new instance to ensure
        the queue is ready before the instance starts processing messages.

        Args:
            instance_id: Unique identifier for the instance
            maxsize: Maximum number of messages in the queue (default: 100)

        Returns:
            The newly created Queue object

        Raises:
            ValueError: If a queue already exists for this instance_id
            Exception: If queue creation fails
        """
        try:
            if instance_id in self.response_queues:
                logger.warning(
                    f"Queue already exists for instance {instance_id}, returning existing queue"
                )
                return self.response_queues[instance_id]

            # Create queue and lock
            queue = self.manager.Queue(maxsize=maxsize)
            lock = self.manager.Lock()

            self.response_queues[instance_id] = queue
            self.queue_locks[instance_id] = lock

            logger.info(f"Created response queue for instance {instance_id} (maxsize={maxsize})")
            return queue
        except Exception as e:
            logger.error(f"Failed to create response queue for {instance_id}: {e}")
            raise

    def get_response_queue(self, instance_id: str) -> Queue:
        """Get response queue for an instance (creates if doesn't exist).

        This is a convenience method that ensures a queue exists for the given
        instance_id. If no queue exists, it will be created automatically.

        Args:
            instance_id: Unique identifier for the instance

        Returns:
            The Queue object for this instance

        Raises:
            Exception: If queue creation or retrieval fails
        """
        try:
            if instance_id not in self.response_queues:
                logger.debug(f"Queue not found for {instance_id}, creating new queue")
                return self.create_response_queue(instance_id)
            return self.response_queues[instance_id]
        except Exception as e:
            logger.error(f"Failed to get response queue for {instance_id}: {e}")
            raise

    def register_message(self, message_id: str, envelope_dict: dict[str, Any]) -> None:
        """Register a message envelope in shared state.

        Stores a message envelope in the shared message registry for tracking
        across process boundaries. The envelope should be converted to a plain
        dict (via MessageEnvelope.to_dict()) before passing to this method.

        Args:
            message_id: Unique message identifier (correlation ID)
            envelope_dict: Message envelope as a dictionary

        Raises:
            ValueError: If message_id is empty or envelope_dict is invalid
            Exception: If registration fails
        """
        try:
            if not message_id:
                raise ValueError("message_id cannot be empty")

            if not isinstance(envelope_dict, dict):
                raise ValueError("envelope_dict must be a dictionary")

            # Ensure envelope has required fields
            required_fields = ["message_id", "sender_id", "recipient_id", "status"]
            missing_fields = [field for field in required_fields if field not in envelope_dict]
            if missing_fields:
                raise ValueError(f"envelope_dict missing required fields: {missing_fields}")

            self.message_registry[message_id] = envelope_dict
            logger.debug(
                f"Registered message {message_id} from {envelope_dict.get('sender_id')} "
                f"to {envelope_dict.get('recipient_id')}"
            )
        except Exception as e:
            logger.error(f"Failed to register message {message_id}: {e}")
            raise

    def update_message_status(self, message_id: str, status: str, **kwargs: Any) -> None:
        """Update message status in shared registry.

        Updates the status and any additional fields of a registered message.
        This method is thread-safe and can be called from any process.

        Args:
            message_id: Message identifier to update
            status: New status value (e.g., "replied", "timeout", "error")
            **kwargs: Additional fields to update in the envelope

        Raises:
            KeyError: If message_id is not found in registry
            Exception: If update fails
        """
        try:
            if message_id not in self.message_registry:
                logger.warning(f"Attempted to update non-existent message {message_id}")
                raise KeyError(f"Message {message_id} not found in registry")

            # DictProxy requires getting, modifying, and setting the whole dict
            envelope = dict(self.message_registry[message_id])
            envelope["status"] = status
            envelope.update(kwargs)

            # Update timestamp
            envelope["updated_at"] = datetime.now().isoformat()

            self.message_registry[message_id] = envelope
            logger.debug(
                f"Updated message {message_id} status to {status} with {len(kwargs)} additional fields"
            )
        except Exception as e:
            logger.error(f"Failed to update message {message_id}: {e}")
            raise

    def get_message_envelope(self, message_id: str) -> dict[str, Any] | None:
        """Get a message envelope from the registry.

        Args:
            message_id: Message identifier to retrieve

        Returns:
            Message envelope as a dictionary, or None if not found

        Raises:
            Exception: If retrieval fails
        """
        try:
            if message_id in self.message_registry:
                return dict(self.message_registry[message_id])
            logger.debug(f"Message {message_id} not found in registry")
            return None
        except Exception as e:
            logger.error(f"Failed to get message envelope {message_id}: {e}")
            raise

    def cleanup_instance(self, instance_id: str) -> None:
        """Clean up shared resources for a terminated instance.

        This method should be called when an instance is terminated to prevent
        resource leaks. It drains any remaining messages in the queue and removes
        all associated data structures.

        Args:
            instance_id: Instance identifier to clean up

        Raises:
            Exception: If cleanup fails (non-critical, will be logged)
        """
        try:
            logger.info(f"Cleaning up shared resources for instance {instance_id}")

            # Clean up response queue
            if instance_id in self.response_queues:
                queue = self.response_queues[instance_id]

                # Drain the queue
                drained_count = 0
                while not queue.empty():
                    try:
                        queue.get_nowait()
                        drained_count += 1
                    except Exception:
                        # Queue might be empty or have race condition
                        break

                if drained_count > 0:
                    logger.warning(
                        f"Drained {drained_count} unprocessed messages from {instance_id} queue"
                    )

                del self.response_queues[instance_id]
                logger.debug(f"Removed response queue for {instance_id}")

            # Clean up lock
            if instance_id in self.queue_locks:
                del self.queue_locks[instance_id]
                logger.debug(f"Removed lock for {instance_id}")

            # Clean up instance metadata
            if instance_id in self.instance_metadata:
                del self.instance_metadata[instance_id]
                logger.debug(f"Removed metadata for {instance_id}")

            # Note: We don't clean up messages in message_registry as they may
            # be needed for debugging or audit purposes. Consider adding a
            # separate cleanup_old_messages() method with a retention policy.

            logger.info(f"Successfully cleaned up resources for {instance_id}")
        except Exception as e:
            logger.error(f"Error during cleanup of instance {instance_id}: {e}", exc_info=True)
            # Don't raise - cleanup errors are logged but not critical

    def get_queue_depth(self, instance_id: str) -> int | None:
        """Get the current depth (number of messages) in an instance's queue.

        Args:
            instance_id: Instance identifier

        Returns:
            Number of messages in queue, or None if queue doesn't exist

        Raises:
            Exception: If queue size check fails
        """
        try:
            if instance_id not in self.response_queues:
                return None
            return self.response_queues[instance_id].qsize()
        except Exception as e:
            logger.error(f"Failed to get queue depth for {instance_id}: {e}")
            return None

    def shutdown(self) -> None:
        """Shutdown the manager and clean up all resources.

        This method should be called during orchestrator shutdown to properly
        clean up the Manager daemon and all shared resources. After calling
        this method, the SharedStateManager instance is no longer usable.

        Raises:
            Exception: If shutdown fails (non-critical, will be logged)
        """
        try:
            logger.info("Shutting down SharedStateManager")

            # Clean up all instance queues
            instance_ids = list(self.response_queues.keys())
            for instance_id in instance_ids:
                try:
                    self.cleanup_instance(instance_id)
                except Exception as e:
                    logger.error(f"Error cleaning up {instance_id} during shutdown: {e}")

            # Shutdown the Manager daemon
            logger.info("Shutting down Manager daemon")
            self.manager.shutdown()

            logger.info("SharedStateManager shutdown complete")
        except Exception as e:
            logger.error(f"Error during SharedStateManager shutdown: {e}", exc_info=True)
            # Don't raise - shutdown errors are logged but allow process to exit

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the shared state.

        Returns:
            Dictionary containing current state statistics

        Raises:
            Exception: If stats collection fails
        """
        try:
            stats = {
                "active_queues": len(self.response_queues),
                "active_locks": len(self.queue_locks),
                "registered_messages": len(self.message_registry),
                "instance_metadata_count": len(self.instance_metadata),
                "queue_depths": {},
            }

            # Add queue depth for each instance
            for instance_id in self.response_queues.keys():
                depth = self.get_queue_depth(instance_id)
                if depth is not None:
                    stats["queue_depths"][instance_id] = depth

            return stats
        except Exception as e:
            logger.error(f"Failed to get SharedStateManager stats: {e}")
            return {"error": str(e)}

    def __repr__(self) -> str:
        """String representation of SharedStateManager."""
        try:
            stats = self.get_stats()
            return (
                f"SharedStateManager("
                f"queues={stats.get('active_queues', 0)}, "
                f"messages={stats.get('registered_messages', 0)}, "
                f"metadata={stats.get('instance_metadata_count', 0)})"
            )
        except Exception:
            return "SharedStateManager(error retrieving stats)"
