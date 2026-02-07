"use client"

import { Search } from "lucide-react"
import { Input } from "@/components/ui/input"

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
}: FilterBarProps) {
  return (
    <div className="relative w-52">
      <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/60" />
      <Input
        placeholder="Search instances..."
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
        className="pl-8 h-8 text-xs bg-background/50 border-border/40 placeholder:text-muted-foreground/40"
      />
    </div>
  )
}
