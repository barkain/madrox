import { memo } from "react"
import type { SystemLog, AuditLog } from "@/types"
import { cn } from "@/lib/utils"

interface SystemLogEntryProps {
  log: SystemLog
  type: "system"
}

interface AuditLogEntryProps {
  log: AuditLog
  type: "audit"
}

type LogEntryProps = SystemLogEntryProps | AuditLogEntryProps

const getLevelColor = (level: string) => {
  switch (level) {
    case "DEBUG":
      return "text-gray-500"
    case "INFO":
      return "text-blue-500"
    case "WARNING":
      return "text-yellow-500"
    case "ERROR":
      return "text-red-500"
    case "CRITICAL":
      return "text-red-700 font-bold"
    default:
      return "text-muted-foreground"
  }
}

const getLevelBadge = (level: string) => {
  switch (level) {
    case "DEBUG":
      return "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
    case "INFO":
      return "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
    case "WARNING":
      return "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
    case "ERROR":
      return "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
    case "CRITICAL":
      return "bg-red-200 text-red-900 dark:bg-red-800 dark:text-red-100 font-bold"
    default:
      return "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
  }
}

const formatTimestamp = (timestamp: string) => {
  try {
    const date = new Date(timestamp)
    return date.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      fractionalSecondDigits: 3,
    })
  } catch {
    return timestamp
  }
}

export const LogEntry = memo(({ log, type }: LogEntryProps) => {
  return (
    <div className="flex items-start gap-2 py-1.5 px-2 text-xs hover:bg-muted/30 rounded font-mono border-b border-border/50 last:border-0">
      {/* Timestamp */}
      <span className="text-muted-foreground min-w-[90px] flex-shrink-0">
        {formatTimestamp(log.timestamp)}
      </span>

      {/* Level Badge */}
      <span
        className={cn(
          "min-w-[70px] text-center px-2 py-0.5 rounded text-[10px] font-semibold uppercase flex-shrink-0",
          getLevelBadge(log.level),
        )}
      >
        {log.level}
      </span>

      {/* Logger/Module */}
      <span className="text-purple-600 dark:text-purple-400 min-w-[120px] flex-shrink-0 truncate">
        {log.logger}
      </span>

      {/* System-specific fields */}
      {type === "system" && (
        <>
          <span className="text-cyan-600 dark:text-cyan-400 min-w-[100px] flex-shrink-0 truncate">
            {(log as SystemLog).module}
          </span>
          <span className="text-gray-500 dark:text-gray-400 min-w-[120px] flex-shrink-0 truncate">
            {(log as SystemLog).function}:{(log as SystemLog).line}
          </span>
        </>
      )}

      {/* Audit-specific fields */}
      {type === "audit" && (log as AuditLog).action && (
        <span className="text-green-600 dark:text-green-400 min-w-[100px] flex-shrink-0 truncate">
          {(log as AuditLog).action}
        </span>
      )}

      {/* Message */}
      <span className="text-foreground flex-1 break-words">{log.message}</span>

      {/* Metadata (audit logs only) */}
      {type === "audit" && (log as AuditLog).metadata && (
        <span className="text-xs text-muted-foreground flex-shrink-0">
          {JSON.stringify((log as AuditLog).metadata, null, 0)}
        </span>
      )}
    </div>
  )
})

LogEntry.displayName = "LogEntry"
