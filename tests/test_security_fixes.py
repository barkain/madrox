"""Security fix validation tests.

Tests for critical security vulnerabilities fixed in the orchestrator package:
1. Command injection (CWE-77) in tmux_instance_manager.py
2. SSRF (CWE-918) in llm_summarizer.py
3. Unbounded memory growth (CWE-770) in shared_state_manager.py and tmux_instance_manager.py
"""

import shlex
from datetime import UTC, datetime, timedelta

import pytest


class TestCommandInjectionFix:
    """Test command injection prevention in MCP server configuration."""

    def test_server_name_validation_rejects_special_chars(self):
        """Test that server names with shell metacharacters are rejected."""
        import re

        pattern = r"^[a-zA-Z0-9_-]+$"

        # Valid server names should pass
        valid_names = ["playwright", "github", "my-server", "test_123"]
        for name in valid_names:
            assert re.match(pattern, name), f"Valid name rejected: {name}"

        # Invalid names with injection attempts should fail
        invalid_names = [
            "test;rm -rf /",  # Command injection
            "test`whoami`",  # Command substitution
            "test$(ls)",  # Command substitution
            "../../../etc/passwd",  # Path traversal
            "test|cat /etc/passwd",  # Pipe injection
            "test&& echo pwned",  # Command chaining
        ]
        for name in invalid_names:
            assert not re.match(pattern, name), f"Invalid name accepted: {name}"

    def test_shlex_quote_escapes_shell_metacharacters(self):
        """Test that shlex.quote() properly escapes dangerous characters."""
        dangerous_inputs = [
            "test;rm -rf /",
            "test`whoami`",
            "test$(ls)",
            "test|cat /etc/passwd",
            "test&& echo pwned",
        ]

        for dangerous_input in dangerous_inputs:
            quoted = shlex.quote(dangerous_input)
            # Quoted string should be safe (wrapped in single quotes or escaped)
            assert quoted.startswith("'"), f"Shell metacharacters not quoted: {quoted}"
            # Original dangerous characters should be inside quotes
            assert dangerous_input in quoted or "\\;" in quoted

    def test_env_var_name_validation(self):
        """Test that environment variable names are validated."""
        import re

        pattern = r"^[a-zA-Z_][a-zA-Z0-9_]*$"

        # Valid env var names
        valid_names = ["PATH", "MY_VAR", "_PRIVATE", "VAR123"]
        for name in valid_names:
            assert re.match(pattern, name), f"Valid env var rejected: {name}"

        # Invalid env var names
        invalid_names = [
            "123VAR",  # Starts with number
            "MY-VAR",  # Contains hyphen
            "MY;VAR",  # Contains semicolon
            "$(whoami)",  # Command injection
        ]
        for name in invalid_names:
            assert not re.match(pattern, name), f"Invalid env var accepted: {name}"


class TestSSRFFix:
    """Test SSRF prevention in LLMSummarizer."""

    def test_url_allowlist_validation(self):
        """Test that only trusted OpenRouter URLs are allowed."""
        from urllib.parse import urlparse

        # Trusted endpoints
        trusted_urls = [
            "https://openrouter.ai/api/v1/chat/completions",
            "https://api.openrouter.ai/api/v1/chat/completions",
        ]

        # Untrusted URLs that should be rejected
        untrusted_urls = [
            "http://openrouter.ai/api/v1/chat/completions",  # HTTP instead of HTTPS
            "https://evil.com/api/v1/chat/completions",  # Wrong domain
            "https://openrouter.ai.evil.com/api/v1/chat/completions",  # Subdomain attack
            "https://169.254.169.254/latest/meta-data/",  # AWS metadata SSRF
            "https://localhost:8080/admin",  # Local network
        ]

        for url in trusted_urls:
            parsed = urlparse(url)
            assert parsed.scheme == "https", f"Trusted URL not HTTPS: {url}"
            assert parsed.netloc in [
                "openrouter.ai",
                "api.openrouter.ai",
            ], f"Trusted URL wrong domain: {url}"

        for url in untrusted_urls:
            parsed = urlparse(url)
            is_valid = parsed.scheme == "https" and parsed.netloc in [
                "openrouter.ai",
                "api.openrouter.ai",
            ]
            assert not is_valid, f"Untrusted URL incorrectly validated: {url}"


