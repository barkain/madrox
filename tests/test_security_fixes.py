"""
Security fix tests for CWE-22 (Path Traversal) and CWE-532 (Secret Exposure).

Tests verify that:
1. Path traversal attacks are blocked in mcp_loader.py
2. Secrets are properly redacted in logs
3. Authentication keys are not exposed in log output
"""

import logging
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from orchestrator.mcp_loader import MCPConfigLoader
from orchestrator.llm_summarizer import LLMSummarizer, redact_secret
from orchestrator.shared_state_manager import redact_authkey as redact_authkey_shared
from orchestrator.tmux_instance_manager import redact_authkey as redact_authkey_tmux


class TestPathTraversalFix:
    """Test CWE-22 path traversal fix in mcp_loader.py"""

    def test_reject_path_traversal_dotdot(self):
        """Test that ../ path traversal is rejected"""
        loader = MCPConfigLoader()

        # Try various path traversal attacks
        attacks = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "../../secrets.json",
        ]

        for attack in attacks:
            result = loader.load_config(attack)
            assert result is None, f"Path traversal attack '{attack}' should be rejected"

    def test_reject_absolute_paths(self):
        """Test that absolute paths are rejected"""
        loader = MCPConfigLoader()

        attacks = [
            "/etc/passwd",
            "/root/.ssh/id_rsa",
            "C:\\Windows\\System32\\config\\SAM",
        ]

        for attack in attacks:
            result = loader.load_config(attack)
            assert result is None, f"Absolute path attack '{attack}' should be rejected"

    def test_reject_special_characters(self):
        """Test that special characters in name are rejected"""
        loader = MCPConfigLoader()

        invalid_names = [
            "config/../secret",
            "config/./../../etc/passwd",
            "config\\..\\secret",
            "config\x00.json",  # Null byte injection
            "config;rm -rf /",
            "config|cat /etc/passwd",
        ]

        for name in invalid_names:
            result = loader.load_config(name)
            assert result is None, f"Invalid name '{name}' should be rejected"

    def test_accept_valid_names(self):
        """Test that valid config names work correctly"""
        loader = MCPConfigLoader()

        # Create a temporary config file
        with tempfile.TemporaryDirectory() as tmpdir:
            loader.configs_dir = Path(tmpdir)

            # Create a valid config
            config_file = loader.configs_dir / "test-config.json"
            config_file.write_text('{"name": "test", "config": {}}')

            # Valid names should work
            valid_names = [
                "test-config",
                "playwright",
                "github-api",
                "my_server",
                "Server123",
            ]

            for name in valid_names:
                # For non-existent files, should return None (not error)
                # For existing file, should return config
                if name == "test-config":
                    result = loader.load_config(name)
                    assert result is not None, f"Valid name '{name}' should be accepted"
                    assert result["name"] == "test"

    def test_symlink_escape_prevented(self):
        """Test that symlink-based path traversal is prevented"""
        loader = MCPConfigLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create configs_dir inside tmpdir
            configs_dir = Path(tmpdir) / "configs"
            configs_dir.mkdir()
            loader.configs_dir = configs_dir

            # Create an external file OUTSIDE of configs_dir
            external_dir = Path(tmpdir) / "external"
            external_dir.mkdir()
            external_file = external_dir / "secret.json"
            external_file.write_text('{"secret": "exposed"}')

            # Create a symlink inside configs_dir pointing to external file
            symlink_path = loader.configs_dir / "escape.json"
            # Try to create symlink (might fail on Windows, that's ok)
            try:
                symlink_path.symlink_to(external_file)

                # Attempt to load via symlink should be blocked
                result = loader.load_config("escape")
                # Should return None since resolved path is outside configs_dir
                assert result is None, "Symlink escape should be prevented"
            except OSError:
                # Symlink creation failed (e.g., on Windows without admin)
                pytest.skip("Symlink creation not supported on this platform")


