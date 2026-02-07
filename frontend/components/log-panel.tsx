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
    <div className="flex flex-col h-full rounded-xl overflow-hidden border border-white/10 backdrop-blur-xl bg-white/5 shadow-2xl shadow-black/20">
      {/* Header - Glass morphism with gradient text */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-gradient-to-r from-white/5 to-white/[0.02]">
        <div className="flex items-center gap-3">
          <h2 className={`text-sm font-bold bg-gradient-to-r ${isSystem ? 'from-cyan-400 to-blue-400' : 'from-emerald-400 to-teal-400'} bg-clip-text text-transparent capitalize`}>
            {type} Logs
          </h2>
          <span className="text-xs text-slate-400 px-2 py-0.5 rounded-full bg-white/5 border border-white/10">
            {logs.length} {logs.length === 1 ? "entry" : "entries"}
          </span>
          {isPaused && (
            <span className="text-xs bg-amber-500/20 text-amber-300 px-2.5 py-0.5 rounded-full font-medium border border-amber-500/30 animate-pulse">
              PAUSED
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={togglePause}
            title={isPaused ? "Resume logging" : "Pause logging"}
            className="h-8 w-8 p-0 rounded-lg hover:bg-white/10 hover:text-white transition-all duration-200 text-slate-400"
          >
            {isPaused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
          </Button>

          <Button
            size="sm"
            variant="ghost"
            onClick={clearLogs}
            title="Clear logs"
            className="h-8 w-8 p-0 rounded-lg hover:bg-white/10 hover:text-white transition-all duration-200 text-slate-400 disabled:opacity-30"
            disabled={logs.length === 0}
          >
            <Trash2 className="h-4 w-4" />
          </Button>

          <Button
            size="sm"
            variant="ghost"
            onClick={handleExport}
            title="Export logs as JSON"
            className="h-8 w-8 p-0 rounded-lg hover:bg-white/10 hover:text-white transition-all duration-200 text-slate-400 disabled:opacity-30"
            disabled={logs.length === 0}
          >
            <Download className="h-4 w-4" />
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
