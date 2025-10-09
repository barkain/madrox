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
import type { MessageFlow } from "@/types"

export default function MadroxMonitor() {
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string[]>([])
  const [typeFilter, setTypeFilter] = useState<string[]>([])
  const [auditLogHeight, setAuditLogHeight] = useState(240) // Default 240px (~15rem)
  const [isDragging, setIsDragging] = useState(false)
  const [isDraggingTerminal, setIsDraggingTerminal] = useState<string | null>(null)
  const [terminalSizes, setTerminalSizes] = useState<Record<string, { width: number; height: number }>>({})
  const [activeTab, setActiveTab] = useState<"graph" | "terminals">("graph")
  const [isAuditLogVisible, setIsAuditLogVisible] = useState(true)
  const [openTerminals, setOpenTerminals] = useState<Array<{ id: string; name: string }>>([])
  const [expandedTerminal, setExpandedTerminal] = useState<string | null>(null)
  const [dismissedTerminals, setDismissedTerminals] = useState<string[]>([])
  const [messageFlows, setMessageFlows] = useState<MessageFlow[]>([])
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
      if (isDragging && containerRef.current) {
        const containerRect = containerRef.current.getBoundingClientRect()
        const newHeight = containerRect.bottom - e.clientY

        // Min height: 100px, Max height: 60% of container
        const minHeight = 100
        const maxHeight = containerRect.height * 0.6
        const clampedHeight = Math.min(Math.max(newHeight, minHeight), maxHeight)

        setAuditLogHeight(clampedHeight)
      }

      if (isDraggingTerminal) {
        const terminalEl = document.getElementById(`terminal-${isDraggingTerminal}`)
        if (!terminalEl) return

        const rect = terminalEl.getBoundingClientRect()
        const newWidth = e.clientX - rect.left
        const newHeight = e.clientY - rect.top

        // Min size: 400x300px
        const minWidth = 400
        const minHeight = 300

        setTerminalSizes(prev => ({
          ...prev,
          [isDraggingTerminal]: {
            width: Math.max(newWidth, minWidth),
            height: Math.max(newHeight, minHeight)
          }
        }))
      }
    }

    const handleMouseUp = () => {
      setIsDragging(false)
      setIsDraggingTerminal(null)
    }

    if (isDragging || isDraggingTerminal) {
      window.addEventListener("mousemove", handleMouseMove)
      window.addEventListener("mouseup", handleMouseUp)
    }

    return () => {
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseup", handleMouseUp)
    }
  }, [isDragging, isDraggingTerminal])

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

  // Track message flows from audit logs
  useEffect(() => {
    const MESSAGE_FLOW_DURATION = 3000 // 3 seconds

    // Process audit logs to create message flows
    const newFlows: MessageFlow[] = []

    auditLogs.forEach((log) => {
      if ((log.type === "message_sent" || log.type === "message_exchange") && log.metadata) {
        const { from_instance, to_instance, message_id } = log.metadata

        if (from_instance && to_instance && message_id) {
          const timestamp = new Date(log.timestamp)
          const now = new Date()
          const age = now.getTime() - timestamp.getTime()
          const isActive = age < MESSAGE_FLOW_DURATION

          newFlows.push({
            id: message_id,
            fromId: from_instance,
            toId: to_instance,
            timestamp,
            active: isActive,
          })
        }
      }
    })

    setMessageFlows(newFlows)

    // Set up interval to update active state
    const interval = setInterval(() => {
      setMessageFlows((prev) =>
        prev.map((flow) => ({
          ...flow,
          active: new Date().getTime() - flow.timestamp.getTime() < MESSAGE_FLOW_DURATION,
        }))
      )
    }, 100)

    return () => clearInterval(interval)
  }, [auditLogs])

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
            <NetworkGraph instances={filteredInstances} messageFlows={messageFlows} onNodeClick={handleNodeClick} />
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
                  {openTerminals.map((terminal) => {
                    const size = terminalSizes[terminal.id]
                    return (
                      <div
                        key={terminal.id}
                        id={`terminal-${terminal.id}`}
                        className="border border-border rounded-lg overflow-hidden bg-card hover:border-primary transition-colors relative"
                        style={size ? { width: `${size.width}px`, height: `${size.height}px` } : { height: '320px' }}
                      >
                        <div
                          className="px-3 py-2 border-b border-border bg-muted/50 flex items-center justify-between"
                        >
                          <div className="flex items-center gap-2 cursor-pointer hover:opacity-80" onClick={() => setExpandedTerminal(terminal.id)}>
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
                        <div className="h-[calc(100%-2.5rem)] bg-[#1e1e1e]">
                          <TerminalViewer
                            instanceId={terminal.id}
                            instanceName={terminal.name}
                            onClose={() => {}}
                            compact
                          />
                        </div>
                        {/* Resize Handle */}
                        <div
                          className="absolute bottom-0 right-0 w-4 h-4 cursor-nwse-resize hover:bg-primary/30 transition-colors"
                          onMouseDown={(e) => {
                            e.stopPropagation()
                            e.preventDefault()
                            setIsDraggingTerminal(terminal.id)
                          }}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <svg className="w-full h-full text-muted-foreground" viewBox="0 0 16 16">
                            <path d="M14,12 L12,14 M14,8 L8,14 M14,4 L4,14" stroke="currentColor" strokeWidth="1" fill="none" />
                          </svg>
                        </div>
                      </div>
                    )
                  })}
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
