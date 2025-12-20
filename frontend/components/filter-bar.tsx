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
    <div className="relative flex-1 max-w-md">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
      <Input
        placeholder="Search instances..."
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
        className="pl-9 bg-background"
      />
    </div>
  )
}
