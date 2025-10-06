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
        return "text-[var(--status-error)]"
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
        <div className="px-4 py-1 space-y-0.5">
          {logs.length === 0 ? (
            <p className="text-xs text-muted-foreground py-3">No activity yet</p>
          ) : (
            logs.map((log) => (
              <div key={log.id} className="flex items-center gap-2 py-1 text-xs hover:bg-muted/50 rounded px-1.5 -mx-1.5">
                <Clock className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                <span className="font-mono text-muted-foreground min-w-[70px]">{log.timestamp}</span>
                <span className={`font-medium ${getEventColor(log.type)}`}>{log.type.replace(/_/g, " ")}</span>
                <span className="text-muted-foreground flex-1 truncate">{log.message}</span>
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
