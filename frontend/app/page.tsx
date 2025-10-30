"use client"

import { useState, useRef, useEffect } from "react"
import { X } from "lucide-react"
import { ConnectionStatus } from "@/components/connection-status"
import { StatsHeader } from "@/components/stats-header"
import { FilterBar } from "@/components/filter-bar"
import { NetworkGraph } from "@/components/network-graph"
import { TerminalViewer } from "@/components/terminal-viewer"
import { useWebSocket } from "@/hooks/use-websocket"
import type { MessageFlow } from "@/types"
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
  DragStartEvent,
  DragOverlay,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  rectSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

// Sortable Terminal Component
interface SortableTerminalProps {
  terminal: { id: string; name: string }
  size?: { width: number; height: number }
  onExpand: (id: string) => void
  onClose: (id: string) => void
  onResizeStart: (id: string) => void
}

function SortableTerminal({ terminal, size, onExpand, onClose, onResizeStart }: SortableTerminalProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: terminal.id,
    transition: {
      duration: 200,
      easing: 'ease-out',
    },
  })

  // With flexbox, terminals wrap naturally based on width
  const style = {
    transform: CSS.Transform.toString(transform),
    transition: transition || 'transform 200ms ease-out',
    opacity: isDragging ? 0.4 : 1,
    zIndex: isDragging ? 1000 : 'auto',
    width: size ? `${size.width}px` : '600px', // Increased from 400px to 600px (150%)
    height: size ? `${size.height}px` : '320px',
    flexShrink: 0, // Prevent shrinking
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`border border-border rounded-lg overflow-hidden bg-card transition-all relative ${
        isDragging
          ? 'border-primary shadow-2xl scale-105 ring-2 ring-primary/50'
          : 'hover:border-primary hover:shadow-lg'
      }`}
      id={`terminal-${terminal.id}`}
      role="article"
      aria-label={`Terminal for ${terminal.name}`}
      tabIndex={0}
    >
      <div
        className="px-3 py-2 border-b border-border bg-muted/50 flex items-center justify-between cursor-grab active:cursor-grabbing"
        {...attributes}
        {...listeners}
        role="button"
        aria-label={`Drag to reorder ${terminal.name} terminal`}
        tabIndex={-1}
      >
        <div
          className="flex items-center gap-2 cursor-pointer hover:opacity-80"
          onClick={(e) => { e.stopPropagation(); onExpand(terminal.id); }}
          role="button"
          aria-label={`Expand ${terminal.name} terminal`}
        >
          <span className="text-xs font-semibold truncate">{terminal.name}</span>
          <span className="text-xs text-muted-foreground font-mono">{terminal.id.slice(0, 8)}</span>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onClose(terminal.id)
          }}
          className="p-1 rounded hover:bg-muted transition-colors"
          aria-label={`Close ${terminal.name} terminal`}
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
        className="absolute bottom-0 right-0 w-4 h-4 cursor-nwse-resize hover:bg-primary/50 transition-all z-10 group"
        onMouseDown={(e) => {
          e.stopPropagation()
          e.preventDefault()
          onResizeStart(terminal.id)
        }}
        onClick={(e) => e.stopPropagation()}
        role="button"
        aria-label={`Resize ${terminal.name} terminal`}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onResizeStart(terminal.id)
          }
        }}
      >
        <svg className="w-full h-full text-muted-foreground group-hover:text-primary transition-colors" viewBox="0 0 16 16">
          <path d="M14,12 L12,14 M14,8 L8,14 M14,4 L4,14" stroke="currentColor" strokeWidth="1.5" fill="none" />
        </svg>
      </div>
    </div>
  )
}

