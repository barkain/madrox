# Dual-Panel Logging System

## Overview

A real-time, dual-panel logging interface for monitoring system and audit logs separately with advanced filtering, search, and export capabilities.

## Architecture

### Component Structure

```
<DualPanelLogs>                    # Main container with WebSocket connection
  ├─ ConnectionStatus               # WebSocket status indicator
  └─ PanelGroup                     # Resizable panels container
      ├─ Panel (System)             # Left panel
      │   └─ <LogPanel type="system">
      │       ├─ LogPanelHeader      # Controls (pause/clear/export)
      │       ├─ LogFilters          # Level toggles + search
      │       └─ LogList             # Virtualized log entries
      │           └─ LogEntry[]      # Individual log items
      ├─ PanelResizeHandle           # Draggable divider
      └─ Panel (Audit)               # Right panel
          └─ <LogPanel type="audit">
              ├─ LogPanelHeader
              ├─ LogFilters
              └─ LogList
                  └─ LogEntry[]
```

### State Management (Zustand)

**Store**: `/store/log-store.ts`

Separate state for system and audit logs:
- Logs array (max 1000 entries)
- Filters (levels, search, modules)
- Auto-scroll toggle
- Pause/resume toggle

### WebSocket Integration

**Hook**: `/hooks/use-log-websocket.ts`

- Connects to: `ws://localhost:8001/ws/logs`
- Auto-reconnects on disconnect (3s delay)
- Handles two message types:
  - `system_log`: System logging events
  - `audit_log`: Audit trail events

### TypeScript Types

**File**: `/types/index.ts`

```typescript
// System log
{
  id: string
  timestamp: string      // ISO 8601
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"
  logger: string
  message: string
  module: string
  function: string
  line: number
}

// Audit log
{
  id: string
  timestamp: string
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"
  logger: string
  message: string
  action?: string
  metadata?: Record<string, any>
}
```

## Features

### 1. Real-time Streaming
- WebSocket connection for live log updates
- Connection status indicator (connected/connecting/disconnected/error)
- Auto-reconnection on disconnect

### 2. Dual Independent Panels
- Side-by-side system and audit logs
- Resizable panels with draggable divider
- Independent filters and controls for each panel

### 3. Filtering
- **Level Filtering**: Toggle DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Search**: Full-text search across all log fields
- **Visual Feedback**: Color-coded level badges

### 4. Controls (per panel)
- **Pause/Resume**: Freeze log updates while debugging
- **Clear**: Remove all logs from panel
- **Export**: Download logs as JSON file

### 5. Performance
- Efficient rendering with React.memo
- Scroll virtualization ready (using ScrollArea)
- Max 1000 logs kept in memory per panel

### 6. Accessibility
- Semantic HTML
- Keyboard-navigable controls
- Clear visual indicators for all states

## Files Created

### Components
- `/components/dual-panel-logs.tsx` - Main container component
- `/components/log-panel.tsx` - Individual panel with controls
- `/components/log-filters.tsx` - Filter controls (levels + search)
- `/components/log-list.tsx` - Scrollable log list with filtering
- `/components/log-entry.tsx` - Single log entry renderer

### State & Hooks
- `/store/log-store.ts` - Zustand store for log state
- `/hooks/use-log-websocket.ts` - WebSocket connection hook

### Types
- `/types/index.ts` - TypeScript definitions (updated)

### Pages
- `/app/logs/page.tsx` - Demo page at `/logs` route

## Usage

### 1. Development Server

```bash
cd /Users/nadavbarkai/dev/madrox/frontend
npm run dev
```

Navigate to: `http://localhost:3000/logs`

### 2. Backend Requirements

The frontend expects a WebSocket server at `ws://localhost:8001/ws/logs` that sends messages in this format:

```typescript
// System log message
{
  type: "system_log",
  data: {
    timestamp: "2025-10-08T21:30:45.123Z",
    level: "INFO",
    logger: "orchestrator",
    message: "Instance started successfully",
    module: "core.instance",
    function: "start_instance",
    line: 142
  }
}

// Audit log message
{
  type: "audit_log",
  data: {
    timestamp: "2025-10-08T21:30:45.123Z",
    level: "INFO",
    logger: "audit",
    message: "User logged in",
    action: "user.login",
    metadata: {
      user_id: "123",
      ip: "192.168.1.1"
    }
  }
}
```

### 3. Integrate into Existing App

```tsx
import { DualPanelLogs } from "@/components/dual-panel-logs"

export default function YourPage() {
  return (
    <div className="h-screen">
      <DualPanelLogs />
    </div>
  )
}
```

## Customization

### Change WebSocket URL

Edit `/hooks/use-log-websocket.ts`:

```typescript
const WS_URL = "ws://your-server:port/ws/logs"
```

### Adjust Max Logs

Edit `/store/log-store.ts`:

```typescript
const MAX_LOGS = 1000 // Change this value
```

### Modify Colors

Colors are defined using Tailwind CSS classes. Key areas:
- Level badges: `/components/log-entry.tsx` - `getLevelBadge()`
- Filter buttons: `/components/log-filters.tsx` - `getLevelColor()`

### Add Module Filtering

The store already supports module filtering. To enable:

1. Track available modules in the store
2. Add module selector to LogFilters component
3. Update LogList filtering logic (already supports it)

## Testing

### Manual Testing

1. **Connection Status**
   - Start frontend → should show "Connecting..."
   - Start backend → should show "Connected" (green)
   - Stop backend → should show "Disconnected" and auto-reconnect

2. **Log Streaming**
   - Generate logs from backend
   - Verify logs appear in correct panel (system vs audit)
   - Verify newest logs appear at top

3. **Filtering**
   - Click level badges → should hide/show logs
   - Type in search → should filter in real-time
   - Try all 5 levels

4. **Controls**
   - Pause → logs should stop updating
   - Resume → logs should update again
   - Clear → all logs should disappear
   - Export → should download JSON file

5. **Panel Resizing**
   - Drag divider → panels should resize
   - Should respect min-width (30%)

## Performance Considerations

- Logs limited to 1000 entries per panel (prevents memory bloat)
- Using React.memo for LogEntry to prevent unnecessary re-renders
- ScrollArea component from Radix UI handles large lists efficiently
- Consider adding react-window/react-virtuoso for >1000 logs

## Browser Support

Tested on:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Known Limitations

1. No log persistence (cleared on refresh)
2. No time range filtering (yet)
3. No log level statistics (yet)
4. No log export to CSV (only JSON)

## Future Enhancements

- [ ] Add timestamp range filtering
- [ ] Add module/logger filtering UI
- [ ] Add log statistics dashboard
- [ ] Add CSV export option
- [ ] Add log highlighting/bookmarking
- [ ] Add log tail mode (follow new logs)
- [ ] Add keyboard shortcuts
- [ ] Add dark/light theme toggle
- [ ] Add log detail modal on click
- [ ] Add full virtualization for 10K+ logs

## Dependencies

Already in package.json:
- `zustand` - State management
- `react-resizable-panels` - Panel resizing
- `@radix-ui/react-scroll-area` - Scroll area
- `lucide-react` - Icons
- `tailwindcss` - Styling

## Support

For issues or questions, refer to the main Madrox documentation or open an issue in the repository.
