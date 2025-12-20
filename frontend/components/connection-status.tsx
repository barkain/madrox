import { Wifi, WifiOff } from "lucide-react"

interface ConnectionStatusProps {
  status: "connected" | "connecting" | "disconnected" | "error"
}

export function ConnectionStatus({ status }: ConnectionStatusProps) {
  const statusConfig = {
    connected: {
      icon: Wifi,
      color: "text-green-500",
      title: "Connected",
    },
    connecting: {
      icon: Wifi,
      color: "text-yellow-500",
      title: "Connecting...",
    },
    disconnected: {
      icon: WifiOff,
      color: "text-red-500",
      title: "Disconnected",
    },
    error: {
      icon: WifiOff,
      color: "text-red-500",
      title: "Connection Error",
    },
  }

  const config = statusConfig[status]
  const Icon = config.icon

  return (
    <div className="absolute top-4 right-6 z-10 flex items-center gap-2">
      <Icon className={`h-4 w-4 ${config.color}`} />
      <span className={`text-sm font-medium ${config.color}`}>{config.title}</span>
    </div>
  )
}
