"use client"

import { Wifi, WifiOff, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface ConnectionStatusProps {
  status: "connected" | "connecting" | "disconnected" | "error"
}

export function ConnectionStatus({ status }: ConnectionStatusProps) {
  const statusConfig = {
    connected: {
      icon: Wifi,
      label: "Connected",
      dotColor: "bg-emerald-500",
      textColor: "text-emerald-400",
      glowClass: "glow-success",
      badgeClass: "border-emerald-500/30 bg-emerald-500/10",
      animate: false,
    },
    connecting: {
      icon: Loader2,
      label: "Connecting",
      dotColor: "bg-amber-500",
      textColor: "text-amber-400",
      glowClass: "",
      badgeClass: "border-amber-500/30 bg-amber-500/10",
      animate: true,
    },
    disconnected: {
      icon: WifiOff,
      label: "Disconnected",
      dotColor: "bg-red-500",
      textColor: "text-red-400",
      glowClass: "glow-error",
      badgeClass: "border-red-500/30 bg-red-500/10",
      animate: false,
    },
    error: {
      icon: WifiOff,
      label: "Error",
      dotColor: "bg-red-500",
      textColor: "text-red-400",
      glowClass: "glow-error",
      badgeClass: "border-red-500/30 bg-red-500/10",
      animate: false,
    },
  }

  const config = statusConfig[status]
  const Icon = config.icon

  return (
    <div
      className={cn(
        "absolute top-4 right-6 z-10",
        "glass rounded-full px-4 py-2",
        "flex items-center gap-3",
        "border transition-all duration-300 ease-out",
        "hover:scale-105",
        config.badgeClass,
        config.glowClass
      )}
    >
      {/* Status Dot with Pulse Animation */}
      <div className="relative flex items-center justify-center">
        {/* Pulse ring for connected/connecting states */}
        {(status === "connected" || status === "connecting") && (
          <span
            className={cn(
              "absolute inline-flex h-3 w-3 rounded-full opacity-75",
              config.dotColor,
              "animate-ping"
            )}
          />
        )}
        {/* Solid dot */}
        <span
          className={cn(
            "relative inline-flex h-2.5 w-2.5 rounded-full",
            config.dotColor,
            "transition-colors duration-300"
          )}
        />
      </div>

      {/* Icon */}
      <Icon
        className={cn(
          "h-4 w-4 transition-all duration-300",
          config.textColor,
          config.animate && "animate-spin"
        )}
      />

      {/* Label */}
      <span
        className={cn(
          "text-sm font-medium tracking-wide",
          "transition-colors duration-300",
          config.textColor
        )}
      >
        {config.label}
      </span>
    </div>
  )
}
