"""PTY-based Claude instance for persistent sessions."""

import asyncio
import json
import logging
import os
import pty
import select
import subprocess
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PTYInstance:
    """Manages a persistent Claude CLI instance via PTY."""

    def __init__(self, instance_id: str, instance_config: dict[str, Any]):
        self.instance_id = instance_id
        self.config = instance_config
        self.master_fd: int | None = None
        self.slave_fd: int | None = None
        self.process: subprocess.Popen | None = None
        self.output_buffer: list[str] = []
        self.response_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.running = False
        self._read_thread: threading.Thread | None = None

    async def start(self):
        """Start the persistent Claude CLI session."""
        try:
            # Create PTY
            self.master_fd, self.slave_fd = pty.openpty()

            # Build Claude CLI command for interactive session
            cmd = [
                "claude",
                "--input-format", "stream-json",
                "--output-format", "stream-json",
                "--dangerously-skip-permissions"  # For workspace operations
            ]

            # Set working directory
            working_dir = (
                str(Path.cwd())
                if self.config.get("bypass_isolation", False)
                else self.config["workspace_dir"]
            )

            # Start process
            self.process = subprocess.Popen(
                cmd,
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                cwd=working_dir,
                env=os.environ.copy(),
                preexec_fn=os.setsid
            )

            self.running = True

            # Start background thread to read output
            self._read_thread = threading.Thread(
                target=self._read_output_loop,
                daemon=True
            )
            self._read_thread.start()

            # Send initial system prompt
            await self._send_system_prompt()

            logger.info(f"PTY instance {self.instance_id} started successfully")

        except Exception as e:
            logger.error(f"Failed to start PTY instance {self.instance_id}: {e}")
            await self.cleanup()
            raise

    async def send_message(self, message: str, timeout: int = 30) -> dict[str, Any]:
        """Send a message and wait for response."""
        if not self.running:
            raise RuntimeError("PTY instance not running")

        try:
            # Create message in stream-json format
            message_data = {
                "type": "user_message",
                "content": message,
                "timestamp": datetime.now(UTC).isoformat()
            }

            # Send to Claude CLI via PTY
            if self.master_fd is None:
                raise RuntimeError("PTY master file descriptor is None")
            message_json = json.dumps(message_data) + "\n"
            os.write(self.master_fd, message_json.encode('utf-8'))

            # Wait for response
            response = await asyncio.wait_for(
                self.response_queue.get(),
                timeout=timeout
            )

            return response

        except TimeoutError:
            logger.warning(f"Timeout waiting for response from PTY instance {self.instance_id}")
            raise
        except Exception as e:
            logger.error(f"Error sending message to PTY instance {self.instance_id}: {e}")
            raise

    async def _send_system_prompt(self):
        """Send initial system prompt to establish context."""
        if self.master_fd is None:
            raise RuntimeError("PTY master file descriptor is None")

        system_message = {
            "type": "system_message",
            "content": self.config.get("context", ""),
            "timestamp": datetime.now(UTC).isoformat()
        }

        system_json = json.dumps(system_message) + "\n"
        os.write(self.master_fd, system_json.encode('utf-8'))

    def _read_output_loop(self):
        """Background thread to continuously read PTY output."""
        buffer = ""

        while self.running:
            try:
                # Check if data is available
                if self.master_fd is not None and select.select([self.master_fd], [], [], 0.1)[0]:
                    data = os.read(self.master_fd, 4096).decode('utf-8', errors='ignore')
                    buffer += data

                    # Process complete JSON messages
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if line.strip():
                            self._process_output_line(line.strip())

            except Exception as e:
                if self.running:  # Only log if we're supposed to be running
                    logger.error(f"Error reading from PTY {self.instance_id}: {e}")
                break

    def _process_output_line(self, line: str):
        """Process a line of output from Claude CLI."""
        try:
            data = json.loads(line)

            # Check if this is a response message
            if data.get("type") == "assistant_message" or "content" in data:
                # Queue the response for the waiting send_message call
                try:
                    self.response_queue.put_nowait({
                        "instance_id": self.instance_id,
                        "response": data.get("content", str(data)),
                        "timestamp": datetime.now(UTC).isoformat(),
                        "raw_data": data
                    })
                except asyncio.QueueFull:
                    logger.warning(f"Response queue full for instance {self.instance_id}")

        except json.JSONDecodeError:
            # Non-JSON output, might be Claude CLI status messages
            logger.debug(f"Non-JSON output from {self.instance_id}: {line}")

    async def cleanup(self):
        """Clean up PTY resources."""
        self.running = False

        try:
            if self.process:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()

            if self.master_fd:
                os.close(self.master_fd)
            if self.slave_fd:
                os.close(self.slave_fd)

            if self._read_thread and self._read_thread.is_alive():
                self._read_thread.join(timeout=2)

            logger.info(f"PTY instance {self.instance_id} cleaned up")

        except Exception as e:
            logger.error(f"Error cleaning up PTY instance {self.instance_id}: {e}")

    @property
    def is_running(self) -> bool:
        """Check if the PTY instance is running."""
        return (
            self.running and
            self.process is not None and
            self.process.poll() is None
        )
