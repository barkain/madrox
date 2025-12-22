"""Test MCP Adapter message injection and template metadata parsing."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.orchestrator.mcp_adapter import MCPAdapter


@pytest.fixture
def mock_instance_manager():
    """Mock InstanceManager for testing."""
    manager = AsyncMock()
    manager.instances = {}
    manager.jobs = {}
    manager.main_inbox = []

    # Mock FastMCP tools
    mock_tool = MagicMock()
    mock_tool.to_mcp_tool.return_value = MagicMock(
        name="test_tool",
        description="Test tool",
        inputSchema={"type": "object", "properties": {}, "required": []},
    )

    async def mock_get_tools():
        return {"test_tool": mock_tool}

    manager.mcp = MagicMock()
    manager.mcp.get_tools = mock_get_tools
    manager.get_and_clear_main_inbox = MagicMock(return_value=[])

    return manager


@pytest.fixture
def mcp_adapter(mock_instance_manager):
    """Create MCPAdapter with mocked dependencies."""
    return MCPAdapter(mock_instance_manager)


class TestMessageInjection:
    """Test _inject_main_messages functionality."""

    def test_inject_main_messages_empty_inbox(self, mcp_adapter):
        """Test injection with no pending messages."""
        result = {"content": [{"type": "text", "text": "Original"}]}

        mcp_adapter.manager.get_and_clear_main_inbox.return_value = []

        injected = mcp_adapter._inject_main_messages(result)

        assert injected == result
        assert len(injected["content"]) == 1

    def test_inject_main_messages_with_messages(self, mcp_adapter):
        """Test injection with pending messages."""
        result = {"content": [{"type": "text", "text": "Original"}]}

        mcp_adapter.manager.get_and_clear_main_inbox.return_value = [
            {"content": "Message 1 from child"},
            {"content": "Message 2 from child"},
        ]

        injected = mcp_adapter._inject_main_messages(result)

        # Should have 2 prepended messages + 1 original
        assert len(injected["content"]) == 3
        assert "Message from child instance" in injected["content"][0]["text"]
        assert "Message 1 from child" in injected["content"][0]["text"]
        assert "Message 2 from child" in injected["content"][1]["text"]
        assert injected["content"][2]["text"] == "Original"

    def test_inject_main_messages_skip_on_error(self, mcp_adapter):
        """Test that messages are not injected into error results."""
        result = {"error": "Something went wrong"}

        mcp_adapter.manager.get_and_clear_main_inbox.return_value = [
            {"content": "This should be skipped"},
        ]

        injected = mcp_adapter._inject_main_messages(result)

        # Should return unchanged
        assert injected == result
        assert "content" not in injected

    def test_inject_main_messages_no_content_field(self, mcp_adapter):
        """Test injection when result has no content field."""
        result = {"status": "success", "data": "something"}

        mcp_adapter.manager.get_and_clear_main_inbox.return_value = [
            {"content": "Message"},
        ]

        injected = mcp_adapter._inject_main_messages(result)

        # Should return unchanged (no content field to inject into)
        assert injected == result
        assert "content" not in injected

    def test_inject_main_messages_empty_content(self, mcp_adapter):
        """Test injection with message that has no content."""
        result = {"content": [{"type": "text", "text": "Original"}]}

        mcp_adapter.manager.get_and_clear_main_inbox.return_value = [
            {},  # Message with no content
        ]

        injected = mcp_adapter._inject_main_messages(result)

        # Should inject empty message
        assert len(injected["content"]) == 2
        assert "Message from child instance" in injected["content"][0]["text"]


class TestTemplateMetadataParsing:
    """Test _parse_template_metadata functionality."""

    def test_parse_template_metadata_full(self, mcp_adapter):
        """Test parsing complete template metadata."""
        template = """
        # Team Template

        Team Size: 5 instances
        Estimated Duration: 2-4 hours

        ### Technical Lead
        **Role**: `architect`
        **Priority**: High
        """

        metadata = mcp_adapter._parse_template_metadata(template)

        assert metadata["team_size"] == 5
        assert metadata["duration"] == "2-4 hours"
        assert metadata["estimated_cost"] == "$25"  # 5 * $5
        assert metadata["supervisor_role"] == "architect"

    def test_parse_template_metadata_defaults(self, mcp_adapter):
        """Test parsing with missing fields uses defaults."""
        template = """
        # Simple Template
        Just some text without metadata
        """

        metadata = mcp_adapter._parse_template_metadata(template)

        assert metadata["team_size"] == 6  # default
        assert "hours" in metadata["duration"]  # default
        assert metadata["supervisor_role"] == "general"  # default

    def test_parse_template_metadata_research_lead(self, mcp_adapter):
        """Test parsing Research Lead role."""
        template = """
        ### Research Lead
        **Role**: `data_analyst`
        """

        metadata = mcp_adapter._parse_template_metadata(template)

        assert metadata["supervisor_role"] == "data_analyst"

    def test_parse_template_metadata_security_lead(self, mcp_adapter):
        """Test parsing Security Lead role."""
        template = """
        ### Security Lead
        **Role**: `security_analyst`
        """

        metadata = mcp_adapter._parse_template_metadata(template)

        assert metadata["supervisor_role"] == "security_analyst"

    def test_parse_template_metadata_data_lead(self, mcp_adapter):
        """Test parsing Data Engineering Lead role."""
        template = """
        ### Data Engineering Lead
        **Role**: `backend_developer`
        """

        metadata = mcp_adapter._parse_template_metadata(template)

        assert metadata["supervisor_role"] == "backend_developer"

    def test_parse_template_metadata_invalid_team_size(self, mcp_adapter):
        """Test parsing with invalid team size."""
        template = """
        Team Size: invalid instances
        """

        metadata = mcp_adapter._parse_template_metadata(template)

        # Should use default
        assert metadata["team_size"] == 6

    def test_parse_template_metadata_duration_with_colon(self, mcp_adapter):
        """Test parsing duration with colon format."""
        template = """
        Duration: 6-8 hours with testing
        """

        metadata = mcp_adapter._parse_template_metadata(template)

        assert "6-8 hours with testing" in metadata["duration"]

    def test_parse_template_metadata_multiple_roles(self, mcp_adapter):
        """Test parsing template with multiple role sections."""
        template = """
        ### Technical Lead
        **Role**: `architect`

        ### Other Section
        **Role**: `general`

        ### Another Role
        **Role**: `backend_developer`
        """

        metadata = mcp_adapter._parse_template_metadata(template)

        # Should pick the first matching supervisor section
        assert metadata["supervisor_role"] == "architect"

    def test_parse_template_metadata_role_without_backticks(self, mcp_adapter):
        """Test parsing role without backtick formatting."""
        template = """
        ### Technical Lead
        **Role**: architect
        """

        metadata = mcp_adapter._parse_template_metadata(template)

        # Should use default when backticks missing
        assert metadata["supervisor_role"] == "general"

    def test_parse_template_metadata_large_team(self, mcp_adapter):
        """Test parsing with large team size."""
        template = """
        Team Size: 15 instances
        """

        metadata = mcp_adapter._parse_template_metadata(template)

        assert metadata["team_size"] == 15
        assert metadata["estimated_cost"] == "$75"  # 15 * $5

    def test_parse_template_metadata_team_size_edge_cases(self, mcp_adapter):
        """Test edge cases in team size parsing."""
        # Test with extra text
        template1 = "Team Size: 8 instances for large projects"
        metadata1 = mcp_adapter._parse_template_metadata(template1)
        assert metadata1["team_size"] == 8

        # Test with no number
        template2 = "Team Size: many instances"
        metadata2 = mcp_adapter._parse_template_metadata(template2)
        assert metadata2["team_size"] == 6  # default

    def test_parse_template_metadata_cost_calculation(self, mcp_adapter):
        """Test cost calculation based on team size."""
        template = "Team Size: 10 instances"
        metadata = mcp_adapter._parse_template_metadata(template)

        assert metadata["estimated_cost"] == "$50"

        template2 = "Team Size: 3 instances"
        metadata2 = mcp_adapter._parse_template_metadata(template2)

        assert metadata2["estimated_cost"] == "$15"
