"use client"

import { useEffect, useCallback } from "react"
import {
  ReactFlow,
  ReactFlowProvider,
  type Node,
  type Edge,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  useReactFlow,
  MarkerType,
  ControlButton,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { RotateCcw, ZoomIn, ZoomOut, Maximize2 } from "lucide-react"
import { hierarchy, tree } from "d3-hierarchy"
import { useTheme } from "next-themes"
import { AgentNode } from "./agent-node"
import type { AgentInstance, MessageFlow } from "@/types"

const nodeTypes = {
  agent: AgentNode,
}

// Custom CSS for React Flow controls and minimap with glass morphism
const customStyles = `
  /* Glass morphism controls panel */
  .react-flow__controls {
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.1) 0%,
      rgba(255, 255, 255, 0.05) 100%
    ) !important;
    backdrop-filter: blur(20px) saturate(180%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
    border: 1px solid rgba(255, 255, 255, 0.18) !important;
    border-radius: 16px !important;
    box-shadow:
      0 8px 32px rgba(0, 0, 0, 0.12),
      0 0 0 1px rgba(var(--primary-rgb), 0.1),
      inset 0 1px 0 rgba(255, 255, 255, 0.1) !important;
    overflow: hidden !important;
    padding: 6px !important;
  }

  /* Dark mode overrides - FORCE visibility */
  .dark .react-flow__controls {
    background: rgba(30, 41, 59, 0.95) !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4) !important;
  }

  .dark .react-flow__controls-button {
    background: rgba(30, 41, 59, 0.9) !important;
    color: rgba(255, 255, 255, 0.95) !important;
    fill: rgba(255, 255, 255, 0.95) !important;
    border-color: rgba(255, 255, 255, 0.15) !important;
  }

  .dark .react-flow__controls-button:hover {
    background: rgba(51, 65, 85, 1) !important;
    color: white !important;
    fill: white !important;
  }

  .dark .react-flow__controls-button svg {
    fill: rgba(255, 255, 255, 0.95) !important;
    stroke: rgba(255, 255, 255, 0.95) !important;
  }

  .dark .react-flow__controls-button:hover svg {
    fill: white !important;
    stroke: white !important;
  }

  .react-flow__controls-button {
    background: transparent !important;
    border: none !important;
    border-radius: 10px !important;
    width: 36px !important;
    height: 36px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    color: rgba(30, 41, 59, 0.9) !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    position: relative !important;
  }

  .react-flow__controls-button::before {
    content: '' !important;
    position: absolute !important;
    inset: 0 !important;
    border-radius: 10px !important;
    background: linear-gradient(135deg, rgba(var(--primary-rgb), 0.2), rgba(var(--primary-rgb), 0.05)) !important;
    opacity: 0 !important;
    transition: opacity 0.25s ease !important;
  }

  .react-flow__controls-button:hover {
    color: hsl(var(--primary)) !important;
    transform: scale(1.08) translateY(-1px) !important;
    text-shadow: 0 0 12px rgba(var(--primary-rgb), 0.5) !important;
  }

  .react-flow__controls-button:hover::before {
    opacity: 1 !important;
  }

  .react-flow__controls-button:active {
    transform: scale(0.95) translateY(0) !important;
  }

  .react-flow__controls-button svg {
    width: 18px !important;
    height: 18px !important;
    fill: currentColor !important;
    position: relative !important;
    z-index: 1 !important;
  }

  /* Glass morphism minimap */
  .react-flow__minimap {
    background: linear-gradient(
      145deg,
      rgba(255, 255, 255, 0.12) 0%,
      rgba(255, 255, 255, 0.05) 100%
    ) !important;
    backdrop-filter: blur(24px) saturate(200%) !important;
    -webkit-backdrop-filter: blur(24px) saturate(200%) !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 16px !important;
    box-shadow:
      0 8px 32px rgba(0, 0, 0, 0.15),
      0 0 0 1px rgba(var(--primary-rgb), 0.1),
      inset 0 1px 0 rgba(255, 255, 255, 0.12) !important;
    overflow: hidden !important;
  }

  .dark .react-flow__minimap {
    background: linear-gradient(
      145deg,
      rgba(30, 30, 40, 0.85) 0%,
      rgba(15, 15, 25, 0.7) 100%
    ) !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    box-shadow:
      0 8px 32px rgba(0, 0, 0, 0.5),
      0 0 0 1px rgba(var(--primary-rgb), 0.12),
      inset 0 1px 0 rgba(255, 255, 255, 0.03) !important;
  }

  .react-flow__minimap-mask {
    fill: rgba(var(--primary-rgb), 0.12) !important;
    stroke: rgba(var(--primary-rgb), 0.4) !important;
    stroke-width: 1.5px !important;
    filter: drop-shadow(0 0 4px rgba(var(--primary-rgb), 0.3)) !important;
  }

  /* Edge animation for active connections */
  @keyframes edge-flow {
    0% {
      stroke-dashoffset: 24;
    }
    100% {
      stroke-dashoffset: 0;
    }
  }

  @keyframes edge-glow {
    0%, 100% {
      filter: drop-shadow(0 0 3px rgba(var(--primary-rgb), 0.4));
    }
    50% {
      filter: drop-shadow(0 0 8px rgba(var(--primary-rgb), 0.6));
    }
  }

  .react-flow__edge-path.animated {
    animation: edge-flow 1s linear infinite, edge-glow 2s ease-in-out infinite !important;
  }

  /* Gradient edge definitions and styling */
  .react-flow__edges {
    filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.15));
  }

  .react-flow__edge-path {
    stroke-linecap: round !important;
    stroke-linejoin: round !important;
  }

  /* Make React Flow transparent for aurora background */
  .react-flow__background {
    display: none !important;
  }

  .react-flow__pane {
    background: transparent !important;
  }

  .react-flow__viewport {
    background: transparent !important;
  }

  /* Panel background with gradient overlay */
  .react-flow__panel {
    transition: all 0.3s ease !important;
  }
`

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
          stroke: instance.status === "running" ? "#60a5fa" : "rgba(148, 163, 184, 0.6)",
          strokeWidth: 2.5,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: instance.status === "running" ? "#60a5fa" : "rgba(148, 163, 184, 0.6)",
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

    // Fit view after layout updates
    setTimeout(() => {
      fitView({ padding: 0.2, duration: 300, maxZoom: 0.6 })
    }, 100)
  }, [instances, messageFlows, setNodes, setEdges, fitView])

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
      minZoom={0.1}
      maxZoom={2}
      style={{ background: 'transparent' }}
    >
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
    <div className="w-full h-full bg-transparent">
      <style>{customStyles}</style>
      <ReactFlowProvider>
        <NetworkGraphInner instances={instances} messageFlows={messageFlows} onNodeClick={onNodeClick} />
      </ReactFlowProvider>
    </div>
  )
}
