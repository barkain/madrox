"use client"

import { getSmoothStepPath, type EdgeProps } from "@xyflow/react"

export function AnimatedMessageEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}: EdgeProps) {
  const [edgePath] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    borderRadius: 16,
  })

  const isActive = (data as any)?.active ?? false

  if (!isActive) {
    return (
      <path
        id={id}
        className="react-flow__edge-path"
        d={edgePath}
        style={{
          stroke: "#6b7280",
          strokeWidth: 2,
          strokeDasharray: "6,4",
          opacity: 0.4,
          fill: "none",
        }}
      />
    )
  }

  return (
    <g>
      {/* Base path - green line */}
      <path
        id={id}
        className="react-flow__edge-path"
        d={edgePath}
        style={{
          stroke: "#10b981",
          strokeWidth: 3,
          opacity: 0.8,
          fill: "none",
        }}
      />
      {/* Glow path */}
      <path
        d={edgePath}
        style={{
          stroke: "#10b981",
          strokeWidth: 10,
          opacity: 0.2,
          fill: "none",
          filter: "blur(4px)",
        }}
      />
      {/* Animated particle - outer glow */}
      <circle r="10" fill="#10b981" opacity="0.35">
        <animateMotion dur="1.5s" repeatCount="indefinite" path={edgePath} />
      </circle>
      {/* Animated particle - middle */}
      <circle r="7" fill="#10b981" opacity="0.7">
        <animateMotion dur="1.5s" repeatCount="indefinite" path={edgePath} />
      </circle>
      {/* Animated particle - bright core */}
      <circle r="4" fill="#34d399" opacity="1">
        <animateMotion dur="1.5s" repeatCount="indefinite" path={edgePath} />
      </circle>
    </g>
  )
}
