"""Integration module for Madrox supervision system."""

from supervision.integration.manager_integration import (
    attach_supervisor,
    spawn_supervised_network,
    spawn_supervisor,
)

__all__ = [
    "spawn_supervisor",
    "attach_supervisor",
    "spawn_supervised_network",
]
