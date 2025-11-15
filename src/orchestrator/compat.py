"""
Compatibility layer for Python 3.10+ support.

This module provides backward-compatible imports for features introduced
in later Python versions, allowing the codebase to work across Python 3.10+.

Key compatibility fixes:
- datetime.UTC: Introduced in Python 3.11 (PEP 615)
  - Python 3.11+: Uses native datetime.UTC
  - Python 3.10: Uses datetime.timezone.utc as fallback
"""

import sys
from datetime import timezone

# UTC constant backport for Python 3.10 compatibility
if sys.version_info >= (3, 11):
    from datetime import UTC
else:
    # Python 3.10: datetime.UTC doesn't exist yet
    # Use timezone.utc as equivalent fallback
    UTC = timezone.utc

__all__ = ["UTC"]
