"use client"

import { DualPanelLogs } from "@/components/dual-panel-logs"
import { AnimatedBackground } from "@/components/animated-background"
import { ThemeToggleDropdown } from "@/components/theme-toggle"

export default function LogsPage() {
  return (
    <div className="relative min-h-screen w-full bg-transparent transition-colors duration-300">
      {/* Animated background with grid variant for logs page */}
      <AnimatedBackground variant="aurora" intensity="subtle" />

      {/* Fixed theme toggle in top right corner */}
      <div className="fixed top-4 right-4 z-50">
        <ThemeToggleDropdown />
      </div>

      {/* Main content */}
      <div className="relative z-10 h-screen w-full">
        <DualPanelLogs />
      </div>
    </div>
  )
}
