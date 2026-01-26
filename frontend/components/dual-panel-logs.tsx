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
        return <Wifi className="h-4 w-4 text-emerald-400 drop-shadow-[0_0_6px_rgba(16,185,129,0.6)]" />
      case "connecting":
        return <Loader2 className="h-4 w-4 text-amber-400 animate-spin drop-shadow-[0_0_6px_rgba(251,191,36,0.6)]" />
      case "disconnected":
      case "error":
        return <WifiOff className="h-4 w-4 text-rose-400 drop-shadow-[0_0_6px_rgba(251,113,133,0.6)]" />
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
        return "text-emerald-400"
      case "connecting":
        return "text-amber-400"
      case "disconnected":
      case "error":
        return "text-rose-400"
    }
  }

  return (
    <div className="flex flex-col h-full w-full bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Connection Status Bar - Glass morphism */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-white/10 backdrop-blur-xl bg-white/5 shadow-lg shadow-black/10">
        <h1 className="text-lg font-bold bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
          Dual-Panel Logging System
        </h1>
        <div className={cn(
          "flex items-center gap-2 text-sm px-3 py-1.5 rounded-full backdrop-blur-sm bg-white/5 border border-white/10",
          getConnectionColor()
        )}>
          {getConnectionIcon()}
          <span className="font-medium">{getConnectionText()}</span>
        </div>
      </div>

      {/* Dual Panel Layout */}
      <div className="flex-1 p-4">
        <PanelGroup direction="horizontal" className="h-full gap-0">
          {/* System Logs Panel */}
          <Panel defaultSize={50} minSize={30}>
            <LogPanel type="system" />
          </Panel>

          {/* Resize Handle - Enhanced with glow effect */}
          <PanelResizeHandle className="w-3 mx-1 transition-all duration-300 flex items-center justify-center group relative">
            {/* Glow effect on hover */}
            <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-gradient-to-b from-transparent via-blue-500/20 to-transparent blur-sm" />
            {/* Handle bar */}
            <div className="relative w-1 h-16 rounded-full bg-white/10 group-hover:bg-gradient-to-b group-hover:from-blue-400 group-hover:via-purple-400 group-hover:to-blue-400 transition-all duration-300 group-hover:shadow-[0_0_12px_rgba(147,197,253,0.5)] group-hover:h-24" />
            {/* Grip dots */}
            <div className="absolute flex flex-col gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
              <div className="w-1 h-1 rounded-full bg-blue-300/60" />
              <div className="w-1 h-1 rounded-full bg-purple-300/60" />
              <div className="w-1 h-1 rounded-full bg-blue-300/60" />
            </div>
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
