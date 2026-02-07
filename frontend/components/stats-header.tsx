import { Activity } from "lucide-react"

interface StatsHeaderProps {
  stats: {
    activeInstances: number
  }
}

export function StatsHeader({ stats }: StatsHeaderProps) {
  return (
    <div className="flex items-center gap-6">
      {/* Stats Card with Glass Morphism */}
      <div
        className="
          group
          flex items-center gap-4
          px-5 py-3.5
          rounded-xl
          glass
          border border-white/10 dark:border-white/5
          shadow-lg shadow-black/5 dark:shadow-black/20
          hover-lift
          hover:border-primary/20 dark:hover:border-primary/30
          hover:shadow-primary/5 dark:hover:shadow-primary/10
          transition-all duration-300 ease-out
        "
      >
        {/* Icon Container with Glow */}
        <div
          className="
            p-2.5
            rounded-lg
            bg-gradient-to-br from-primary/20 to-primary/5
            dark:from-primary/30 dark:to-primary/10
            group-hover:from-primary/30 group-hover:to-primary/10
            dark:group-hover:from-primary/40 dark:group-hover:to-primary/20
            transition-all duration-300
            shadow-inner shadow-primary/10
          "
        >
          <Activity
            className="
              h-5 w-5
              text-primary
              group-hover:scale-110
              transition-transform duration-300
            "
          />
        </div>

        {/* Text Content with Improved Typography */}
        <div className="flex flex-col">
          <p
            className="
              text-[10px]
              font-medium
              uppercase
              tracking-wider
              text-muted-foreground/70
              group-hover:text-muted-foreground
              transition-colors duration-300
            "
          >
            Active Instances
          </p>
          <p
            className="
              text-2xl
              font-bold
              font-mono
              gradient-text-primary
              tracking-tight
              leading-none
              mt-0.5
            "
          >
            {stats.activeInstances}
          </p>
        </div>
      </div>
    </div>
  )
}
