# Claude CLI Event Parsing Implementation

## Overview

Implemented comprehensive event parsing for Claude CLI stream-json output in `TmuxInstanceManager`. This enables tracking of tool calls and tool results during instance execution.

## Implementation Details

### 1. `_parse_cli_output` Method (Line ~1405)

Parses Claude CLI JSON events from stream-json output format.

**Supported Event Types:**
- `tool_use`: Tool invocation events with name, input parameters, and tool_use_id
- `tool_result`: Tool execution results with content and error status
- `text`: Claude's thinking/response text

**Features:**
- Robust JSON parsing with error handling
- Automatic timestamp injection (ISO 8601 format)
- Structured logging with event context
- Returns `None` for non-JSON or invalid events

### 2. Event Capture in `send_message` Method (Line ~582-654)

Modified the polling loop to parse and capture events in real-time.

**Implementation:**
- Tracks seen lines to avoid duplicate processing
- Parses each line for JSON events during polling
- Captures `tool_call` events with:
  - `role`: "tool_call"
  - `tool`: Tool name (e.g., "Bash", "Read")
  - `tool_use_id`: Unique identifier for correlation
  - `input`: Tool input parameters
  - `timestamp`: ISO 8601 timestamp
- Captures `tool_result` events with:
  - `role`: "tool_result"
  - `tool_use_id`: Correlation ID
  - `content`: Tool output
  - `is_error`: Error status flag
  - `timestamp`: ISO 8601 timestamp

### 3. Stream-JSON Flag (Line ~1072)

Enabled `--stream-json` flag in Claude CLI initialization to emit JSON events.

```python
cmd_parts = [
    "claude",
    "--permission-mode",
    "bypassPermissions",
    "--dangerously-skip-permissions",
    "--stream-json",  # Enable JSON event streaming
]
```

### 4. Event Statistics Method (Line ~1353)

Added `get_event_statistics(instance_id)` method for analyzing captured events.

**Returns:**
- Event counts by type (user, assistant, tool_call, tool_result)
- Tool usage statistics (count per tool)
- Total events count

## Message History Structure

Each instance's `message_history` now contains:

```python
# User message
{"role": "user", "content": "message text", "timestamp": "2025-10-07T00:00:00Z"}

# Tool call
{"role": "tool_call", "tool": "Bash", "tool_use_id": "toolu_xyz", "input": {...}, "timestamp": "..."}

# Tool result
{"role": "tool_result", "tool_use_id": "toolu_xyz", "content": "output", "is_error": False, "timestamp": "..."}

# Assistant response
{"role": "assistant", "content": "response text", "timestamp": "2025-10-07T00:00:00Z"}
```

## Testing

Comprehensive test suite in `tests/test_cli_event_parsing.py`:

- ✅ Parse tool_use events
- ✅ Parse tool_result events
- ✅ Parse text events
- ✅ Handle invalid JSON gracefully
- ✅ Handle non-event JSON
- ✅ Handle empty lines
- ✅ Event statistics calculation
- ✅ Automatic timestamp injection
- ✅ Tool usage tracking

All 9 tests passing.

## Logging

Structured logging with context at all levels:

```python
logger.info(
    f"Captured tool_call event: {tool_name}",
    extra={
        "instance_id": instance_id,
        "tool_name": tool_name,
        "tool_use_id": tool_use_id,
    }
)
```

## Code Quality

- Modern Python 3.12+ syntax (type unions with `|`, built-in generics)
- Proper error handling with specific exceptions
- Comprehensive docstrings
- Passes ruff linting and formatting
- Follows project logging conventions (no `print()` statements)
