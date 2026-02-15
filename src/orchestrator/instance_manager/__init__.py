"""Instance Manager package — manages Claude instance lifecycle with MCP tools."""

from ._mcp import mcp
from .core import InstanceManager

__all__ = ["InstanceManager", "mcp"]