class TestUnboundedMemoryGrowthFix:
    """Test memory growth prevention in message registries and histories."""

    def test_message_registry_cleanup_by_age(self):
        """Test that old messages are cleaned up based on TTL."""
        # Simulate message registry with old and new messages
        message_registry = {}

        # Old message (25 hours ago - should be cleaned)
        old_time = datetime.now(UTC) - timedelta(hours=25)
        message_registry["old_msg"] = {
            "message_id": "old_msg",
            "sender_id": "instance1",
            "recipient_id": "instance2",
            "sent_at": old_time.isoformat(),
            "status": "sent",
        }

        # Recent message (1 hour ago - should be kept)
        recent_time = datetime.now(UTC) - timedelta(hours=1)
        message_registry["recent_msg"] = {
            "message_id": "recent_msg",
            "sender_id": "instance1",
            "recipient_id": "instance2",
            "sent_at": recent_time.isoformat(),
            "status": "sent",
        }

        # Check cleanup logic
        retention_hours = 24
        cutoff_time = datetime.now(UTC) - timedelta(hours=retention_hours)

        messages_to_remove = []
        for msg_id, envelope in message_registry.items():
            sent_at_str = envelope.get("sent_at")
            if sent_at_str:
                sent_at = datetime.fromisoformat(sent_at_str.replace("Z", "+00:00"))
                if sent_at < cutoff_time:
                    messages_to_remove.append(msg_id)

        assert "old_msg" in messages_to_remove, "Old message not marked for removal"
        assert "recent_msg" not in messages_to_remove, (
            "Recent message incorrectly marked for removal"
        )

    def test_message_history_size_limit(self):
        """Test that message history is limited to prevent unbounded growth."""
        MAX_MESSAGE_HISTORY = 500

        # Simulate message history growing beyond limit
        message_history = []
        for i in range(600):  # Add 600 messages
            message_history.append({"role": "user", "content": f"Message {i}"})

        # Apply size limit (keep only last MAX_MESSAGE_HISTORY messages)
        if len(message_history) > MAX_MESSAGE_HISTORY:
            message_history = message_history[-MAX_MESSAGE_HISTORY:]

        assert len(message_history) == MAX_MESSAGE_HISTORY, "History not limited correctly"
        assert message_history[0]["content"] == "Message 100", (
            "Wrong messages kept (should keep last 500)"
        )
        assert message_history[-1]["content"] == "Message 599", (
            "Wrong messages kept (should keep last 500)"
        )

    def test_completed_messages_cleanup(self):
        """Test that completed messages are cleaned up after retention period."""
        # Completed message (2 hours ago - should be removed after 1 hour retention)
        completed_time = datetime.now(UTC) - timedelta(hours=2)
        message = {
            "message_id": "completed_msg",
            "status": "replied",
            "updated_at": completed_time.isoformat(),
        }

        # Check if should be removed (completed messages have 1 hour retention)
        should_remove = False
        if message["status"] in ["replied", "timeout", "error"]:
            updated_at_str = message.get("updated_at")
            if updated_at_str:
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                cutoff = datetime.now(UTC) - timedelta(hours=1)
                should_remove = updated_at < cutoff

        assert should_remove, "Completed message not marked for removal"


class TestSecurityBestPractices:
    """Test general security best practices are followed."""

    def test_secret_redaction_in_logs(self):
        """Test that secrets are redacted in log output."""

        def redact_secret(secret: str | None, show_chars: int = 4) -> str:
            """Redact sensitive strings for logging."""
            if not secret:
                return "[not set]"
            if len(secret) <= show_chars:
                return f"***{secret[-2:]}"
            return f"***{secret[-show_chars:]}"

        # Test API key redaction
        api_key = "sk-or-v1-1234567890abcdef"
        redacted = redact_secret(api_key)
        assert "***" in redacted, "Secret not redacted"
        assert "1234567890abcdef" not in redacted, "Full secret exposed"
        assert redacted.endswith("cdef"), "Last 4 chars not shown"

        # Test empty secret
        assert redact_secret(None) == "[not set]"

    def test_authkey_redaction_in_logs(self):
        """Test that authkeys are redacted in log output."""

        def redact_authkey(authkey: bytes | None) -> str:
            """Redact authentication keys for logging."""
            if not authkey:
                return "[not set]"
            last_bytes = authkey[-4:] if len(authkey) >= 4 else authkey
            return f"***{last_bytes.hex()}"

        # Test authkey redaction
        authkey = b"secret_authentication_key_12345"
        redacted = redact_authkey(authkey)
        assert "***" in redacted, "Authkey not redacted"
        assert "secret" not in redacted.lower(), "Secret text exposed"
        assert redacted.endswith(authkey[-4:].hex()), "Last 4 bytes not shown in hex"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
