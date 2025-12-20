import { Activity } from "lucide-react"

interface StatsHeaderProps {
  stats: {
    activeInstances: number
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
    </div>
  )
}
