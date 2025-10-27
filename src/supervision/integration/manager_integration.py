"""Integration layer for Supervisor Agent with Madrox InstanceManager.

This module provides functions to spawn and attach supervisor agents to
Madrox instance managers, enabling autonomous network monitoring.
"""

import logging
from typing import Any

from supervision.supervisor.agent import SupervisionConfig, SupervisorAgent
from supervision.supervisor.system_prompt import get_supervisor_prompt

logger = logging.getLogger(__name__)


async def spawn_supervisor(
    instance_manager: Any,
    config: SupervisionConfig | None = None,
    auto_start: bool = True,
) -> tuple[str, SupervisorAgent]:
    """Spawn a supervisor instance to monitor a Madrox network.

    This function creates a new Claude instance with the supervisor system prompt
    and initializes a SupervisorAgent to monitor all other instances in the network.

    Args:
        instance_manager: The InstanceManager to monitor
        config: Supervision configuration (uses defaults if None)
        auto_start: Automatically start the supervision loop

    Returns:
        Tuple of (supervisor_instance_id, supervisor_agent)

    Example:
        ```python
        from supervision.integration import spawn_supervisor

        # Spawn supervisor for a network
        supervisor_id, supervisor = await spawn_supervisor(
            instance_manager=manager,
            config=SupervisionConfig(
                stuck_threshold_seconds=300,
                evaluation_interval_seconds=30
            )
        )
        ```
    """
    if config is None:
        config = SupervisionConfig()

    # Generate supervisor system prompt
    system_prompt = get_supervisor_prompt(config)

    logger.info("Spawning supervisor instance for autonomous network monitoring")

    # Spawn supervisor as Claude instance with special prompt
    supervisor_id = await instance_manager.spawn_instance(
        name="network-supervisor",
        role="general",  # Use general role with custom system prompt
        system_prompt=system_prompt,
        bypass_isolation=False,
        wait_for_ready=True,
    )

    logger.info(
        "Supervisor instance spawned",
        extra={
            "supervisor_id": supervisor_id,
            "stuck_threshold": config.stuck_threshold_seconds,
            "evaluation_interval": config.evaluation_interval_seconds,
        },
    )

    # Create SupervisorAgent to manage the supervisor instance
    supervisor_agent = SupervisorAgent(
        instance_manager=instance_manager,
        config=config,
    )

    # Start supervision loop if requested
    if auto_start:
        await supervisor_agent.start()
        logger.info("Supervisor agent started - autonomous monitoring active")

    return supervisor_id, supervisor_agent


async def attach_supervisor(
    instance_manager: Any,
    config: SupervisionConfig | None = None,
) -> SupervisorAgent:
    """Attach a supervisor agent to an existing InstanceManager without spawning.

    This creates a SupervisorAgent that monitors the network without spawning
    a dedicated Claude instance. Useful for embedding supervision in existing
    infrastructure.

    Args:
        instance_manager: The InstanceManager to monitor
        config: Supervision configuration (uses defaults if None)

    Returns:
        Initialized SupervisorAgent (not started)

    Example:
        ```python
        from supervision.integration import attach_supervisor

        # Attach supervisor to existing manager
        supervisor = await attach_supervisor(
            instance_manager=manager,
            config=SupervisionConfig(evaluation_interval_seconds=60)
        )

        # Start supervision manually
        await supervisor.start()

        # Later, stop supervision
        await supervisor.stop()
        ```
    """
    if config is None:
        config = SupervisionConfig()

    logger.info("Attaching supervisor agent to instance manager")

    supervisor_agent = SupervisorAgent(
        instance_manager=instance_manager,
        config=config,
    )

    logger.info(
        "Supervisor agent attached (not started)",
        extra={
            "stuck_threshold": config.stuck_threshold_seconds,
            "evaluation_interval": config.evaluation_interval_seconds,
        },
    )

    return supervisor_agent


async def spawn_supervised_network(
    instance_manager: Any,
    participant_configs: list[dict[str, Any]],
    supervision_config: SupervisionConfig | None = None,
) -> dict[str, Any]:
    """Spawn a complete supervised network with participants and supervisor.

    This is a convenience function that spawns multiple participant instances
    and a supervisor to monitor them all.

    Args:
        instance_manager: The InstanceManager
        participant_configs: List of participant instance configurations
        supervision_config: Supervision configuration (uses defaults if None)

    Returns:
        Dictionary with supervisor_id, supervisor_agent, and participant_ids

    Example:
        ```python
        from supervision.integration import spawn_supervised_network

        # Spawn a supervised team
        network = await spawn_supervised_network(
            instance_manager=manager,
            participant_configs=[
                {"name": "frontend-dev", "role": "frontend_developer"},
                {"name": "backend-dev", "role": "backend_developer"},
                {"name": "tester", "role": "testing_specialist"},
            ],
            supervision_config=SupervisionConfig()
        )

        # Access components
        supervisor_id = network["supervisor_id"]
        participant_ids = network["participant_ids"]
        supervisor = network["supervisor_agent"]
        ```
    """
    logger.info(
        "Spawning supervised network", extra={"participant_count": len(participant_configs)}
    )

    # Spawn all participant instances
    participant_ids = []
    for config in participant_configs:
        instance_id = await instance_manager.spawn_instance(**config)
        participant_ids.append(instance_id)
        logger.info(
            "Spawned participant",
            extra={"instance_id": instance_id, "participant_name": config.get("name")},
        )

    # Spawn supervisor
    supervisor_id, supervisor_agent = await spawn_supervisor(
        instance_manager=instance_manager,
        config=supervision_config,
        auto_start=True,
    )

    logger.info(
        "Supervised network spawned successfully",
        extra={
            "supervisor_id": supervisor_id,
            "participant_count": len(participant_ids),
        },
    )

    return {
        "supervisor_id": supervisor_id,
        "supervisor_agent": supervisor_agent,
        "participant_ids": participant_ids,
        "network_size": len(participant_ids) + 1,  # +1 for supervisor
    }
