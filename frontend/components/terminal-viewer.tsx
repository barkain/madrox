"use client"

import { useEffect, useState, useRef } from "react"
import { X, RefreshCw, Pause, Play } from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"

interface TerminalViewerProps {
  instanceId: string
  instanceName: string
  onClose: () => void
  compact?: boolean
}

export function TerminalViewer({ instanceId, instanceName, onClose, compact = false }: TerminalViewerProps) {
  const [content, setContent] = useState<string>("")
  const [isLoading, setIsLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [autoScroll, setAutoScroll] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)

  const fetchContent = async () => {
    try {
      const response = await fetch("http://localhost:8001/mcp/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: Date.now(),
          method: "tools/call",
          params: {
            name: "get_tmux_pane_content",
            arguments: {
              instance_id: instanceId,
              lines: 1000, // Increased from 100 to 1000 for more scrollback history
            },
          },
        }),
      })

      const data = await response.json()
      if (data.result?.content?.[0]?.text) {
        setContent(data.result.content[0].text)
      }
    } catch (error) {
      console.error("Failed to fetch tmux content:", error)
      setContent("Error: Failed to fetch terminal content")
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchContent()

    if (autoRefresh) {
      const interval = setInterval(fetchContent, 1000) // Refresh every 1 second
      return () => clearInterval(interval)
    }
  }, [instanceId, autoRefresh])

  // Auto-scroll to bottom when content updates (only if autoScroll is enabled)
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      if (compact) {
        // For compact mode with plain div
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight
      } else {
        // For full mode with ScrollArea
        const scrollArea = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]')
        if (scrollArea) {
          scrollArea.scrollTop = scrollArea.scrollHeight
        }
      }
    }
  }, [content, autoScroll, compact])

  if (compact) {
    return (
      <div className="h-full bg-[#1e1e1e] flex flex-col">
        {/* Compact Header */}
        <div className="px-2 py-1 border-b border-border/30 flex items-center justify-end gap-1 bg-[#2d2d2d] flex-shrink-0">
          <button
            onClick={(e) => {
              e.stopPropagation()
              setAutoScroll(!autoScroll)
            }}
            className={`p-1 rounded hover:bg-muted/50 transition-colors ${
              autoScroll ? "text-blue-400" : "text-gray-500"
            }`}
            title={autoScroll ? "Auto-scroll ON" : "Auto-scroll OFF"}
          >
            {autoScroll ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              setAutoRefresh(!autoRefresh)
            }}
            className={`p-1 rounded hover:bg-muted/50 transition-colors ${
              autoRefresh ? "text-green-400" : "text-gray-500"
            }`}
            title={autoRefresh ? "Auto-refresh ON" : "Auto-refresh OFF"}
          >
            <RefreshCw className={`h-3 w-3 ${autoRefresh ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              fetchContent()
            }}
            className="p-1 rounded hover:bg-muted/50 transition-colors text-gray-400"
            title="Refresh now"
          >
            <RefreshCw className="h-3 w-3" />
          </button>
        </div>
        {/* Terminal Content */}
        <div ref={scrollRef} className="flex-1 overflow-auto">
          <div className="p-2">
            {isLoading ? (
              <div className="text-gray-400 text-xs">Loading...</div>
            ) : (
              <pre className="text-[10px] font-mono whitespace-pre-wrap break-words text-gray-100 leading-tight">
                {content}
              </pre>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full bg-card border border-border rounded-lg shadow-lg flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold">Terminal: {instanceName}</h2>
          <span className="text-xs text-muted-foreground font-mono">{instanceId.slice(0, 8)}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`p-1.5 rounded hover:bg-muted transition-colors ${
              autoScroll ? "text-blue-500" : "text-muted-foreground"
            }`}
            title={autoScroll ? "Auto-scroll ON (click to pause)" : "Auto-scroll OFF (click to resume)"}
          >
            {autoScroll ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </button>
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`p-1.5 rounded hover:bg-muted transition-colors ${
              autoRefresh ? "text-green-500" : "text-muted-foreground"
            }`}
            title={autoRefresh ? "Auto-refresh ON" : "Auto-refresh OFF"}
          >
            <RefreshCw className={`h-4 w-4 ${autoRefresh ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={fetchContent}
            className="p-1.5 rounded hover:bg-muted transition-colors text-muted-foreground"
            title="Refresh now"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-muted transition-colors text-muted-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Terminal Content */}
      <div className="flex-1 bg-[#1e1e1e] overflow-hidden">
        <ScrollArea ref={scrollRef} className="h-full">
          <div className="p-4">
            {isLoading ? (
              <div className="text-gray-400 text-sm">Loading terminal content...</div>
            ) : (
              <pre className="text-xs font-mono whitespace-pre-wrap break-words text-gray-100 leading-relaxed">
                {content}
              </pre>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
