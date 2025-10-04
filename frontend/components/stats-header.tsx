import { Activity, Coins, Zap } from "lucide-react"

interface StatsHeaderProps {
  stats: {
    activeInstances: number
    totalTokens: number
    totalCost: number
  }
}

export function StatsHeader({ stats }: StatsHeaderProps) {
  return (
    <div className="flex items-center gap-4">
      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 text-muted-foreground" />
        <div>
          <p className="text-xs text-muted-foreground">Active</p>
          <p className="text-lg font-semibold font-mono text-foreground">{stats.activeInstances}</p>
        </div>
      </div>

      <div className="h-8 w-px bg-border" />

      <div className="flex items-center gap-2">
        <Zap className="h-4 w-4 text-muted-foreground" />
        <div>
          <p className="text-xs text-muted-foreground">Tokens</p>
          <p className="text-lg font-semibold font-mono text-foreground">{stats.totalTokens.toLocaleString()}</p>
        </div>
      </div>

      <div className="h-8 w-px bg-border" />

      <div className="flex items-center gap-2">
        <Coins className="h-4 w-4 text-muted-foreground" />
        <div>
          <p className="text-xs text-muted-foreground">Cost</p>
          <p className="text-lg font-semibold font-mono text-foreground">${stats.totalCost.toFixed(4)}</p>
        </div>
      </div>
    </div>
  )
}
