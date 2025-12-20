import { ScrollArea } from "@/components/ui/scroll-area"
import { Clock, ChevronDown, ChevronUp } from "lucide-react"
import type { AuditLogEntry } from "@/types"

interface AuditLogProps {
  logs: AuditLogEntry[]
  height: number
  isCollapsed: boolean
  onToggle: () => void
}

export function AuditLog({ logs, height, isCollapsed, onToggle }: AuditLogProps) {
  const getEventColor = (type: string) => {
    switch (type) {
      case "instance_created":
      case "instance_started":
      case "instance_spawn":
        return "text-[var(--status-running)]"
      case "instance_terminated":
      case "instance_terminate":
        return "text-[var(--status-terminated)]"
      case "instance_error":
      case "error":
      case "timeout":
        return "text-[var(--status-error)]"
      case "message_sent":
      case "message_exchange":
        return "text-blue-500"
      case "message_received":
        return "text-green-500"
      case "state_change":
        return "text-yellow-500"
      case "instance_updated":
        return "text-purple-500"
      default:
        return "text-muted-foreground"
    }
  }

  if (isCollapsed) {
    return (
      <div className="border-t border-border bg-card/50">
        <div className="px-4 py-1.5 flex items-center justify-between cursor-pointer hover:bg-muted/30 transition-colors" onClick={onToggle}>
          <h2 className="text-xs font-semibold text-foreground">Audit Log</h2>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{logs.length} events</span>
            <button
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              title="Expand audit log"
            >
              <ChevronUp className="h-3 w-3" />
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="border-t border-border bg-card/50" style={{ height: `${height}px` }}>
      <div className="px-4 py-1.5 border-b border-border flex items-center justify-between">
        <h2 className="text-xs font-semibold text-foreground">Audit Log</h2>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{logs.length} events</span>
          <button
            onClick={onToggle}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            title="Collapse audit log"
          >
            <ChevronDown className="h-3 w-3" />
          </button>
        </div>
      </div>

      <ScrollArea className="h-[calc(100%-2rem)]">
        <div className="px-4 py-1 space-y-0.5 min-w-max">
          {logs.length === 0 ? (
            <p className="text-xs text-muted-foreground py-3">No activity yet</p>
          ) : (
            logs.map((log) => (
              <div key={log.id} className="flex items-center gap-2 py-1 text-xs hover:bg-muted/50 rounded px-1.5 -mx-1.5 min-w-max">
                <Clock className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                <span className="font-mono text-muted-foreground min-w-[70px] flex-shrink-0">{log.timestamp}</span>
                <span className={`font-medium whitespace-nowrap flex-shrink-0 ${getEventColor(log.type)}`}>{log.type.replace(/_/g, " ")}</span>
                <span className="text-muted-foreground whitespace-nowrap">{log.message}</span>
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
