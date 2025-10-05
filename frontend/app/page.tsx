"use client"

import { useState, useRef, useEffect } from "react"
import { ConnectionStatus } from "@/components/connection-status"
import { StatsHeader } from "@/components/stats-header"
import { FilterBar } from "@/components/filter-bar"
import { NetworkGraph } from "@/components/network-graph"
import { AuditLog } from "@/components/audit-log"
import { useWebSocket } from "@/hooks/use-websocket"

export default function MadroxMonitor() {
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string[]>([])
  const [typeFilter, setTypeFilter] = useState<string[]>([])
  const [auditLogHeight, setAuditLogHeight] = useState(240) // Default 240px (~15rem)
  const [isDragging, setIsDragging] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const { connectionStatus, instances, auditLogs, stats } = useWebSocket()

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

          {/* Bottom Row - Filters */}
          <div className="px-6 pb-3">
            <FilterBar
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              statusFilter={statusFilter}
              onStatusFilterChange={setStatusFilter}
              typeFilter={typeFilter}
              onTypeFilterChange={setTypeFilter}
            />
          </div>
        </div>

        {/* Network Graph - Dynamic height based on audit log */}
        <div className="overflow-hidden" style={{ flex: `1 1 calc(100% - ${auditLogHeight}px)` }}>
          <NetworkGraph instances={filteredInstances} />
        </div>

        {/* Resizable Divider */}
        <div
          className={`h-1 border-t border-border cursor-ns-resize hover:bg-primary/20 transition-colors ${
            isDragging ? "bg-primary/30" : ""
          }`}
          onMouseDown={handleMouseDown}
        />

        {/* Resizable Audit Log */}
        <div style={{ flex: `0 0 ${auditLogHeight}px` }}>
          <AuditLog logs={auditLogs} height={auditLogHeight} />
        </div>
      </div>
    </div>
  )
}
