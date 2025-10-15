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

        If running as a child process with MADROX_MANAGER_* environment variables set,
        connects to the parent's existing Manager daemon instead of creating a new one.
        """
        import base64
        import os
        from multiprocessing.managers import BaseManager

        try:
            # Check if we should connect to an existing Manager (child process)
            manager_host = os.getenv("MADROX_MANAGER_HOST")
            manager_port_str = os.getenv("MADROX_MANAGER_PORT")
            manager_socket = os.getenv("MADROX_MANAGER_SOCKET")
            manager_authkey_b64 = os.getenv("MADROX_MANAGER_AUTHKEY")

            # Determine if we should connect (either TCP or Unix socket)
            has_tcp_address = manager_host and manager_port_str and manager_authkey_b64
            has_unix_socket = manager_socket and manager_authkey_b64

            if has_tcp_address or has_unix_socket:
                # Child process: connect to parent's Manager daemon
                manager_authkey = base64.b64decode(manager_authkey_b64)

                if has_tcp_address:
                    # TCP connection
                    manager_port = int(manager_port_str)
                    manager_address = (manager_host, manager_port)
                    logger.info(
                        f"Connecting to parent Manager daemon at {manager_host}:{manager_port} (TCP)"
                    )
                else:
                    # Unix socket connection
                    manager_address = manager_socket
                    logger.info(
                        f"Connecting to parent Manager daemon at {manager_socket} (Unix socket)"
                    )

                # Create a custom manager that connects to existing daemon
                class RemoteManager(BaseManager):
                    pass

                # Register the same types that Manager() provides
                RemoteManager.register("Queue")
                RemoteManager.register("dict")
                RemoteManager.register("Lock")

                # Connect to the existing manager
                remote_manager = RemoteManager(address=manager_address, authkey=manager_authkey)
                remote_manager.connect()
                self.manager = remote_manager
                self.is_child_connection = True

                logger.info("Successfully connected to parent Manager daemon")
            else:
                # Parent process: create new Manager daemon
                self.manager: Manager = Manager()
                self.is_child_connection = False
                logger.info("Multiprocessing Manager daemon started (parent)")

            # Store connection details for child processes
            # The Manager's address is available via _address attribute
            self.manager_address = self.manager._address
            self.manager_authkey = self.manager._authkey

            # Address can be either (host, port) tuple or Unix socket path (string)
            address_type = "unix_socket" if isinstance(self.manager_address, str) else "tcp"
            logger.info(
                f"Manager address: {self.manager_address} ({address_type}), authkey available for IPC"
            )

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

        If this is a child connection, only local resources are cleaned up,
        not the parent's Manager daemon.

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

            # Only shutdown the Manager daemon if we created it (not a child connection)
            if hasattr(self, "is_child_connection") and self.is_child_connection:
                logger.info("Child connection - not shutting down parent's Manager daemon")
            else:
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

    def health_check(self, timeout: float = 5.0) -> dict[str, Any]:
        """Perform health check on the Manager daemon.

        Tests that the Manager daemon is responsive by performing basic operations
        (creating a test queue, accessing shared dict, cleaning up).

        Args:
            timeout: Maximum time to wait for health check operations (seconds)

        Returns:
            Health check result dict with status and diagnostic info

        Example:
            >>> manager = SharedStateManager()
            >>> result = manager.health_check()
            >>> print(result)
            {'healthy': True, 'response_time_ms': 1.23, 'manager_alive': True}
        """
        import time
        from queue import Empty

        start_time = time.time()
        health_result = {
            "healthy": False,
            "manager_alive": False,
            "test_queue_created": False,
            "test_dict_accessed": False,
            "test_cleanup_completed": False,
            "response_time_ms": 0.0,
            "error": None,
        }

        try:
            # Test 1: Check if manager is still running
            if not hasattr(self.manager, "_process") or self.manager._process is None:
                health_result["error"] = "Manager process object not found"
                return health_result

            # Check if the manager process is alive
            if hasattr(self.manager._process, "is_alive"):
                is_alive = self.manager._process.is_alive()
                health_result["manager_alive"] = is_alive
                if not is_alive:
                    health_result["error"] = "Manager daemon process is dead"
                    return health_result
            else:
                # Fallback: try to use the manager
                health_result["manager_alive"] = True

            # Test 2: Create a test queue (tests Manager responsiveness)
            try:
                test_queue = self.manager.Queue(maxsize=10)
                health_result["test_queue_created"] = True
            except Exception as e:
                health_result["error"] = f"Failed to create test queue: {e}"
                return health_result

            # Test 3: Test queue operations (put/get with timeout)
            try:
                test_data = {"ping": "health_check", "timestamp": time.time()}
                test_queue.put(test_data, timeout=timeout)
                retrieved_data = test_queue.get(timeout=timeout)

                if retrieved_data != test_data:
                    health_result["error"] = "Queue data mismatch (corrupted communication)"
                    return health_result
            except Empty:
                health_result["error"] = "Queue get timeout (Manager not responding)"
                return health_result
            except Exception as e:
                health_result["error"] = f"Queue operation failed: {e}"
                return health_result

            # Test 4: Access shared dict (tests proxy object communication)
            try:
                test_key = "__health_check_test__"
                test_value = {"status": "testing", "timestamp": time.time()}
                self.instance_metadata[test_key] = test_value
                retrieved_value = self.instance_metadata.get(test_key)

                if retrieved_value != test_value:
                    health_result["error"] = "Shared dict data mismatch"
                    return health_result

                health_result["test_dict_accessed"] = True
            except Exception as e:
                health_result["error"] = f"Shared dict access failed: {e}"
                return health_result

            # Test 5: Cleanup test data
            try:
                del self.instance_metadata[test_key]
                # Queue cleanup (just let it be garbage collected)
                health_result["test_cleanup_completed"] = True
            except Exception as e:
                logger.warning(f"Health check cleanup failed (non-critical): {e}")
                # Non-critical error, don't fail health check

            # All tests passed
            elapsed_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            health_result["response_time_ms"] = round(elapsed_time, 2)
            health_result["healthy"] = True

            logger.debug(
                f"Manager health check passed ({elapsed_time:.2f}ms)",
                extra={"response_time_ms": elapsed_time},
            )

            return health_result

        except Exception as e:
            elapsed_time = (time.time() - start_time) * 1000
            health_result["response_time_ms"] = round(elapsed_time, 2)
            health_result["error"] = f"Unexpected health check error: {e}"
            logger.error(f"Manager health check failed: {e}", exc_info=True)
            return health_result

    def is_manager_alive(self) -> bool:
        """Quick check if the Manager daemon process is alive.

        This is a lightweight check that doesn't perform full health validation,
        just verifies the process is running.

        Returns:
            True if manager process is alive, False otherwise
        """
        try:
            if not hasattr(self.manager, "_process") or self.manager._process is None:
                return False

            if hasattr(self.manager._process, "is_alive"):
                return self.manager._process.is_alive()

            # Fallback: assume alive if we can't check
            return True
        except Exception as e:
            logger.error(f"Error checking manager process status: {e}")
            return False

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
