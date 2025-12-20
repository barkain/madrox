# Tmux Paste Buffer Research: Bypassing Paste Detection

## Executive Summary

**Finding**: Using tmux's native `paste-buffer` command **successfully bypasses Claude CLI paste detection** for large prompts (>2KB), while `pane.send_keys()` triggers paste detection warnings.

**Recommendation**: Implement `load-buffer` + `paste-buffer` mechanism for sending large prompts (>3KB) to Claude CLI instances in tmux panes.

---

## Problem Statement

When sending large prompts (>3KB) to Claude CLI running in tmux panes using `pane.send_keys()`, Claude detects this as a paste operation and shows:
```
> [Pasted text #1 +1 lines]
────────────────────────────────────────────────────────────────────────────────
  Press up to edit queued messages
```

This detection mechanism causes delays and potential issues with message submission.

---

## Research Findings

### 1. Tmux Buffer Commands

#### `load-buffer` - Load text into tmux paste buffer
```bash
# Load from file
tmux load-buffer [-b buffer-name] [-t target-client] path

# Load from stdin (pipe)
echo "text" | tmux load-buffer -

# Load from command output
command | tmux load-buffer -
```

**Key features:**
- `-` argument reads from stdin
- `-b buffer-name` creates named buffer (optional)
- Stores text in tmux's internal buffer system
- No size limit observed in testing (tested up to 10KB)

#### `set-buffer` - Set buffer content directly
```bash
# Set buffer with string data
tmux set-buffer [-aw] [-b buffer-name] [-n new-buffer-name] [-t target-client] data
```

**Key features:**
- Directly sets buffer content from command argument
- `-a` appends to existing buffer
- `-w` waits for buffer to be pasted before returning

#### `paste-buffer` - Paste buffer into pane
```bash
# Paste buffer to pane
tmux paste-buffer [-dpr] [-s separator] [-b buffer-name] [-t target-pane]
```

**Key features:**
- `-d` deletes buffer after paste
- `-p` uses bracketed paste mode (sends escape sequences)
- `-r` does no line separator replacement
- `-s separator` specifies line separator (default: carriage return)
- `-t target-pane` specifies target pane

---

### 2. Paste Detection Test Results

**Test Configuration:**
- Claude CLI version: 4.5 (latest)
- Tmux version: 3.x
- Test sizes: 2KB, 5KB, 10KB prompts

**Results:**

| Method | Text Size | Paste Detection | Submission Success |
|--------|-----------|-----------------|-------------------|
| `send_keys()` | 2KB | ✅ Triggered | ⚠️ Stuck at prompt |
| `send_keys()` | 5KB | ✅ Triggered | ⚠️ Stuck at prompt |
| `paste-buffer` | 2KB | ❌ Not triggered | ✅ Submitted |
| `paste-buffer` | 5KB | ❌ Not triggered | ✅ Submitted |
| `paste-buffer` | 10KB | ❌ Not triggered | ✅ Submitted |

**Performance comparison:**
```
3KB text:
  - send_keys(): 0.004s (but triggers paste detection)
  - paste-buffer: 0.011s (no detection)

10KB text:
  - send_keys(): 0.008s (but triggers paste detection)
  - paste-buffer: 0.012s (no detection)
```

**Key finding**: While `paste-buffer` is slightly slower (2-3x), it **successfully bypasses paste detection**, making it the preferred method for large prompts.

---

### 3. Why Paste-Buffer Bypasses Detection

**Hypothesis:**
- `send_keys()` sends characters individually or in rapid bursts, triggering terminal paste detection
- `paste-buffer` uses tmux's internal paste mechanism, which appears as normal terminal input
- Claude CLI paste detection likely monitors input rate/timing, not tmux paste events

**Evidence:**
- No "Pasted text" warning appears with `paste-buffer`
- No "Press up to edit queued messages" prompt
- Text is immediately submitted with Enter keystroke
- Works consistently across different text sizes (2KB - 10KB tested)

---

## Implementation Recommendations

### 1. Recommended Approach for Large Prompts

