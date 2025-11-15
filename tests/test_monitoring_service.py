"""
Comprehensive Test Suite for MonitoringService

Phase 3: Background Monitoring Service - Testing
"""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest


# Mock the monitoring_service module for testing
class MockInstanceManager:
    """Mock InstanceManager for testing."""

    def __init__(self):
        self.instances = {
            "test-instance-1": {
                "status": "running",
                "name": "test_agent_1"
            },
            "test-instance-2": {
                "status": "busy",
                "name": "test_agent_2"
            },
            "test-instance-3": {
                "status": "completed",
                "name": "test_agent_3"
            }
        }

    def get_all_instances(self):
        """Return all instances."""
        return self.instances

    def get_instance_output(self, instance_id: str, limit: int = 1000):
        """Return mock output for an instance."""
        return {
            "output": f"Mock output for {instance_id}\nLine 2\nLine 3"
        }


class MockLLMSummarizer:
    """Mock LLMSummarizer for testing."""

    async def summarize_activity(
        self,
        instance_id: str,
        activity_text: str,
        max_tokens: int = 200
    ) -> str:
        """Generate a mock summary."""
        return f"Summary for {instance_id}: Agent is working on tasks..."


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_instance_manager():
    """Provide a mock instance manager."""
    return MockInstanceManager()


@pytest.fixture
def mock_llm_summarizer():
    """Provide a mock LLM summarizer."""
    return MockLLMSummarizer()


@pytest.fixture
async def monitoring_service(temp_storage, mock_instance_manager, mock_llm_summarizer):
    """Create a MonitoringService instance for testing."""
    from orchestrator.monitoring_service import MonitoringService

    # Reset singleton
    MonitoringService._instance = None  # type: ignore[assignment]
    MonitoringService._lock = None  # type: ignore[assignment]

    service = await MonitoringService.get_instance(
        instance_manager=mock_instance_manager,
        llm_summarizer=mock_llm_summarizer,
        poll_interval=1,  # Short interval for testing
        storage_path=temp_storage
    )

    yield service

    # Cleanup
    if service.is_running():
        await service.stop()


# ============================================================================
# Lifecycle Tests
# ============================================================================

@pytest.mark.asyncio
async def test_monitoring_service_start_stop(monitoring_service):
    """Test that MonitoringService can start and stop."""
    # Should not be running initially
    assert not monitoring_service.is_running()

    # Start the service
    await monitoring_service.start()
    assert monitoring_service.is_running()

    # Stop the service
    await monitoring_service.stop()
    assert not monitoring_service.is_running()


@pytest.mark.asyncio
async def test_monitoring_service_cannot_start_twice(monitoring_service):
    """Test that MonitoringService raises error if started twice."""
    await monitoring_service.start()

    # Try to start again
    with pytest.raises(RuntimeError, match="already running"):
        await monitoring_service.start()

    await monitoring_service.stop()


@pytest.mark.asyncio
async def test_monitoring_service_singleton(mock_instance_manager, mock_llm_summarizer, temp_storage):
    """Test that MonitoringService follows singleton pattern."""
    import sys
    sys.path.insert(0, '/tmp/claude_orchestrator/3d87bec8-6946-4e57-b250-4f7485c93169/src')

    from orchestrator.monitoring_service import MonitoringService

    # Reset singleton
    MonitoringService._instance = None  # type: ignore[assignment]
    MonitoringService._lock = None  # type: ignore[assignment]

    instance1 = await MonitoringService.get_instance(
        instance_manager=mock_instance_manager,
        llm_summarizer=mock_llm_summarizer,
        storage_path=temp_storage
    )

    instance2 = await MonitoringService.get_instance(
        instance_manager=mock_instance_manager,
        llm_summarizer=mock_llm_summarizer,
        storage_path=temp_storage
    )

    # Both should be the same instance
    assert instance1 is instance2


# ============================================================================
# Persistence Tests
# ============================================================================

