"use client"

import { useState, useRef, useEffect } from "react"
import { X } from "lucide-react"
import { ConnectionStatus } from "@/components/connection-status"
import { StatsHeader } from "@/components/stats-header"
import { FilterBar } from "@/components/filter-bar"
import { NetworkGraph } from "@/components/network-graph"
import { AuditLog } from "@/components/audit-log"
import { TerminalViewer } from "@/components/terminal-viewer"
import { useWebSocket } from "@/hooks/use-websocket"

export default function MadroxMonitor() {
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string[]>([])
  const [typeFilter, setTypeFilter] = useState<string[]>([])
  const [auditLogHeight, setAuditLogHeight] = useState(240) // Default 240px (~15rem)
  const [isDragging, setIsDragging] = useState(false)
  const [activeTab, setActiveTab] = useState<"graph" | "terminals">("graph")
  const [isAuditLogVisible, setIsAuditLogVisible] = useState(true)
  const [openTerminals, setOpenTerminals] = useState<Array<{ id: string; name: string }>>([])
  const [expandedTerminal, setExpandedTerminal] = useState<string | null>(null)
  const [dismissedTerminals, setDismissedTerminals] = useState<string[]>([])
  const containerRef = useRef<HTMLDivElement>(null)

  const { connectionStatus, instances, auditLogs, stats } = useWebSocket()

  const handleNodeClick = (instance: { id: string; name: string }) => {
    setOpenTerminals((prev) => {
      if (prev.find((t) => t.id === instance.id)) {
        return prev
      }
      return [...prev, instance]
    })
    setDismissedTerminals((prev) => prev.filter((id) => id !== instance.id))
    setActiveTab("terminals")
    setExpandedTerminal(instance.id)
  }

  const closeTerminal = (instanceId: string) => {
    setOpenTerminals((prev) => prev.filter((t) => t.id !== instanceId))
    setDismissedTerminals((prev) => (prev.includes(instanceId) ? prev : [...prev, instanceId]))
    setExpandedTerminal((current) => (current === instanceId ? null : current))
  }

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging || !containerRef.current) return

      const containerRect = containerRef.current.getBoundingClientRect()
      const newHeight = containerRect.bottom - e.clientY

      // Min height: 100px, Max height: 60% of container
      const minHeight = 100
      const maxHeight = containerRect.height * 0.6
      const clampedHeight = Math.min(Math.max(newHeight, minHeight), maxHeight)

      setAuditLogHeight(clampedHeight)
    }

    const handleMouseUp = () => {
      setIsDragging(false)
    }

    if (isDragging) {
      window.addEventListener("mousemove", handleMouseMove)
      window.addEventListener("mouseup", handleMouseUp)
    }

    return () => {
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseup", handleMouseUp)
    }
  }, [isDragging])

  useEffect(() => {
    setOpenTerminals((prev) => {
      if (instances.length === 0) {
        return prev.length === 0 ? prev : []
      }

      const instanceMap = new Map(instances.map((instance) => [instance.id, instance]))
      let didChange = false

      const next: Array<{ id: string; name: string }> = []

      prev.forEach((terminal) => {
        const instance = instanceMap.get(terminal.id)
        if (!instance) {
          didChange = true
          return
        }
        if (terminal.name !== instance.name) {
          didChange = true
          next.push({ id: terminal.id, name: instance.name })
          return
        }
        next.push(terminal)
      })

      const existingIds = new Set(next.map((terminal) => terminal.id))

      instances.forEach((instance) => {
        if (!existingIds.has(instance.id) && !dismissedTerminals.includes(instance.id)) {
          next.push({ id: instance.id, name: instance.name })
          didChange = true
        }
      })

      if (!didChange) {
        return prev
      }

      return next
    })
  }, [instances, dismissedTerminals])

  useEffect(() => {
    if (expandedTerminal && !openTerminals.some((terminal) => terminal.id === expandedTerminal)) {
      setExpandedTerminal(openTerminals.length > 0 ? openTerminals[0].id : null)
    }
  }, [openTerminals, expandedTerminal])

  // Filter instances based on search and filters
  const filteredInstances = instances.filter((instance) => {
    const matchesSearch =
      searchQuery === "" ||
      instance.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      instance.name?.toLowerCase().includes(searchQuery.toLowerCase())

    const matchesStatus = statusFilter.length === 0 || statusFilter.includes(instance.status)

    const matchesType = typeFilter.length === 0 || typeFilter.includes(instance.type)

    return matchesSearch && matchesStatus && matchesType
  })

  return (
    <div className="flex flex-col h-screen bg-background">
      <ConnectionStatus status={connectionStatus} />

      <div ref={containerRef} className="flex-1 flex flex-col overflow-hidden">
        {/* Elegant Header - Two Rows */}
        <div className="border-b border-border">
          {/* Top Row - Title and Stats */}
          <div className="px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-8">
              <div>
                <h1 className="text-xl font-semibold text-foreground">Madrox Monitor</h1>
                <p className="text-sm text-muted-foreground">Real-time agent network</p>
              </div>

              <div className="h-10 w-px bg-border/50" />

              <StatsHeader stats={stats} />
            </div>
          </div>

          {/* Bottom Row - Filters and Tabs */}
          <div className="px-6 pb-3 flex items-center justify-between gap-4">
            <FilterBar
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              statusFilter={statusFilter}
              onStatusFilterChange={setStatusFilter}
              typeFilter={typeFilter}
              onTypeFilterChange={setTypeFilter}
            />

            {/* Tab Switcher */}
            <div className="flex gap-2">
              <button
                onClick={() => setActiveTab("graph")}
                className={`px-4 py-1.5 text-sm font-medium rounded transition-colors ${
                  activeTab === "graph"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                Network Graph
              </button>
              <button
                onClick={() => setActiveTab("terminals")}
                className={`px-4 py-1.5 text-sm font-medium rounded transition-colors ${
                  activeTab === "terminals"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                Terminals ({openTerminals.length})
              </button>
            </div>
          </div>
        </div>

        {/* Content Area - Tabbed */}
        <div className="flex-1 overflow-hidden">
          {activeTab === "graph" ? (
            <NetworkGraph instances={filteredInstances} onNodeClick={handleNodeClick} />
          ) : (
            <div className="h-full p-4 overflow-auto bg-background">
              {openTerminals.length === 0 ? (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  <div className="text-center">
                    <p className="text-lg">No terminals open</p>
                    <p className="text-sm mt-2">Click on an instance node in the Network Graph to open its terminal</p>
                  </div>
                </div>
              ) : expandedTerminal ? (
                <div className="h-full">
                  <TerminalViewer
                    instanceId={expandedTerminal}
                    instanceName={openTerminals.find((t) => t.id === expandedTerminal)?.name || expandedTerminal}
                    onClose={() => setExpandedTerminal(null)}
                  />
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 auto-rows-fr">
                  {openTerminals.map((terminal) => (
                    <div
                      key={terminal.id}
                      className="border border-border rounded-lg overflow-hidden bg-card hover:border-primary transition-colors cursor-pointer h-80"
                      onClick={() => setExpandedTerminal(terminal.id)}
                    >
                      <div className="px-3 py-2 border-b border-border bg-muted/50 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold truncate">{terminal.name}</span>
                          <span className="text-xs text-muted-foreground font-mono">{terminal.id.slice(0, 8)}</span>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            closeTerminal(terminal.id)
                          }}
                          className="p-1 rounded hover:bg-muted transition-colors"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                      <div className="p-2 h-[calc(100%-2.5rem)] bg-[#1e1e1e] overflow-hidden">
                        <TerminalViewer
                          instanceId={terminal.id}
                          instanceName={terminal.name}
                          onClose={() => {}}
                          compact
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Resizable Divider - Only show when audit log is visible */}
        {isAuditLogVisible && (
          <div
            className={`h-1 border-t border-border cursor-ns-resize hover:bg-primary/20 transition-colors ${
              isDragging ? "bg-primary/30" : ""
            }`}
            onMouseDown={handleMouseDown}
          />
        )}

        {/* Audit Log - Collapsible */}
        <div style={{ flex: isAuditLogVisible ? `0 0 ${auditLogHeight}px` : '0 0 auto' }}>
          <AuditLog
            logs={auditLogs}
            height={auditLogHeight}
            isCollapsed={!isAuditLogVisible}
            onToggle={() => setIsAuditLogVisible(!isAuditLogVisible)}
          />
        </div>
      </div>
    </div>
  )
}
