"use client"

import { useEffect, useCallback } from "react"
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
import type { AgentInstance } from "@/types"

const nodeTypes = {
  agent: AgentNode,
}

interface NetworkGraphProps {
  instances: AgentInstance[]
}

// Tree layout algorithm that respects parent-child structure
function calculateHierarchicalLayout(instances: AgentInstance[]): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>()
  const horizontalSpacing = 300
  const verticalSpacing = 200

  // Track next available X position at each level
  let nextXByLevel = new Map<number, number>()

  // Recursive function to layout a subtree
  const layoutSubtree = (instance: AgentInstance, level: number, startX: number): number => {
    // Get all children of this instance
    const children = instances.filter(i => i.parentId === instance.id)

    if (children.length === 0) {
      // Leaf node - position it at the next available X for this level
      const x = nextXByLevel.get(level) || startX
      positions.set(instance.id, { x, y: level * verticalSpacing + 100 })
      nextXByLevel.set(level, x + horizontalSpacing)
      return x
    }

    // Layout all children first
    const childPositions: number[] = []
    let currentX = nextXByLevel.get(level + 1) || startX

    children.forEach(child => {
      const childX = layoutSubtree(child, level + 1, currentX)
      childPositions.push(childX)
      currentX = nextXByLevel.get(level + 1) || currentX
    })

    // Position parent centered above children
    const leftmostChild = Math.min(...childPositions)
    const rightmostChild = Math.max(...childPositions)
    const parentX = (leftmostChild + rightmostChild) / 2

    positions.set(instance.id, { x: parentX, y: level * verticalSpacing + 100 })

    return parentX
  }

  // Find root nodes and layout each tree
  const rootNodes = instances.filter(i => !i.parentId)
  let currentRootX = 0

  rootNodes.forEach((root, index) => {
    if (index > 0) {
      // Add spacing between separate trees
      const maxX = nextXByLevel.get(0) || 0
      currentRootX = maxX + horizontalSpacing * 2
      // Reset X tracking for new tree
      nextXByLevel = new Map()
    }

    layoutSubtree(root, 0, currentRootX)
  })

  return positions
}

function NetworkGraphInner({ instances }: NetworkGraphProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const { fitView } = useReactFlow()

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
      fitView({ padding: 0.2, duration: 500 })
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

    const newEdges: Edge[] = instances
      .filter((instance) => instance.parentId)
      .map((instance) => ({
        id: `${instance.parentId}-${instance.id}`,
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

    setNodes(newNodes)
    setEdges(newEdges)
  }, [instances, setNodes, setEdges])

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={nodeTypes}
      fitView
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
        className="bg-card border border-border"
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

export function NetworkGraph({ instances }: NetworkGraphProps) {
  return (
    <div className="w-full h-full bg-background">
      <ReactFlowProvider>
        <NetworkGraphInner instances={instances} />
      </ReactFlowProvider>
    </div>
  )
}