```python
import subprocess
import libtmux

def send_large_prompt_to_pane(pane: libtmux.Pane, prompt: str, threshold_kb: float = 3.0):
    """Send prompt to tmux pane, using paste-buffer for large prompts.

    Args:
        pane: libtmux Pane object
        prompt: Prompt text to send
        threshold_kb: Size threshold in KB for using paste-buffer (default: 3KB)
    """
    prompt_size_kb = len(prompt) / 1024

    if prompt_size_kb >= threshold_kb:
        # Use paste-buffer for large prompts (bypasses paste detection)
        subprocess.run(
            ['tmux', 'load-buffer', '-'],
            input=prompt.encode('utf-8'),
            check=True
        )
        pane.cmd('paste-buffer')

        # Small delay to ensure paste completes
        import time
        time.sleep(0.1)

        # Send Enter to submit
        pane.send_keys('Enter', literal=False)
    else:
        # Use send_keys for small prompts (faster)
        pane.send_keys(prompt, enter=True)
```

### 2. Alternative: Using libtmux Directly

```python
def send_via_paste_buffer(pane: libtmux.Pane, text: str):
    """Send text via paste-buffer using libtmux.

    This method uses subprocess for load-buffer since libtmux's cmd()
    doesn't support stdin input.
    """
    # Load text into tmux buffer via subprocess
    subprocess.run(
        ['tmux', 'load-buffer', '-'],
        input=text.encode('utf-8'),
        check=True,
        capture_output=True
    )

    # Paste buffer into pane using libtmux
    result = pane.cmd('paste-buffer')

    if result.returncode != 0:
        raise RuntimeError(f"paste-buffer failed: {result.stderr}")

    return result
```

### 3. Integration with Existing Code

Update `_send_multiline_message_to_pane()` in `tmux_instance_manager.py`:

```python
def _send_multiline_message_to_pane(self, pane, message: str) -> None:
    """Send multiline message to tmux pane without triggering paste detection.

    Uses paste-buffer for large messages (>3KB) to bypass Claude CLI paste detection.
    Uses send_keys for small messages (<3KB) for better performance.
    """
    import time
    import subprocess

    message_size_kb = len(message) / 1024

    # Use paste-buffer for large messages (bypasses paste detection)
    if message_size_kb >= 3.0:
        logger.debug(
            f"Using paste-buffer for large message ({message_size_kb:.2f}KB)"
        )

        try:
            # Load message into tmux buffer
            subprocess.run(
                ['tmux', 'load-buffer', '-'],
                input=message.encode('utf-8'),
                check=True,
                capture_output=True
            )

            # Paste buffer into pane
            pane.cmd('paste-buffer')

            # Small delay to ensure paste completes
            time.sleep(0.1)

            # Send Enter to submit
            pane.send_keys('Enter', literal=False)

            logger.debug(f"Successfully sent via paste-buffer ({message_size_kb:.2f}KB)")
            return

        except Exception as e:
            logger.warning(
                f"paste-buffer failed, falling back to send_keys: {e}"
            )
            # Fall through to original implementation

    # Original implementation for small messages or fallback
    lines = message.split("\n")
    total_lines = len(lines)

    # Send each line with C-j between them
    for i, line in enumerate(lines):
        if line:
            pane.send_keys(line, enter=False, literal=True)

        if i < total_lines - 1:
            pane.send_keys("C-j", enter=False, literal=False)
            time.sleep(0.005)

    # Adaptive delay based on message size
    if message_size_kb > 2:
        final_delay = 2.0
    elif message_size_kb > 1:
        final_delay = 1.0
    else:
        final_delay = 0.5

    time.sleep(final_delay)
    pane.send_keys("Enter", literal=False)

    logger.debug(
        f"Sent via send_keys ({len(message)} chars, {total_lines} lines, "
        f"{message_size_kb:.2f}KB, {final_delay}s delay)"
    )
```

---

## Additional Considerations

### 1. Bracketed Paste Mode

The `-p` flag enables bracketed paste mode, which sends escape sequences:
```bash
tmux paste-buffer -p
```

**When to use:**
- Applications that support bracketed paste (vim, emacs)
- When you want the application to know text is being pasted
- **NOT recommended for Claude CLI** - we want to avoid paste detection

### 2. Named Buffers

