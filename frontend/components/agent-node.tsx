import { memo } from "react"
import { Handle, Position } from "@xyflow/react"
import { Activity, Clock, Zap, Coins } from "lucide-react"
import type { AgentInstance } from "@/types"

interface AgentNodeProps {
  data: AgentInstance
}

export const AgentNode = memo(({ data }: AgentNodeProps) => {
  const statusColors = {
    running: "border-[var(--status-running)] bg-[var(--status-running)]/10",
    pending: "border-[var(--status-pending)] bg-[var(--status-pending)]/10",
    error: "border-[var(--status-error)] bg-[var(--status-error)]/10",
    terminated: "border-[var(--status-terminated)] bg-[var(--status-terminated)]/10",
  }

  const statusDotColors = {
    running: "bg-[var(--status-running)]",
    pending: "bg-[var(--status-pending)]",
    error: "bg-[var(--status-error)]",
    terminated: "bg-[var(--status-terminated)]",
  }

  // Different background colors for Claude vs Codex
  const instanceTypeBackground = {
    claude: "bg-gray-50 dark:bg-gray-900/50",
    codex: "bg-gray-200 dark:bg-gray-800/80",
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
    <div className={`px-4 py-3 rounded-lg border-2 min-w-[240px] ${instanceTypeBackground[data.type]} ${statusColors[data.status]}`}>
      <Handle type="target" position={Position.Top} className="w-3 h-3" />

      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <div className={`w-2 h-2 rounded-full ${statusDotColors[data.status]}`} />
            <span className="text-xs font-medium text-muted-foreground uppercase">{data.type}</span>
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
