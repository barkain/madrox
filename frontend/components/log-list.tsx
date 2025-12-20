"use client"

import { useEffect, useRef, useMemo, useState } from "react"
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area"
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
  const [resizingColumn, setResizingColumn] = useState<string | null>(null)

  // Column widths state
  const [columnWidths, setColumnWidths] = useState({
    timestamp: 90,
    level: 70,
    logger: 120,
    module: 100,
    functionLine: 120,
    action: 100,
    message: 200,
  })

  // Filter logs with proper typing
  const filteredLogs = useMemo(() => {
    if (type === "system") {
      return filterLogs(logs as SystemLog[], filters)
    } else {
      return filterLogs(logs as AuditLog[], filters)
    }
  }, [logs, filters, type])

  // Handle column resize
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!resizingColumn) return

      const deltaX = e.movementX
      setColumnWidths(prev => ({
        ...prev,
        [resizingColumn]: Math.max(50, prev[resizingColumn as keyof typeof prev] + deltaX)
      }))
    }

    const handleMouseUp = () => {
      setResizingColumn(null)
    }

    if (resizingColumn) {
      document.addEventListener("mousemove", handleMouseMove)
      document.addEventListener("mouseup", handleMouseUp)
      document.body.style.cursor = "col-resize"
      document.body.style.userSelect = "none"
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove)
      document.removeEventListener("mouseup", handleMouseUp)
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }
  }, [resizingColumn])

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
        {/* Column Headers */}
        <div className="flex items-center gap-2 py-1.5 px-2 text-xs font-semibold text-muted-foreground border-b-2 border-border sticky top-0 bg-background z-10 min-w-max">
          <div className="flex-shrink-0 relative" style={{ width: `${columnWidths.timestamp}px` }}>
            Timestamp
            <div
              className="absolute right-0 top-0 bottom-0 w-px bg-border hover:bg-primary cursor-col-resize hover:w-1 transition-all"
              onMouseDown={() => setResizingColumn("timestamp")}
            />
          </div>
          <div className="flex-shrink-0 text-center relative" style={{ width: `${columnWidths.level}px` }}>
            Level
            <div
              className="absolute right-0 top-0 bottom-0 w-px bg-border hover:bg-primary cursor-col-resize hover:w-1 transition-all"
              onMouseDown={() => setResizingColumn("level")}
            />
          </div>
          <div className="flex-shrink-0 relative" style={{ width: `${columnWidths.logger}px` }}>
            Logger
            <div
              className="absolute right-0 top-0 bottom-0 w-px bg-border hover:bg-primary cursor-col-resize hover:w-1 transition-all"
              onMouseDown={() => setResizingColumn("logger")}
            />
          </div>
          {type === "system" ? (
            <>
              <div className="flex-shrink-0 relative" style={{ width: `${columnWidths.module}px` }}>
                Module
                <div
                  className="absolute right-0 top-0 bottom-0 w-px bg-border hover:bg-primary cursor-col-resize hover:w-1 transition-all"
                  onMouseDown={() => setResizingColumn("module")}
                />
              </div>
              <div className="flex-shrink-0 relative" style={{ width: `${columnWidths.functionLine}px` }}>
                Function:Line
                <div
                  className="absolute right-0 top-0 bottom-0 w-px bg-border hover:bg-primary cursor-col-resize hover:w-1 transition-all"
                  onMouseDown={() => setResizingColumn("functionLine")}
                />
              </div>
            </>
          ) : (
            <div className="flex-shrink-0 relative" style={{ width: `${columnWidths.action}px` }}>
              Action
              <div
                className="absolute right-0 top-0 bottom-0 w-px bg-border hover:bg-primary cursor-col-resize hover:w-1 transition-all"
                onMouseDown={() => setResizingColumn("action")}
              />
            </div>
          )}
          <div className="flex-shrink-0 relative" style={{ width: `${columnWidths.message}px` }}>
            Message
            <div
              className="absolute right-0 top-0 bottom-0 w-px bg-border hover:bg-primary cursor-col-resize hover:w-1 transition-all"
              onMouseDown={() => setResizingColumn("message")}
            />
          </div>
          {type === "audit" && (
            <div className="flex-shrink-0 min-w-[100px]">Metadata</div>
          )}
        </div>

        {/* Log Entries */}
        {filteredLogs.length === 0 ? (
          <div className="text-center py-8 text-sm text-muted-foreground">
            {logs.length === 0 ? "No logs yet" : "No logs match the current filters"}
          </div>
        ) : type === "system" ? (
          (filteredLogs as SystemLog[]).map((log) => (
            <LogEntry key={log.id} log={log} type="system" columnWidths={columnWidths} />
          ))
        ) : (
          (filteredLogs as AuditLog[]).map((log) => (
            <LogEntry key={log.id} log={log} type="audit" columnWidths={columnWidths} />
          ))
        )}
      </div>
      <ScrollBar orientation="horizontal" />
    </ScrollArea>
  )
}
