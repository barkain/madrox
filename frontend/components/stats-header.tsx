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
    <div className="flex items-center gap-6">
      <div className="flex items-center gap-3">
        <div className="p-1.5 rounded-md bg-primary/10">
          <Activity className="h-4 w-4 text-primary" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Active Instances</p>
          <p className="text-xl font-semibold font-mono text-foreground">{stats.activeInstances}</p>
        </div>
      </div>

      <div className="h-10 w-px bg-border/50" />

      <div className="flex items-center gap-3">
        <div className="p-1.5 rounded-md bg-primary/10">
          <Zap className="h-4 w-4 text-primary" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Total Tokens</p>
          <p className="text-xl font-semibold font-mono text-foreground">{stats.totalTokens.toLocaleString()}</p>
        </div>
      </div>

      <div className="h-10 w-px bg-border/50" />

      <div className="flex items-center gap-3">
        <div className="p-1.5 rounded-md bg-primary/10">
          <Coins className="h-4 w-4 text-primary" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Total Cost</p>
          <p className="text-xl font-semibold font-mono text-foreground">${stats.totalCost.toFixed(4)}</p>
        </div>
      </div>
    </div>
  )
}
