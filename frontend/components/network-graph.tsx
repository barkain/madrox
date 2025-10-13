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
import { hierarchy, tree } from "d3-hierarchy"
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

// D3-based tree layout algorithm for symmetric, balanced hierarchies
function calculateHierarchicalLayout(instances: AgentInstance[]): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>()
  const horizontalSpacing = 400 // Horizontal node spacing
  const verticalSpacing = 250 // Vertical level spacing

  if (instances.length === 0) return positions

  const instanceMap = new Map(instances.map((instance) => [instance.id, instance]))

  // Find all root nodes (no parent or parent not in dataset)
  const rootNodes = instances
    .filter((instance) => !instance.parentId || !instanceMap.has(instance.parentId))
    .sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())

  if (rootNodes.length === 0) return positions

  // Build hierarchical data structure for each root
  interface HierarchyNode {
    id: string
    instance: AgentInstance
    children?: HierarchyNode[]
  }

  function buildHierarchy(instanceId: string): HierarchyNode {
    const instance = instanceMap.get(instanceId)!
    const children = instances
      .filter((child) => child.parentId === instanceId)
      .sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())
      .map((child) => buildHierarchy(child.id))

    return {
      id: instanceId,
      instance,
      children: children.length > 0 ? children : undefined,
    }
  }

  // Layout each root tree separately with D3
  const treeLayouts: Array<{ root: any; width: number; height: number }> = []

  rootNodes.forEach((rootInstance) => {
    const hierarchyData = buildHierarchy(rootInstance.id)
    const root = hierarchy(hierarchyData)

    // Configure D3 tree layout
    const treeLayout = tree<HierarchyNode>()
      .nodeSize([horizontalSpacing, verticalSpacing])
      .separation((a, b) => {
        // Ensure proper separation between nodes
        return a.parent === b.parent ? 1 : 1.2
      })

    // Apply layout
    const treeRoot = treeLayout(root)

    // Calculate bounds
    let minX = Infinity
    let maxX = -Infinity
    let maxY = -Infinity

    treeRoot.each((node) => {
      if (node.x < minX) minX = node.x
      if (node.x > maxX) maxX = node.x
      if (node.y > maxY) maxY = node.y
    })

    const width = maxX - minX
    const height = maxY

    treeLayouts.push({ root: treeRoot, width, height })
  })

  // Calculate total width needed
  const totalWidth = treeLayouts.reduce((sum, layout) => sum + layout.width, 0)
  const gaps = (treeLayouts.length - 1) * horizontalSpacing
  const totalWidthWithGaps = totalWidth + gaps

  // Position each tree side by side, centered
  let currentX = -totalWidthWithGaps / 2

  treeLayouts.forEach((layout, index) => {
    const { root, width } = layout

    // Find min X for this tree to normalize coordinates
    let minX = Infinity
    root.each((node: any) => {
      if (node.x < minX) minX = node.x
    })

    // Position all nodes in this tree
    root.each((node: any) => {
      const nodeData = node.data as HierarchyNode
      positions.set(nodeData.id, {
        x: currentX + (node.x - minX),
        y: node.y + 100, // Add top padding
      })
    })

    // Move to next tree position
    currentX += width + horizontalSpacing
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
      <Controls className="bg-card border-border" position="top-left">
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
