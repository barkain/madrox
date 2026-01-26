import { memo } from "react"
import { Handle, Position } from "@xyflow/react"
import { Activity, Clock, Zap, AlertCircle, Loader2 } from "lucide-react"
import type { AgentInstance } from "@/types"

interface AgentNodeProps {
  data: AgentInstance
}

export const AgentNode = memo(({ data }: AgentNodeProps) => {
  const statusGlow = {
    running: "glow-success",
    idle: "glow-primary",
    busy: "glow-primary-intense animate-glow-pulse",
    initializing: "glow-warning",
    pending: "",
    error: "glow-error",
    terminated: "",
  }

  const statusDotColors = {
    running: "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]",
    idle: "bg-green-500/80",
    busy: "bg-blue-500 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.6)]",
    initializing: "bg-amber-500 animate-pulse shadow-[0_0_8px_rgba(245,158,11,0.6)]",
    pending: "bg-amber-500/70",
    error: "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]",
    terminated: "bg-gray-400 dark:bg-gray-600",
  }

  const StatusIcon = () => {
    switch (data.status) {
      case "running":
      case "busy":
        return <Zap className="h-3.5 w-3.5 text-green-500 dark:text-green-400" />
      case "initializing":
        return <Loader2 className="h-3.5 w-3.5 text-amber-500 animate-spin" />
      case "error":
        return <AlertCircle className="h-3.5 w-3.5 text-red-500 dark:text-red-400" />
      default:
        return <Activity className="h-3.5 w-3.5 text-muted-foreground" />
    }
  }

  const instanceTypeGradient = {
    claude: "bg-gradient-to-r from-blue-500 to-indigo-500 dark:from-blue-400 dark:to-indigo-400 bg-clip-text text-transparent",
    codex: "bg-gradient-to-r from-purple-500 to-pink-500 dark:from-purple-400 dark:to-pink-400 bg-clip-text text-transparent",
  }

  const borderGradient = {
    claude: "from-blue-500/50 via-indigo-500/50 to-blue-500/50",
    codex: "from-purple-500/50 via-pink-500/50 to-purple-500/50",
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
    <div className={`p-[1px] rounded-xl bg-gradient-to-br ${borderGradient[data.type]} hover-lift transition-all-smooth`}>
      <div className={`relative px-5 py-4 rounded-xl min-w-[260px] glass-subtle dark:glass transition-theme ${statusGlow[data.status]}`}>
        <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-white/5 to-transparent pointer-events-none" />
        <Handle type="target" position={Position.Top} className="!w-3 !h-3 !bg-primary/80 !border-2 !border-background transition-all-smooth hover:!scale-125" />
        <div className="relative flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <div className={`w-2.5 h-2.5 rounded-full ${statusDotColors[data.status]} transition-all-smooth`} />
              <span className={`text-[10px] font-bold uppercase tracking-wider ${instanceTypeGradient[data.type]}`}>{data.type}</span>
              <span className="text-[10px] text-muted-foreground/60 capitalize">{data.status}</span>
            </div>
            <h3 className="font-mono text-sm font-bold text-foreground truncate mb-0.5 tracking-tight">{data.name || data.id}</h3>
            <p className="text-[11px] text-muted-foreground/50 font-mono tracking-wide">{data.id.slice(0, 12)}...</p>
            {data.role && (
              <span className="inline-block mt-1.5 px-2 py-0.5 text-[10px] font-medium rounded-full bg-primary/10 text-primary/80 dark:bg-primary/20 dark:text-primary/90 truncate max-w-full">{data.role}</span>
            )}
          </div>
          <div className="flex-shrink-0 p-1.5 rounded-lg bg-primary/5 dark:bg-primary/10"><StatusIcon /></div>
        </div>
        <div className="relative pt-3 border-t border-border/30 dark:border-border/20">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground/70 flex items-center gap-1.5"><Clock className="h-3 w-3" /><span className="text-[11px]">Uptime</span></span>
            <span className="font-mono font-semibold text-foreground/90 tabular-nums">{calculateUptime()}</span>
          </div>
        </div>
        <Handle type="source" position={Position.Bottom} className="!w-3 !h-3 !bg-primary/80 !border-2 !border-background transition-all-smooth hover:!scale-125" />
      </div>
    </div>
  )
})

AgentNode.displayName = "AgentNode"
