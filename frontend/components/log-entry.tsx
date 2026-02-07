import { memo } from "react"
import type { SystemLog, AuditLog } from "@/types"
import { cn } from "@/lib/utils"

interface ColumnWidths {
  timestamp: number
  level: number
  logger: number
  module: number
  functionLine: number
  action: number
  message: number
}

interface SystemLogEntryProps {
  log: SystemLog
  type: "system"
  columnWidths: ColumnWidths
}

interface AuditLogEntryProps {
  log: AuditLog
  type: "audit"
  columnWidths: ColumnWidths
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
      return "bg-slate-500/20 text-slate-300 border border-slate-500/30"
    case "INFO":
      return "bg-blue-500/20 text-blue-300 border border-blue-500/30"
    case "WARNING":
      return "bg-amber-500/20 text-amber-300 border border-amber-500/30"
    case "ERROR":
      return "bg-rose-500/20 text-rose-300 border border-rose-500/30"
    case "CRITICAL":
      return "bg-rose-600/30 text-rose-200 border border-rose-500/40 font-bold shadow-[0_0_8px_rgba(244,63,94,0.3)]"
    default:
      return "bg-slate-500/20 text-slate-300 border border-slate-500/30"
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

export const LogEntry = memo(({ log, type, columnWidths }: LogEntryProps) => {
  return (
    <div className="flex items-start gap-2 py-2 px-3 text-xs hover:bg-white/5 rounded-lg font-mono border-b border-white/5 last:border-0 min-w-max transition-all duration-200 group">
      {/* Timestamp */}
      <span className="text-slate-500 group-hover:text-slate-400 flex-shrink-0 overflow-hidden transition-colors duration-200" style={{ width: `${columnWidths.timestamp}px` }}>
        {formatTimestamp(log.timestamp)}
      </span>

      {/* Level Badge */}
      <span
        className={cn(
          "text-center px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase flex-shrink-0 overflow-hidden transition-all duration-200",
          getLevelBadge(log.level),
        )}
        style={{ width: `${columnWidths.level}px` }}
      >
        {log.level}
      </span>

      {/* Logger/Module */}
      <span className="text-purple-400 group-hover:text-purple-300 flex-shrink-0 whitespace-nowrap overflow-hidden transition-colors duration-200" style={{ width: `${columnWidths.logger}px` }}>
        {log.logger}
      </span>

      {/* System-specific fields */}
      {type === "system" && (
        <>
          <span className="text-cyan-400 group-hover:text-cyan-300 flex-shrink-0 whitespace-nowrap overflow-hidden transition-colors duration-200" style={{ width: `${columnWidths.module}px` }}>
            {(log as SystemLog).module}
          </span>
          <span className="text-slate-500 group-hover:text-slate-400 flex-shrink-0 whitespace-nowrap overflow-hidden transition-colors duration-200" style={{ width: `${columnWidths.functionLine}px` }}>
            {(log as SystemLog).function}:{(log as SystemLog).line}
          </span>
        </>
      )}

      {/* Audit-specific fields */}
      {type === "audit" && (log as AuditLog).action && (
        <span className="text-emerald-400 group-hover:text-emerald-300 flex-shrink-0 whitespace-nowrap overflow-hidden transition-colors duration-200" style={{ width: `${columnWidths.action}px` }}>
          {(log as AuditLog).action}
        </span>
      )}

      {/* Message */}
      <span className="text-slate-200 group-hover:text-white flex-shrink-0 whitespace-nowrap overflow-hidden transition-colors duration-200" style={{ width: `${columnWidths.message}px` }}>{log.message}</span>

      {/* Metadata (audit logs only) */}
      {type === "audit" && (log as AuditLog).metadata && (
        <span className="text-xs text-slate-500 group-hover:text-slate-400 flex-shrink-0 whitespace-nowrap min-w-[100px] transition-colors duration-200">
          {JSON.stringify((log as AuditLog).metadata, null, 0)}
        </span>
      )}
    </div>
  )
})

LogEntry.displayName = "LogEntry"
