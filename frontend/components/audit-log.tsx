import { ScrollArea } from "@/components/ui/scroll-area"
import { Clock } from "lucide-react"
import type { AuditLogEntry } from "@/types"

interface AuditLogProps {
  logs: AuditLogEntry[]
}

export function AuditLog({ logs }: AuditLogProps) {
  const getEventColor = (type: string) => {
    switch (type) {
      case "instance_created":
      case "instance_started":
        return "text-[var(--status-running)]"
      case "instance_terminated":
        return "text-[var(--status-terminated)]"
      case "instance_error":
        return "text-[var(--status-error)]"
      default:
        return "text-muted-foreground"
    }
  }

  return (
    <div className="border-t border-border bg-card/50 h-48">
      <div className="px-6 py-3 border-b border-border">
        <h2 className="text-sm font-semibold text-foreground">Audit Log</h2>
      </div>

      <ScrollArea className="h-[calc(100%-3rem)]">
        <div className="px-6 py-2 space-y-1">
          {logs.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">No activity yet</p>
          ) : (
            logs.map((log) => (
              <div key={log.id} className="flex items-start gap-3 py-2 text-sm hover:bg-muted/50 rounded px-2 -mx-2">
                <Clock className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                <span className="font-mono text-xs text-muted-foreground min-w-[80px]">{log.timestamp}</span>
                <span className={`font-medium ${getEventColor(log.type)}`}>{log.type.replace(/_/g, " ")}</span>
                <span className="text-muted-foreground flex-1">{log.message}</span>
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
