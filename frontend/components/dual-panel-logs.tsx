"use client"

import { useEffect } from "react"
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels"
import { LogPanel } from "@/components/log-panel"
import { useLogWebSocket } from "@/hooks/use-log-websocket"
import { Wifi, WifiOff, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

export function DualPanelLogs() {
  const { connectionStatus } = useLogWebSocket()

  const getConnectionIcon = () => {
    switch (connectionStatus) {
      case "connected":
        return <Wifi className="h-4 w-4 text-green-500" />
      case "connecting":
        return <Loader2 className="h-4 w-4 text-yellow-500 animate-spin" />
      case "disconnected":
      case "error":
        return <WifiOff className="h-4 w-4 text-red-500" />
    }
  }

  const getConnectionText = () => {
    switch (connectionStatus) {
      case "connected":
        return "Connected"
      case "connecting":
        return "Connecting..."
      case "disconnected":
        return "Disconnected"
      case "error":
        return "Connection Error"
    }
  }

  const getConnectionColor = () => {
    switch (connectionStatus) {
      case "connected":
        return "text-green-600 dark:text-green-400"
      case "connecting":
        return "text-yellow-600 dark:text-yellow-400"
      case "disconnected":
      case "error":
        return "text-red-600 dark:text-red-400"
    }
  }

  return (
    <div className="flex flex-col h-full w-full">
      {/* Connection Status Bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-card/50">
        <h1 className="text-lg font-bold text-foreground">Dual-Panel Logging System</h1>
        <div className={cn("flex items-center gap-2 text-sm", getConnectionColor())}>
          {getConnectionIcon()}
          <span className="font-medium">{getConnectionText()}</span>
        </div>
      </div>

      {/* Dual Panel Layout */}
      <div className="flex-1 p-4">
        <PanelGroup direction="horizontal" className="h-full">
          {/* System Logs Panel */}
          <Panel defaultSize={50} minSize={30}>
            <LogPanel type="system" />
          </Panel>

          {/* Resize Handle */}
          <PanelResizeHandle className="w-2 hover:bg-blue-500/20 transition-colors flex items-center justify-center group">
            <div className="w-1 h-8 bg-border rounded-full group-hover:bg-blue-500 transition-colors" />
          </PanelResizeHandle>

          {/* Audit Logs Panel */}
          <Panel defaultSize={50} minSize={30}>
            <LogPanel type="audit" />
          </Panel>
        </PanelGroup>
      </div>
    </div>
  )
}
