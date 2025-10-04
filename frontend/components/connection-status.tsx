import { Wifi, WifiOff } from "lucide-react"

interface ConnectionStatusProps {
  status: "connected" | "connecting" | "disconnected" | "error"
}

export function ConnectionStatus({ status }: ConnectionStatusProps) {
  const statusConfig = {
    connected: {
      icon: Wifi,
      text: "Connected",
      color: "text-[var(--status-running)]",
      bg: "bg-[var(--status-running)]/10",
    },
    connecting: {
      icon: Wifi,
      text: "Connecting...",
      color: "text-[var(--status-pending)]",
      bg: "bg-[var(--status-pending)]/10",
    },
    disconnected: {
      icon: WifiOff,
      text: "Disconnected",
      color: "text-[var(--status-terminated)]",
      bg: "bg-[var(--status-terminated)]/10",
    },
    error: {
      icon: WifiOff,
      text: "Connection Error",
      color: "text-[var(--status-error)]",
      bg: "bg-[var(--status-error)]/10",
    },
  }

  const config = statusConfig[status]
  const Icon = config.icon

  return (
    <div className={`px-6 py-2 border-b border-border ${config.bg}`}>
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 ${config.color}`} />
        <span className={`text-sm font-medium ${config.color}`}>{config.text}</span>
      </div>
    </div>
  )
}