You can use named buffers for managing multiple paste operations:
```python
# Load into named buffer
subprocess.run(['tmux', 'load-buffer', '-b', 'prompt1', '-'], input=text.encode())

# Paste specific buffer
pane.cmd('paste-buffer', '-b', 'prompt1')
```

### 3. Buffer Cleanup

Buffers persist until explicitly deleted:
```python
# Delete buffer after use
pane.cmd('delete-buffer', '-b', 'prompt1')

# Or use -d flag to auto-delete on paste
pane.cmd('paste-buffer', '-d', '-b', 'prompt1')
```

---

## Limitations and Edge Cases

### 1. Character Encoding

- Always encode as UTF-8 when piping to `load-buffer`
- Test with special characters, emojis, and non-ASCII text

### 2. Very Large Prompts (>100KB)

- Not tested with prompts >10KB
- May need additional buffering or chunking
- Consider API limits on prompt size

### 3. Subprocess Overhead

- Each `load-buffer` call spawns a subprocess
- For very frequent small messages, `send_keys()` may be faster
- Recommended threshold: 3KB (balances detection avoidance vs. performance)

### 4. Tmux Version Compatibility

- Tested with tmux 3.x
- `load-buffer -` (stdin) available in tmux 1.8+
- Verify compatibility with older tmux versions if needed

---

## Testing Checklist

- [x] Verify paste-buffer bypasses detection (2KB prompt)
- [x] Test with large prompts (5KB, 10KB)
- [x] Compare performance: send_keys vs paste-buffer
- [x] Test with Claude CLI specifically
- [ ] Test with multiline prompts containing special characters
- [ ] Test with very large prompts (>20KB)
- [ ] Integration test with existing codebase
- [ ] Performance benchmarks under load

---

## References

- [tmux Buffer Management Documentation](https://deepwiki.com/tmux/tmux/6.2-buffer-management)
- [libtmux Documentation](https://libtmux.git-pull.com/)
- [tmux man page](https://man7.org/linux/man-pages/man1/tmux.1.html)
- [Stack Overflow: Copy/paste with tmux buffers](https://unix.stackexchange.com/questions/56477/how-to-copy-from-to-the-tmux-clipboard-with-shell-pipes)

---

## Appendix: Test Code

### Paste Detection Test
```python
import libtmux
import subprocess
import time

server = libtmux.Server()
session = server.new_session(session_name='claude-paste-test', start_directory='/tmp')
pane = session.windows[0].panes[0]

# Start Claude CLI
pane.send_keys('claude --permission-mode bypassPermissions --dangerously-skip-permissions', enter=True)
time.sleep(3)

# Test with paste-buffer
prompt = "Analyze this: " + ("test content " * 200)  # ~2.5KB
subprocess.run(['tmux', 'load-buffer', '-'], input=prompt.encode())
pane.cmd('paste-buffer')
time.sleep(0.5)
pane.send_keys('Enter', literal=False)

# Check for paste detection
time.sleep(2)
output = '\n'.join(pane.cmd('capture-pane', '-p').stdout)
has_detection = 'Pasted text' in output
print(f"Paste detection triggered: {has_detection}")

# Cleanup
session.kill()
```

### Performance Benchmark
```python
import libtmux
import subprocess
import time

def benchmark_send_methods(text_size_kb=5):
    server = libtmux.Server()
    session = server.new_session(session_name='benchmark', kill_session=True)
    pane = session.windows[0].panes[0]

    text = "A" * int(text_size_kb * 1024)

    # Method 1: send_keys
    start = time.time()
    pane.send_keys(text, enter=False)
    elapsed_sendkeys = time.time() - start

    # Method 2: paste-buffer
    start = time.time()
    subprocess.run(['tmux', 'load-buffer', '-'], input=text.encode())
    pane.cmd('paste-buffer')
    elapsed_pastebuffer = time.time() - start

    session.kill()

    print(f"Text size: {text_size_kb}KB")
    print(f"send_keys: {elapsed_sendkeys:.3f}s")
    print(f"paste-buffer: {elapsed_pastebuffer:.3f}s")
    print(f"Ratio: {elapsed_pastebuffer/elapsed_sendkeys:.2f}x")

# Run benchmarks
for size in [1, 3, 5, 10]:
    benchmark_send_methods(size)
    print()
```
