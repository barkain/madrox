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

// Hierarchical tree layout algorithm
function calculateHierarchicalLayout(instances: AgentInstance[]): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>()
  const levelMap = new Map<string, number>()

  // Calculate depth levels for each instance
  const calculateLevel = (instance: AgentInstance, level = 0): void => {
    const currentLevel = levelMap.get(instance.id) || 0
    if (level > currentLevel) {
      levelMap.set(instance.id, level)
    }

    const children = instances.filter(i => i.parentId === instance.id)
    children.forEach(child => calculateLevel(child, level + 1))
  }

  // Start from root nodes (no parent)
  const rootNodes = instances.filter(i => !i.parentId)
  rootNodes.forEach(root => calculateLevel(root, 0))

  // Group instances by level
  const levelGroups = new Map<number, AgentInstance[]>()
  instances.forEach(instance => {
    const level = levelMap.get(instance.id) || 0
    if (!levelGroups.has(level)) {
      levelGroups.set(level, [])
    }
    levelGroups.get(level)!.push(instance)
  })

  // Position nodes in each level
  const horizontalSpacing = 300
  const verticalSpacing = 200
  const startY = 100

  levelGroups.forEach((levelInstances, level) => {
    const totalWidth = (levelInstances.length - 1) * horizontalSpacing
    const startX = -totalWidth / 2

    levelInstances.forEach((instance, index) => {
      positions.set(instance.id, {
        x: startX + index * horizontalSpacing,
        y: startY + level * verticalSpacing,
      })
    })
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
