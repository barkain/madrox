"use client"

import { useState } from "react"
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

  const { connectionStatus, instances, auditLogs, stats } = useWebSocket()

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

      <div className="flex-1 flex flex-col overflow-hidden">
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

        {/* Network Graph - Takes most of the space */}
        <div className="flex-1 overflow-hidden">
          <NetworkGraph instances={filteredInstances} />
        </div>

        {/* Compact Audit Log */}
        <AuditLog logs={auditLogs} />
      </div>
    </div>
  )
}