export default function MadroxMonitor() {
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string[]>([])
  const [typeFilter, setTypeFilter] = useState<string[]>([])
  const [isDraggingTerminal, setIsDraggingTerminal] = useState<string | null>(null)
  const [isResizing, setIsResizing] = useState<string | null>(null)
  const [terminalSizes, setTerminalSizes] = useState<Record<string, { width: number; height: number }>>({})
  const [activeTab, setActiveTab] = useState<"graph" | "terminals">("graph")
  const [openTerminals, setOpenTerminals] = useState<Array<{ id: string; name: string }>>([])
  const [terminalGridPositions, setTerminalGridPositions] = useState<Record<string, { row: number; col: number; colSpan: number }>>({})
  const [expandedTerminal, setExpandedTerminal] = useState<string | null>(null)
  const [dismissedTerminals, setDismissedTerminals] = useState<string[]>([])
  const [messageFlows, setMessageFlows] = useState<MessageFlow[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [announcement, setAnnouncement] = useState<string>('')
  const containerRef = useRef<HTMLDivElement>(null)

  // Configure drag sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8, // 8px movement required before drag starts
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

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

  // Drag handlers for terminal reordering
  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string)
    const terminal = openTerminals.find((t) => t.id === event.active.id)
    if (terminal) {
      setAnnouncement(`Picked up terminal ${terminal.name}. Use arrow keys to move, space to drop.`)
    }
  }

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event

    setActiveId(null)

    if (over && active.id !== over.id) {
      const activeTerminal = openTerminals.find((t) => t.id === active.id)
      const overTerminal = openTerminals.find((t) => t.id === over.id)

      setOpenTerminals((terminals) => {
        const oldIndex = terminals.findIndex((t) => t.id === active.id)
        const newIndex = terminals.findIndex((t) => t.id === over.id)
        return arrayMove(terminals, oldIndex, newIndex)
      })

      if (activeTerminal && overTerminal) {
        setAnnouncement(`Moved terminal ${activeTerminal.name} to position ${openTerminals.findIndex((t) => t.id === over.id) + 1}`)
      }
    } else if (active.id) {
      const terminal = openTerminals.find((t) => t.id === active.id)
      if (terminal) {
        setAnnouncement(`Terminal ${terminal.name} returned to original position`)
      }
    }
  }

  // Resize handler with automatic reflow
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isResizing) {
        const terminalEl = document.getElementById(`terminal-${isResizing}`)
        if (!terminalEl) return

        const rect = terminalEl.getBoundingClientRect()
        const newWidth = e.clientX - rect.left
        const newHeight = e.clientY - rect.top

        // Min size: 650x500px (width increased from 400px to 600px for 150% scaling)
        const minWidth = 650
        const minHeight = 500

        const finalWidth = Math.max(newWidth, minWidth)
        const finalHeight = Math.max(newHeight, minHeight)

        setTerminalSizes(prev => ({
          ...prev,
          [isResizing]: {
            width: finalWidth,
            height: finalHeight
          }
        }))

        // Check if terminal is becoming full-width and trigger reorder
        const containerWidth = containerRef.current?.clientWidth || window.innerWidth
        const isFullWidth = finalWidth >= containerWidth * 0.85

        // Determine grid column span for CSS Grid
        const columnCount = containerWidth >= 1024 ? 3 : containerWidth >= 768 ? 2 : 1

        // Track if terminal just became full-width
        const wasFullWidth = terminalSizes[isResizing]?.width >= containerWidth * 0.85

        if (isFullWidth && !wasFullWidth) {
          // Just became full-width - trigger immediate reorder
          setTimeout(() => {
            setOpenTerminals(prev => {
              const currentIndex = prev.findIndex(t => t.id === isResizing)
              if (currentIndex === -1) return prev

              // Find the row this terminal is on by checking x positions
              const resizingTerminal = prev[currentIndex]

              // Collect all terminals and separate into before/same-row/after
              const beforeRow: typeof prev = []
              const sameRow: typeof prev = []
              const afterRow: typeof prev = []

              prev.forEach((t, idx) => {
                if (idx < currentIndex) {
                  beforeRow.push(t)
                } else if (idx > currentIndex) {
                  afterRow.push(t)
                }
              })

              // Reorder: before + full-width terminal + everything else moves after
              return [...beforeRow, resizingTerminal, ...afterRow]
            })
          }, 0)
        }
      }
    }

    const handleMouseUp = () => {
      if (isResizing) {
        // Force re-render to update grid layout after resize
        setOpenTerminals(prev => [...prev])
      }
      setIsResizing(null)
    }

    if (isResizing) {
      window.addEventListener("mousemove", handleMouseMove)
      window.addEventListener("mouseup", handleMouseUp)
    }

    return () => {
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseup", handleMouseUp)
    }
  }, [isResizing])

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
      {/* Screen reader announcements for accessibility */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {announcement}
      </div>

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
                <DndContext
                  sensors={sensors}
                  collisionDetection={closestCenter}
                  onDragStart={handleDragStart}
                  onDragEnd={handleDragEnd}
                >
                  <SortableContext
                    items={openTerminals.map((t) => t.id)}
                    strategy={rectSortingStrategy}
                  >
                    <div className="flex flex-wrap gap-4">
                      {openTerminals.map((terminal) => (
                        <SortableTerminal
                          key={terminal.id}
                          terminal={terminal}
                          size={terminalSizes[terminal.id]}
                          onExpand={setExpandedTerminal}
                          onClose={closeTerminal}
                          onResizeStart={setIsResizing}
                        />
                      ))}
                    </div>
                  </SortableContext>
                  <DragOverlay dropAnimation={{
                    duration: 200,
                    easing: 'ease-out',
                  }}>
                    {activeId ? (
                      <div className="border-2 border-primary rounded-lg overflow-hidden bg-card shadow-2xl ring-4 ring-primary/30 scale-105 rotate-2">
                        <div className="px-3 py-2 border-b border-border bg-muted/50 flex items-center justify-between cursor-grabbing">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-semibold truncate">
                              {openTerminals.find((t) => t.id === activeId)?.name}
                            </span>
                            <span className="text-xs text-muted-foreground font-mono">
                              {activeId.slice(0, 8)}
                            </span>
                          </div>
                          <div className="p-1 opacity-50">
                            <X className="h-3 w-3" />
                          </div>
                        </div>
                        <div className="h-64 bg-[#1e1e1e] flex items-center justify-center">
                          <div className="text-muted-foreground text-sm">
                            Drag to reorder
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </DragOverlay>
                </DndContext>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
