"use client"

import { Search, X } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface LogFiltersProps {
  levels: Set<string>
  search: string
  onToggleLevel: (level: string) => void
  onSearchChange: (search: string) => void
  onClearSearch: () => void
}

const LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

const getLevelColor = (level: string, isActive: boolean) => {
  const baseClasses = "transition-all duration-200 border"

  if (!isActive) {
    return `${baseClasses} bg-slate-800/30 text-slate-600 border-slate-700/30 opacity-50`
  }

  switch (level) {
    case "DEBUG":
      return `${baseClasses} bg-slate-500/20 text-slate-300 border-slate-500/40 hover:bg-slate-500/30 hover:border-slate-500/50`
    case "INFO":
      return `${baseClasses} bg-blue-500/20 text-blue-300 border-blue-500/40 hover:bg-blue-500/30 hover:border-blue-500/50`
    case "WARNING":
      return `${baseClasses} bg-amber-500/20 text-amber-300 border-amber-500/40 hover:bg-amber-500/30 hover:border-amber-500/50`
    case "ERROR":
      return `${baseClasses} bg-rose-500/20 text-rose-300 border-rose-500/40 hover:bg-rose-500/30 hover:border-rose-500/50`
    case "CRITICAL":
      return `${baseClasses} bg-rose-600/30 text-rose-200 border-rose-500/50 hover:bg-rose-600/40 hover:border-rose-500/60 font-bold shadow-[0_0_8px_rgba(244,63,94,0.2)]`
    default:
      return `${baseClasses} bg-slate-500/20 text-slate-300 border-slate-500/40`
  }
}

export function LogFilters({
  levels,
  search,
  onToggleLevel,
  onSearchChange,
  onClearSearch,
}: LogFiltersProps) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 border-b border-white/10 bg-white/[0.02]">
      {/* Level filters */}
      <div className="flex gap-1.5">
        {LEVELS.map((level) => {
          const isActive = levels.has(level)
          return (
            <button
              key={level}
              onClick={() => onToggleLevel(level)}
              className={cn(
                "px-2.5 py-1 rounded-md text-[10px] font-semibold uppercase cursor-pointer select-none",
                getLevelColor(level, isActive),
              )}
              title={isActive ? `Hide ${level} logs` : `Show ${level} logs`}
            >
              {level}
            </button>
          )
        })}
      </div>

      {/* Search */}
      <div className="flex-1 relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
        <Input
          type="text"
          placeholder="Search logs..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-9 pr-9 h-8 text-xs bg-white/5 border-white/10 text-slate-200 placeholder:text-slate-500 focus:border-blue-500/50 focus:ring-blue-500/20 transition-all duration-200"
        />
        {search && (
          <button
            onClick={onClearSearch}
            className="absolute right-3 top-1/2 transform -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors duration-200"
            title="Clear search"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  )
}
