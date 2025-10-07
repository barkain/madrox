import { memo } from "react"
import { Handle, Position } from "@xyflow/react"
import { Activity, Clock, Zap, Coins } from "lucide-react"
import type { AgentInstance } from "@/types"

interface AgentNodeProps {
  data: AgentInstance
}

export const AgentNode = memo(({ data }: AgentNodeProps) => {
  // Status-based color scheme (primary indicator)
  const statusColors = {
    running: "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950/30",
    idle: "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950/30",
    busy: "border-blue-300 bg-blue-50 dark:border-blue-700 dark:bg-blue-950/30",
    initializing: "border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/30",
    pending: "border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/30",
    error: "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950/30",
    terminated: "border-gray-300 bg-gray-50 dark:border-gray-700 dark:bg-gray-900/30",
  }

  const statusDotColors = {
    running: "bg-green-500",
    idle: "bg-green-500",
    busy: "bg-blue-500 animate-pulse",
    initializing: "bg-amber-500 animate-pulse",
    pending: "bg-amber-500",
    error: "bg-red-500",
    terminated: "bg-gray-400",
  }

  // Type-based accent colors (secondary indicator)
  const instanceTypeTextColor = {
    claude: "text-blue-600 dark:text-blue-400",
    codex: "text-purple-600 dark:text-purple-400",
  }

  const calculateUptime = () => {
    if (!data.createdAt) return "0m"
    const now = new Date()
    const created = new Date(data.createdAt)
    const diffMs = now.getTime() - created.getTime()
    const diffMins = Math.floor(diffMs / 60000)

    if (diffMins < 60) return `${diffMins}m`
    const hours = Math.floor(diffMins / 60)
    if (hours < 24) return `${hours}h`
    const days = Math.floor(hours / 24)
    return `${days}d`
  }

  return (
    <div className={`px-4 py-3 rounded-lg border-2 min-w-[240px] ${statusColors[data.status]}`}>
      <Handle type="target" position={Position.Top} className="w-3 h-3" />

      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <div className={`w-2 h-2 rounded-full ${statusDotColors[data.status]}`} />
            <span className={`text-xs font-medium uppercase ${instanceTypeTextColor[data.type]}`}>{data.type}</span>
          </div>
          <h3 className="font-mono text-sm font-semibold text-foreground truncate">{data.name || data.id}</h3>
          {data.role && <p className="text-xs text-muted-foreground truncate">{data.role}</p>}
        </div>
        <Activity className="h-4 w-4 text-primary flex-shrink-0" />
      </div>

      <div className="space-y-1.5 text-xs">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground flex items-center gap-1">
            <Clock className="h-3 w-3" />
            Uptime
          </span>
          <span className="font-mono text-foreground">{calculateUptime()}</span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-muted-foreground flex items-center gap-1">
            <Zap className="h-3 w-3" />
            Tokens
          </span>
          <span className="font-mono text-foreground">{data.totalTokens?.toLocaleString() || 0}</span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-muted-foreground flex items-center gap-1">
            <Coins className="h-3 w-3" />
            Cost
          </span>
          <span className="font-mono text-foreground">${data.totalCost?.toFixed(4) || "0.0000"}</span>
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="w-3 h-3" />
    </div>
  )
})

AgentNode.displayName = "AgentNode"
