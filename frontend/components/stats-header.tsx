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
    <div className="px-6 py-4 border-t border-border">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10">
            <Activity className="h-5 w-5 text-primary" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Active Instances</p>
            <p className="text-2xl font-semibold font-mono text-foreground">{stats.activeInstances}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10">
            <Zap className="h-5 w-5 text-primary" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Total Tokens</p>
            <p className="text-2xl font-semibold font-mono text-foreground">{stats.totalTokens.toLocaleString()}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10">
            <Coins className="h-5 w-5 text-primary" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Total Cost</p>
            <p className="text-2xl font-semibold font-mono text-foreground">${stats.totalCost.toFixed(4)}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
