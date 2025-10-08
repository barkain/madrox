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
  const baseClasses = "transition-all duration-200"

  if (!isActive) {
    return `${baseClasses} bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-600 opacity-50`
  }

  switch (level) {
    case "DEBUG":
      return `${baseClasses} bg-gray-200 text-gray-800 dark:bg-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-600`
    case "INFO":
      return `${baseClasses} bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-800`
    case "WARNING":
      return `${baseClasses} bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300 hover:bg-yellow-200 dark:hover:bg-yellow-800`
    case "ERROR":
      return `${baseClasses} bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-800`
    case "CRITICAL":
      return `${baseClasses} bg-red-200 text-red-900 dark:bg-red-800 dark:text-red-100 hover:bg-red-300 dark:hover:bg-red-700 font-bold`
    default:
      return `${baseClasses} bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300`
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
    <div className="flex items-center gap-3 px-3 py-2 border-b border-border bg-card/30">
      {/* Level filters */}
      <div className="flex gap-1.5">
        {LEVELS.map((level) => {
          const isActive = levels.has(level)
          return (
            <button
              key={level}
              onClick={() => onToggleLevel(level)}
              className={cn(
                "px-2.5 py-1 rounded text-[10px] font-semibold uppercase cursor-pointer select-none",
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
        <Search className="absolute left-2.5 top-1/2 transform -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Search logs..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-8 pr-8 h-8 text-xs"
        />
        {search && (
          <button
            onClick={onClearSearch}
            className="absolute right-2.5 top-1/2 transform -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            title="Clear search"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  )
}
