"use client"

import { Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

interface FilterBarProps {
  searchQuery: string
  onSearchChange: (query: string) => void
  statusFilter: string[]
  onStatusFilterChange: (filters: string[]) => void
  typeFilter: string[]
  onTypeFilterChange: (filters: string[]) => void
}

export function FilterBar({
  searchQuery,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  typeFilter,
  onTypeFilterChange,
}: FilterBarProps) {
  const toggleFilter = (filter: string, current: string[], onChange: (filters: string[]) => void) => {
    if (current.includes(filter)) {
      onChange(current.filter((f) => f !== filter))
    } else {
      onChange([...current, filter])
    }
  }

  return (
    <div className="px-6 py-3 border-t border-border bg-card/50">
      <div className="flex flex-col md:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search instances..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9 bg-background"
          />
        </div>

        <div className="flex flex-wrap gap-2">
          <div className="flex gap-1">
            {["running", "pending", "terminated", "error"].map((status) => (
              <Button
                key={status}
                variant={statusFilter.includes(status) ? "default" : "outline"}
                size="sm"
                onClick={() => toggleFilter(status, statusFilter, onStatusFilterChange)}
                className="capitalize"
              >
                {status}
              </Button>
            ))}
          </div>

          <div className="flex gap-1 border-l border-border pl-2">
            {["claude", "codex"].map((type) => (
              <Button
                key={type}
                variant={typeFilter.includes(type) ? "default" : "outline"}
                size="sm"
                onClick={() => toggleFilter(type, typeFilter, onTypeFilterChange)}
                className="capitalize"
              >
                {type}
              </Button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
