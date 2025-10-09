"use client"

import { useEffect, useCallback, useState } from "react"
import {
  ReactFlow,
  ReactFlowProvider,
  type Node,
  type Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  useReactFlow,
  MarkerType,
  ControlButton,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { RotateCcw } from "lucide-react"
import { AgentNode } from "./agent-node"
import type { AgentInstance, MessageFlow } from "@/types"

const nodeTypes = {
  agent: AgentNode,
}

interface NetworkGraphProps {
  instances: AgentInstance[]
  messageFlows?: MessageFlow[]
  onNodeClick?: (instance: AgentInstance) => void
}

// Tree layout algorithm that respects parent-child structure
function calculateHierarchicalLayout(instances: AgentInstance[]): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>()
  const horizontalSpacing = 400
  const verticalSpacing = 250

  const instanceMap = new Map(instances.map((instance) => [instance.id, instance]))

  // Global X counter to ensure left-to-right ordering
  let globalX = 0

  // Recursive function to layout a subtree
  const layoutSubtree = (instance: AgentInstance, level: number): { x: number; width: number } => {
    // Get children that are still present in the dataset, sorted by creation time for consistent ordering
    const children = instances
      .filter((candidate) => candidate.parentId === instance.id && instanceMap.has(candidate.id))
      .sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())

    if (children.length === 0) {
      // Leaf node - position it at the next available X
      const x = globalX
      positions.set(instance.id, { x, y: level * verticalSpacing + 100 })
      globalX += horizontalSpacing
      return { x, width: 0 }
    }

    // Layout all children first (left to right)
    const childResults: { x: number; width: number }[] = []
    children.forEach((child) => {
      const result = layoutSubtree(child, level + 1)
      childResults.push(result)
    })

    // Calculate parent position (centered above children)
    let parentX: number
    if (childResults.length === 1) {
      // Single child - parent directly above child
      parentX = childResults[0].x
    } else {
      // Multiple children - center parent above all children
      const leftmostChildX = childResults[0].x
      const rightmostChildX = childResults[childResults.length - 1].x
      parentX = (leftmostChildX + rightmostChildX) / 2
    }

    positions.set(instance.id, { x: parentX, y: level * verticalSpacing + 100 })

    // Return parent position and total width
    const totalWidth = childResults.length > 1
      ? childResults[childResults.length - 1].x - childResults[0].x
      : 0
    return { x: parentX, width: totalWidth }
  }

  // Treat instances with no parent or with a missing parent as roots and layout each tree
  const rootNodes = instances
    .filter((instance) => !instance.parentId || !instanceMap.has(instance.parentId))
    .sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())

  rootNodes.forEach((root, index) => {
    // Add spacing before each tree (except the first)
    if (index > 0) {
      globalX += horizontalSpacing
    }
    layoutSubtree(root, 0)
  })

  // Assign fallback positions to any nodes that were not reached (e.g. due to malformed parent references)
  instances.forEach((instance) => {
    if (!positions.has(instance.id)) {
      const x = globalX
      positions.set(instance.id, { x, y: 100 })
      globalX += horizontalSpacing
    }
  })

  return positions
}

