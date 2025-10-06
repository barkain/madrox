"""Example: Spawning Claude instances with MCP server configurations.

This example demonstrates various ways to spawn instances with MCP servers
using the reusable configuration files.
"""

import asyncio

from orchestrator.instance_manager import InstanceManager
from orchestrator.mcp_loader import MCPConfigLoader, get_mcp_servers


async def example_playwright_agent():
    """Spawn an agent with Playwright MCP for browser automation."""
    manager = InstanceManager(config={})

    # Method 1: Using the quick helper
    mcp_servers = get_mcp_servers("playwright")

    instance_id = await manager.spawn_instance(
        name="browser-agent",
        role="general",
        enable_madrox=True,
        mcp_servers=mcp_servers,
    )

    logger.info(f"Spawned browser agent: {instance_id}")

    # Test it
    response = await manager.send_to_instance(
        instance_id=instance_id,
        message="Navigate to https://example.com and tell me the page title",
        wait_for_response=True,
        timeout_seconds=60,
    )

    logger.info(f"Response: {response.get('response')}")

    await manager.terminate_instance(instance_id)


async def example_multiple_mcp_servers():
    """Spawn an agent with multiple MCP servers."""
    manager = InstanceManager(config={})

    # Load multiple MCP configs at once
    mcp_servers = get_mcp_servers("playwright", "github", "memory")

    instance_id = await manager.spawn_instance(
        name="full-stack-agent",
        role="general",
        enable_madrox=True,
        mcp_servers=mcp_servers,
    )

    logger.info(f"Spawned full-stack agent with {len(mcp_servers)} MCP servers: {instance_id}")

    # This agent now has access to browser automation, GitHub, and memory storage
    response = await manager.send_to_instance(
        instance_id=instance_id,
        message="What MCP servers do you have access to?",
        wait_for_response=True,
    )

    logger.info(f"Available tools: {response.get('response')}")

    await manager.terminate_instance(instance_id)


async def example_custom_filesystem_config():
    """Spawn an agent with customized filesystem MCP config."""
    manager = InstanceManager(config={})
    loader = MCPConfigLoader()

    # Load filesystem config with custom path
    filesystem_config = loader.load_with_overrides(
        "filesystem", args_overrides=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    )

    mcp_servers = {filesystem_config["name"]: filesystem_config["config"]}

    instance_id = await manager.spawn_instance(
        name="file-agent",
        role="general",
        enable_madrox=True,
        mcp_servers=mcp_servers,
    )

    logger.info(f"Spawned file agent with /tmp access: {instance_id}")

    response = await manager.send_to_instance(
        instance_id=instance_id,
        message="List the files in the directory you have access to",
        wait_for_response=True,
    )

    logger.info(f"Files: {response.get('response')}")

    await manager.terminate_instance(instance_id)


async def example_mix_configs_and_custom():
    """Mix prebuilt configs with custom MCP servers."""
    manager = InstanceManager(config={})

    # Combine prebuilt configs with custom ones
    mcp_servers = get_mcp_servers(
        "playwright",
        "memory",
        # Add a custom MCP server
        custom_api={"command": "python", "args": ["my_custom_mcp_server.py"]},
    )

    instance_id = await manager.spawn_instance(
        name="hybrid-agent",
        role="general",
        enable_madrox=True,
        mcp_servers=mcp_servers,
    )

    logger.info(f"Spawned hybrid agent: {instance_id}")
    await manager.terminate_instance(instance_id)


async def example_github_with_token():
    """Spawn an agent with GitHub MCP and authentication."""
    manager = InstanceManager(config={})
    loader = MCPConfigLoader()

    # Load GitHub config with token
    github_config = loader.load_with_overrides(
        "github", env_overrides={"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_your_token_here"}
    )

    mcp_servers = {github_config["name"]: github_config["config"]}

    instance_id = await manager.spawn_instance(
        name="github-agent",
        role="general",
        enable_madrox=True,
        mcp_servers=mcp_servers,
        environment_vars=github_config.get("env", {}),
    )

    logger.info(f"Spawned GitHub agent: {instance_id}")

    response = await manager.send_to_instance(
        instance_id=instance_id,
        message="List my GitHub repositories",
        wait_for_response=True,
    )

    logger.info(f"Repositories: {response.get('response')}")

    await manager.terminate_instance(instance_id)


async def example_list_available_configs():
    """List all available MCP configurations."""
    loader = MCPConfigLoader()

    available = loader.list_available_configs()
    logger.info(f"Available MCP configs: {', '.join(available)}")

    # Load and inspect a specific config
    playwright_config = loader.load_config("playwright")
    logger.info(f"Playwright config: {playwright_config}")


async def main():
    """Run all examples."""
    import logging

    logging.basicConfig(level=logging.INFO)
    global logger
    logger = logging.getLogger(__name__)

    logger.info("=== Example 1: List available configs ===")
    await example_list_available_configs()

    logger.info("\n=== Example 2: Playwright agent ===")
    await example_playwright_agent()

    logger.info("\n=== Example 3: Multiple MCP servers ===")
    await example_multiple_mcp_servers()

    logger.info("\n=== Example 4: Custom filesystem config ===")
    await example_custom_filesystem_config()

    logger.info("\n=== Example 5: Mix configs and custom ===")
    await example_mix_configs_and_custom()

    logger.info("\n=== Example 6: GitHub with token ===")
    # Uncomment to run (requires actual GitHub token)
    # await example_github_with_token()


if __name__ == "__main__":
    asyncio.run(main())