@pytest.mark.asyncio
async def test_summary_persistence(monitoring_service, temp_storage):
    """Test that summaries are persisted to disk."""
    # Start and let it run for a bit
    await monitoring_service.start()
    await asyncio.sleep(2)  # Let it process at least one cycle
    await monitoring_service.stop()

    # Check that summary files were created
    storage_path = Path(temp_storage)
    instance_dirs = list(storage_path.iterdir())

    # Should have created directories for active instances
    assert len(instance_dirs) >= 1

    # Check for summary files
    for instance_dir in instance_dirs:
        if instance_dir.is_dir():
            summary_files = list(instance_dir.glob("summary_*.json"))
            assert len(summary_files) >= 1

            # Check latest.json symlink
            latest_link = instance_dir / "latest.json"
            assert latest_link.exists() or latest_link.is_symlink()


@pytest.mark.asyncio
async def test_summary_file_format(monitoring_service, temp_storage):
    """Test that summary files have correct JSON format."""
    await monitoring_service.start()
    await asyncio.sleep(2)
    await monitoring_service.stop()

    # Find a summary file
    storage_path = Path(temp_storage)
    for instance_dir in storage_path.iterdir():
        if instance_dir.is_dir():
            summary_files = list(instance_dir.glob("summary_*.json"))
            if summary_files:
                with open(summary_files[0]) as f:
                    data = json.load(f)

                # Check required fields
                assert 'instance_id' in data
                assert 'timestamp' in data
                assert 'status' in data
                assert 'summary' in data
                assert 'metadata' in data

                # Check metadata fields
                metadata = data['metadata']
                assert 'output_length' in metadata
                assert 'error_count' in metadata
                assert 'generation_time_ms' in metadata
                assert 'poll_interval' in metadata

                break


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.asyncio
async def test_error_backoff(monitoring_service):
    """Test that error backoff works correctly."""
    instance_id = "test-instance-error"

    # Simulate errors
    for _ in range(3):
        monitoring_service._record_error(instance_id)

    # Should be in backoff period
    assert monitoring_service._should_skip_instance(instance_id)

    # Check backoff calculation
    assert monitoring_service._get_backoff_seconds(1) == 2
    assert monitoring_service._get_backoff_seconds(3) == 8
    assert monitoring_service._get_backoff_seconds(10) == 300  # Max


@pytest.mark.asyncio
async def test_error_recovery(monitoring_service):
    """Test that successful processing resets error count."""
    instance_id = "test-instance-recovery"

    # Record some errors
    monitoring_service._record_error(instance_id)
    monitoring_service._record_error(instance_id)
    assert monitoring_service._error_counts[instance_id] == 2

    # Record success
    monitoring_service._record_success(instance_id)

    # Error count should be reset
    assert instance_id not in monitoring_service._error_counts


# ============================================================================
# Retrieval Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_summary(monitoring_service, temp_storage):
    """Test retrieving a summary for a specific instance."""
    await monitoring_service.start()
    await asyncio.sleep(2)
    await monitoring_service.stop()

    # Get summary for an instance
    storage_path = Path(temp_storage)
    instance_dirs = list(storage_path.iterdir())

    if instance_dirs and instance_dirs[0].is_dir():
        instance_id = instance_dirs[0].name
        summary = await monitoring_service.get_summary(instance_id)

        assert summary is not None
        assert summary['instance_id'] == instance_id
        assert 'summary' in summary


@pytest.mark.asyncio
async def test_get_all_summaries(monitoring_service, temp_storage):
    """Test retrieving all summaries."""
    await monitoring_service.start()
    await asyncio.sleep(2)
    await monitoring_service.stop()

    # Get all summaries
    summaries = await monitoring_service.get_all_summaries()

    # Should have at least one summary
    assert len(summaries) >= 1

    # Each summary should have required fields
    for instance_id, summary in summaries.items():
        assert summary['instance_id'] == instance_id
        assert 'timestamp' in summary
        assert 'summary' in summary


# ============================================================================
# MCP Adapter Tests
# ============================================================================

# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
