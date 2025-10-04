"use client"

import { useEffect } from "react"
import {
  ReactFlow,
  type Node,
  type Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { AgentNode } from "./agent-node"
import type { AgentInstance } from "@/types"

const nodeTypes = {
  agent: AgentNode,
}

interface NetworkGraphProps {
  instances: AgentInstance[]
}

export function NetworkGraph({ instances }: NetworkGraphProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  // Convert instances to React Flow nodes and edges
  useEffect(() => {
    const newNodes: Node[] = instances.map((instance, index) => ({
      id: instance.id,
      type: "agent",
      position: {
        x: (index % 4) * 300 + 100,
        y: Math.floor(index / 4) * 200 + 100,
      },
      data: instance,
    }))

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
    <div className="w-full h-full bg-background">
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
        <Controls className="bg-card border-border" />
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
    </div>
  )
}
