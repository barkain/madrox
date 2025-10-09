"use client"

import { Pause, Play, Trash2, Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import { LogFilters } from "@/components/log-filters"
import { LogList } from "@/components/log-list"
import { useLogStore } from "@/store/log-store"
import type { SystemLog, AuditLog } from "@/types"

interface SystemLogPanelProps {
  type: "system"
}

interface AuditLogPanelProps {
  type: "audit"
}

type LogPanelProps = SystemLogPanelProps | AuditLogPanelProps

export function LogPanel({ type }: LogPanelProps) {
  const {
    // System log state and actions
    systemLogs,
    systemFilters,
    systemAutoScroll,
    systemPaused,
    clearSystemLogs,
    toggleSystemLevel,
    setSystemSearch,
    toggleSystemPause,

    // Audit log state and actions
    auditLogs,
    auditFilters,
    auditAutoScroll,
    auditPaused,
    clearAuditLogs,
    toggleAuditLevel,
    setAuditSearch,
    toggleAuditPause,
  } = useLogStore()

  const isSystem = type === "system"

  // Select appropriate state and actions based on type
  const logs = isSystem ? systemLogs : auditLogs
  const filters = isSystem ? systemFilters : auditFilters
  const autoScroll = isSystem ? systemAutoScroll : auditAutoScroll
  const isPaused = isSystem ? systemPaused : auditPaused

  const toggleLevel = isSystem ? toggleSystemLevel : toggleAuditLevel
  const setSearch = isSystem ? setSystemSearch : setAuditSearch
  const clearLogs = isSystem ? clearSystemLogs : clearAuditLogs
  const togglePause = isSystem ? toggleSystemPause : toggleAuditPause

  const handleClearSearch = () => setSearch("")

  const handleExport = () => {
    const dataStr = JSON.stringify(logs, null, 2)
    const dataUri = "data:application/json;charset=utf-8," + encodeURIComponent(dataStr)
    const exportFileDefaultName = `${type}-logs-${new Date().toISOString()}.json`

    const linkElement = document.createElement("a")
    linkElement.setAttribute("href", dataUri)
    linkElement.setAttribute("download", exportFileDefaultName)
    linkElement.click()
  }

  return (
    <div className="flex flex-col h-full border border-border rounded-lg overflow-hidden bg-card">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-card/80">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold text-foreground capitalize">
            {type} Logs
          </h2>
          <span className="text-xs text-muted-foreground">
            {logs.length} {logs.length === 1 ? "entry" : "entries"}
          </span>
          {isPaused && (
            <span className="text-xs bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300 px-2 py-0.5 rounded font-medium">
              PAUSED
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          <Button
            size="sm"
            variant="ghost"
            onClick={togglePause}
            title={isPaused ? "Resume logging" : "Pause logging"}
            className="h-7 w-7 p-0"
          >
            {isPaused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
          </Button>

          <Button
            size="sm"
            variant="ghost"
            onClick={clearLogs}
            title="Clear logs"
            className="h-7 w-7 p-0"
            disabled={logs.length === 0}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>

          <Button
            size="sm"
            variant="ghost"
            onClick={handleExport}
            title="Export logs as JSON"
            className="h-7 w-7 p-0"
            disabled={logs.length === 0}
          >
            <Download className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Filters */}
      <LogFilters
        levels={filters.levels}
        search={filters.search}
        onToggleLevel={toggleLevel}
        onSearchChange={setSearch}
        onClearSearch={handleClearSearch}
      />

      {/* Log List */}
      {isSystem ? (
        <LogList logs={systemLogs} filters={filters} autoScroll={autoScroll} type="system" />
      ) : (
        <LogList logs={auditLogs} filters={filters} autoScroll={autoScroll} type="audit" />
      )}
    </div>
  )
}