function NetworkGraphInner({ instances, messageFlows = [], onNodeClick }: NetworkGraphProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const { fitView } = useReactFlow()

  // Handle node clicks
  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      const instance = instances.find((i) => i.id === node.id)
      if (instance && onNodeClick) {
        onNodeClick(instance)
      }
    },
    [instances, onNodeClick],
  )

  // Watch for container resize and re-fit the view
  useEffect(() => {
    const handleResize = () => {
      fitView({ padding: 0.2, duration: 300, maxZoom: 0.6 })
    }

    window.addEventListener("resize", handleResize)

    // Also set up a mutation observer to detect container size changes
    const observer = new ResizeObserver(() => {
      fitView({ padding: 0.2, duration: 300, maxZoom: 0.6 })
    })

    const container = document.querySelector(".react-flow")
    if (container) {
      observer.observe(container)
    }

    return () => {
      window.removeEventListener("resize", handleResize)
      observer.disconnect()
    }
  }, [fitView])

  // Layout reset function
  const resetLayout = useCallback(() => {
    const positions = calculateHierarchicalLayout(instances)

    const newNodes: Node[] = instances.map((instance) => {
      const position = positions.get(instance.id) || { x: 0, y: 0 }
      return {
        id: instance.id,
        type: "agent",
        position,
        data: instance,
      }
    })

    setNodes(newNodes)

    // Fit view after layout
    setTimeout(() => {
      fitView({ padding: 0.2, duration: 500, maxZoom: 0.6 })
    }, 50)
  }, [instances, setNodes, fitView])

  // Convert instances to React Flow nodes and edges
  useEffect(() => {
    const positions = calculateHierarchicalLayout(instances)

    const newNodes: Node[] = instances.map((instance) => {
      const position = positions.get(instance.id) || { x: 0, y: 0 }
      return {
        id: instance.id,
        type: "agent",
        position,
        data: instance,
      }
    })

    const instanceMap = new Map(instances.map((instance) => [instance.id, instance]))

    // Parent-child edges (hierarchy)
    const hierarchyEdges: Edge[] = instances
      .filter((instance) => instance.parentId && instanceMap.has(instance.parentId))
      .map((instance) => ({
        id: `hierarchy-${instance.parentId}-${instance.id}`,
        source: instance.parentId!,
        target: instance.id,
        type: "smoothstep",
        animated: instance.status === "running",
        style: {
          stroke: instance.status === "running" ? "var(--color-primary)" : "var(--color-border)",
          strokeWidth: 2,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: instance.status === "running" ? "var(--color-primary)" : "var(--color-border)",
        },
      }))

    // Message flow edges (communication)
    const messageEdges: Edge[] = messageFlows
      .filter((flow) => instanceMap.has(flow.fromId) && instanceMap.has(flow.toId))
      .map((flow) => ({
        id: `message-${flow.id}`,
        source: flow.fromId,
        target: flow.toId,
        type: "straight",
        animated: flow.active,
        style: {
          stroke: flow.active ? "#10b981" : "#6b7280", // green-500 : gray-500
          strokeWidth: 3,
          strokeDasharray: "5,5",
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: flow.active ? "#10b981" : "#6b7280",
        },
        zIndex: 1000, // Show message edges above hierarchy edges
      }))

    const newEdges = [...hierarchyEdges, ...messageEdges]

    setNodes(newNodes)
    setEdges(newEdges)
  }, [instances, messageFlows, setNodes, setEdges])

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={handleNodeClick}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.2, maxZoom: 0.6 }}
      defaultViewport={{ x: 0, y: 0, zoom: 0.5 }}
      minZoom={0.1}
      maxZoom={2}
    >
      <Background color="var(--color-border)" gap={16} />
      <Controls className="bg-card border-border">
        <ControlButton onClick={resetLayout} title="Reset Layout">
          <RotateCcw className="w-4 h-4" />
        </ControlButton>
      </Controls>
      <MiniMap
        className="bg-card border border-border hidden"
        nodeColor={(node) => {
          const status = (node.data as AgentInstance).status
          const colors = {
            running: "var(--color-status-running)",
            pending: "var(--color-status-pending)",
            error: "var(--color-status-error)",
            terminated: "var(--color-status-terminated)",
          }
          return colors[status as keyof typeof colors] || "var(--color-muted)"
        }}
      />
    </ReactFlow>
  )
}

export function NetworkGraph({ instances, messageFlows, onNodeClick }: NetworkGraphProps) {
  return (
    <div className="w-full h-full bg-background">
      <ReactFlowProvider>
        <NetworkGraphInner instances={instances} messageFlows={messageFlows} onNodeClick={onNodeClick} />
      </ReactFlowProvider>
    </div>
  )
}
