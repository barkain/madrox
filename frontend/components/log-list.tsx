"use client"

import { useEffect, useRef, useMemo } from "react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { LogEntry } from "@/components/log-entry"
import type { SystemLog, AuditLog, LogFilters } from "@/types"

interface SystemLogListProps {
  logs: SystemLog[]
  filters: LogFilters
  autoScroll: boolean
  type: "system"
}

interface AuditLogListProps {
  logs: AuditLog[]
  filters: LogFilters
  autoScroll: boolean
  type: "audit"
}

type LogListProps = SystemLogListProps | AuditLogListProps

function filterLogs<T extends SystemLog | AuditLog>(logs: T[], filters: LogFilters): T[] {
  return logs.filter((log) => {
    // Filter by level
    if (!filters.levels.has(log.level)) {
      return false
    }

    // Filter by search
    if (filters.search) {
      const searchLower = filters.search.toLowerCase()
      const matchesMessage = log.message.toLowerCase().includes(searchLower)
      const matchesLogger = log.logger.toLowerCase().includes(searchLower)

      // For system logs, also search module and function
      if ("module" in log) {
        const systemLog = log as SystemLog
        const matchesModule = systemLog.module.toLowerCase().includes(searchLower)
        const matchesFunction = systemLog.function.toLowerCase().includes(searchLower)
        return matchesMessage || matchesLogger || matchesModule || matchesFunction
      }

      // For audit logs, also search action
      if ("action" in log) {
        const auditLog = log as AuditLog
        const matchesAction = auditLog.action ? auditLog.action.toLowerCase().includes(searchLower) : false
        return matchesMessage || matchesLogger || matchesAction
      }

      return matchesMessage || matchesLogger
    }

    // Filter by modules (if any are selected)
    if (filters.modules.size > 0) {
      if ("module" in log) {
        return filters.modules.has((log as SystemLog).module)
      }
    }

    return true
  })
}

export function LogList({ logs, filters, autoScroll, type }: LogListProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const prevLogsLengthRef = useRef(0)

  // Filter logs with proper typing
  const filteredLogs = useMemo(() => {
    if (type === "system") {
      return filterLogs(logs as SystemLog[], filters)
    } else {
      return filterLogs(logs as AuditLog[], filters)
    }
  }, [logs, filters, type])

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current && logs.length > prevLogsLengthRef.current) {
      const scrollContainer = scrollRef.current.querySelector("[data-radix-scroll-area-viewport]")
      if (scrollContainer) {
        scrollContainer.scrollTop = 0 // Scroll to top since logs are prepended
      }
    }
    prevLogsLengthRef.current = logs.length
  }, [logs.length, autoScroll])

  return (
    <ScrollArea className="flex-1" ref={scrollRef}>
      <div className="px-2 py-1">
        {filteredLogs.length === 0 ? (
          <div className="text-center py-8 text-sm text-muted-foreground">
            {logs.length === 0 ? "No logs yet" : "No logs match the current filters"}
          </div>
        ) : type === "system" ? (
          (filteredLogs as SystemLog[]).map((log) => (
            <LogEntry key={log.id} log={log} type="system" />
          ))
        ) : (
          (filteredLogs as AuditLog[]).map((log) => (
            <LogEntry key={log.id} log={log} type="audit" />
          ))
        )}
      </div>
    </ScrollArea>
  )
}
