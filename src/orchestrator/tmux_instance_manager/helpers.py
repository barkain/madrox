"""Shared helpers and constants for TmuxInstanceManager."""

# SECURITY FIX (CWE-770): Message history limits to prevent unbounded memory growth
MAX_MESSAGE_HISTORY_PER_INSTANCE = 500  # Keep last 500 messages per instance


# SECURITY FIX (CWE-532): Helper function to redact authkeys in logs
def redact_authkey(authkey: bytes | None) -> str:
    """Redact authentication keys for logging.

    Args:
        authkey: Authentication key bytes to redact

    Returns:
        Redacted string like "***1234" showing last 4 bytes in hex
    """
    if not authkey:
        return "[not set]"
    # Show last 4 bytes as hex
    last_bytes = authkey[-4:] if len(authkey) >= 4 else authkey
    return f"***{last_bytes.hex()}"