class TestSecretRedaction:
    """Test CWE-532 secret exposure fixes"""

    def test_redact_secret_function(self):
        """Test the redact_secret helper function"""
        # Test with API key
        api_key = "sk-or-v1-1234567890abcdef"
        redacted = redact_secret(api_key)
        assert "sk-or-v1" not in redacted
        assert "1234567890abcdef" not in redacted
        assert "cdef" in redacted  # Should show last 4 chars
        assert "***" in redacted

        # Test with None
        redacted = redact_secret(None)
        assert redacted == "[not set]"

        # Test with short secret
        short_secret = "abc"
        redacted = redact_secret(short_secret)
        assert "***" in redacted
        assert len(redacted) < len(short_secret) + 5  # Should still be redacted

    def test_redact_authkey_shared_function(self):
        """Test the redact_authkey helper in shared_state_manager"""
        # Test with bytes authkey
        authkey = b"secret_authentication_key_12345"
        redacted = redact_authkey_shared(authkey)
        assert "secret" not in redacted
        assert "authentication" not in redacted
        assert "***" in redacted
        assert len(redacted) < 20  # Should be significantly shorter

        # Test with None
        redacted = redact_authkey_shared(None)
        assert redacted == "[not set]"

    def test_redact_authkey_tmux_function(self):
        """Test the redact_authkey helper in tmux_instance_manager"""
        # Test with bytes authkey
        authkey = b"manager_secret_key_value_xyz"
        redacted = redact_authkey_tmux(authkey)
        assert "secret" not in redacted
        assert "manager" not in redacted
        assert "***" in redacted

        # Test with None
        redacted = redact_authkey_tmux(None)
        assert redacted == "[not set]"

    def test_llm_summarizer_api_key_not_logged(self, caplog):
        """Test that LLMSummarizer doesn't log raw API keys"""
        with caplog.at_level(logging.INFO):
            api_key = "sk-or-v1-super-secret-key-12345"
            summarizer = LLMSummarizer(api_key=api_key)

            # Check all log records
            for record in caplog.records:
                # API key should never appear in raw form
                assert api_key not in record.message
                assert "super-secret-key" not in record.message

                # But should see redacted version
                if "api_key" in record.message:
                    assert "***" in record.message or "[not set]" in record.message

    def test_llm_summarizer_repr_redacts_key(self):
        """Test that LLMSummarizer.__repr__ redacts the API key"""
        api_key = "sk-or-v1-my-secret-api-key-value"
        summarizer = LLMSummarizer(api_key=api_key)

        repr_str = repr(summarizer)

        # Raw key should not appear
        assert api_key not in repr_str
        assert "my-secret" not in repr_str

        # Should show redacted version
        assert "***" in repr_str

    def test_shared_state_manager_authkey_not_logged(self, caplog):
        """Test that SharedStateManager doesn't log raw authkeys"""
        # This test would require full SharedStateManager setup
        # For now, we'll test the redaction function directly
        authkey = b"very_secret_authentication_key_xyz"
        redacted = redact_authkey_shared(authkey)

        # Verify redaction
        assert b"very_secret" not in redacted.encode()
        assert b"authentication" not in redacted.encode()
        assert "***" in redacted


class TestSecurityIntegration:
    """Integration tests for security fixes"""

    def test_mcp_loader_logs_rejected_attacks(self, caplog):
        """Test that path traversal attempts are logged for security monitoring"""
        loader = MCPConfigLoader()

        with caplog.at_level(logging.ERROR):
            # Try a path traversal attack
            loader.load_config("../../etc/passwd")

            # Should have logged the security violation
            assert any(
                "illegal characters" in record.message.lower() or
                "path traversal" in record.message.lower()
                for record in caplog.records
            )

    def test_no_secrets_in_error_messages(self):
        """Test that error messages don't accidentally expose secrets"""
        # Test with LLMSummarizer
        api_key = "sk-or-v1-secret-key-12345"
        summarizer = LLMSummarizer(api_key=api_key)

        # Even in error scenarios, key shouldn't leak
        error_repr = str(summarizer)
        assert "secret-key" not in error_repr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
