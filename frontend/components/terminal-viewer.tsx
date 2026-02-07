"use client"

import { useEffect, useState, useRef } from "react"
import { X, RefreshCw, Pause, Play, Terminal } from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

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
  const [isFocused, setIsFocused] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const fetchContent = async () => {
    try {
      const response = await fetch(
        `http://localhost:8001/instances/${instanceId}/terminal?lines=1000`
      )
      if (response.status === 404) {
        setContent("Instance not found — it may have been terminated.")
        setAutoRefresh(false)
        return
      }
      const data = await response.json()
      if (data.content) {
        setContent(data.content)
      }
    } catch {
      // Silently handle fetch failures (server may be restarting)
      if (!content) {
        setContent("Connecting to terminal...")
      }
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
      <div
        ref={containerRef}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        onMouseEnter={() => setIsFocused(true)}
        onMouseLeave={() => setIsFocused(false)}
        tabIndex={0}
        className={cn(
          "h-full flex flex-col rounded-lg overflow-hidden transition-all duration-300",
          // Glass morphism background
          "bg-black/80 backdrop-blur-xl",
          "border border-white/10",
          // Glow effect when focused/active
          isFocused && "ring-2 ring-cyan-500/30 shadow-[0_0_30px_rgba(6,182,212,0.15)]"
        )}
      >
        {/* Compact Header with gradient */}
        <div className="px-2 py-1.5 border-b border-white/10 flex items-center justify-end gap-1 flex-shrink-0 bg-gradient-to-r from-slate-800/90 via-slate-700/80 to-slate-800/90">
          <button
            onClick={(e) => {
              e.stopPropagation()
              setAutoScroll(!autoScroll)
            }}
            className={cn(
              "p-1 rounded transition-all duration-200",
              // Glass button effect
              "bg-white/5 hover:bg-white/10 backdrop-blur-sm",
              "border border-white/10 hover:border-white/20",
              autoScroll ? "text-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.3)]" : "text-gray-500"
            )}
            title={autoScroll ? "Auto-scroll ON" : "Auto-scroll OFF"}
          >
            {autoScroll ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              setAutoRefresh(!autoRefresh)
            }}
            className={cn(
              "p-1 rounded transition-all duration-200",
              "bg-white/5 hover:bg-white/10 backdrop-blur-sm",
              "border border-white/10 hover:border-white/20",
              autoRefresh ? "text-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.3)]" : "text-gray-500"
            )}
            title={autoRefresh ? "Auto-refresh ON" : "Auto-refresh OFF"}
          >
            <RefreshCw className={`h-3 w-3 ${autoRefresh ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              fetchContent()
            }}
            className={cn(
              "p-1 rounded transition-all duration-200",
              "bg-white/5 hover:bg-white/10 backdrop-blur-sm",
              "border border-white/10 hover:border-white/20",
              "text-gray-400 hover:text-gray-200"
            )}
            title="Refresh now"
          >
            <RefreshCw className="h-3 w-3" />
          </button>
        </div>
        {/* Terminal Content with smooth scrolling */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-auto scroll-smooth"
          style={{ scrollBehavior: 'smooth' }}
        >
          <div className="p-2">
            {isLoading ? (
              <div className="text-cyan-400/70 text-xs animate-pulse">Loading...</div>
            ) : (
              <pre className="text-[10px] font-mono whitespace-pre-wrap break-words leading-tight text-gray-50 [text-shadow:0_0_1px_rgba(255,255,255,0.1)]">
                {content}
              </pre>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      onFocus={() => setIsFocused(true)}
      onBlur={() => setIsFocused(false)}
      onMouseEnter={() => setIsFocused(true)}
      onMouseLeave={() => setIsFocused(false)}
      tabIndex={0}
      className={cn(
        "h-full flex flex-col rounded-xl overflow-hidden transition-all duration-300",
        // Glass morphism background
        "bg-black/70 backdrop-blur-2xl",
        "border border-white/10",
        "shadow-2xl",
        // Glow effect when focused/active
        isFocused && "ring-2 ring-cyan-500/40 shadow-[0_0_40px_rgba(6,182,212,0.2)]"
      )}
    >
      {/* Header with gradient */}
      <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between bg-gradient-to-r from-slate-900/95 via-slate-800/90 to-slate-900/95">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-cyan-400" />
            <h2 className="text-sm font-semibold text-white">Terminal: {instanceName}</h2>
          </div>
          <span className="text-xs text-cyan-400/70 font-mono bg-cyan-500/10 px-2 py-0.5 rounded-full border border-cyan-500/20">
            {instanceId.slice(0, 8)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={cn(
              "p-1.5 rounded-lg transition-all duration-200",
              // Glass button effect
              "bg-white/5 hover:bg-white/10 backdrop-blur-sm",
              "border border-white/10 hover:border-white/20",
              autoScroll ? "text-cyan-400 shadow-[0_0_10px_rgba(6,182,212,0.3)]" : "text-gray-500"
            )}
            title={autoScroll ? "Auto-scroll ON (click to pause)" : "Auto-scroll OFF (click to resume)"}
          >
            {autoScroll ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </button>
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={cn(
              "p-1.5 rounded-lg transition-all duration-200",
              "bg-white/5 hover:bg-white/10 backdrop-blur-sm",
              "border border-white/10 hover:border-white/20",
              autoRefresh ? "text-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.3)]" : "text-gray-500"
            )}
            title={autoRefresh ? "Auto-refresh ON" : "Auto-refresh OFF"}
          >
            <RefreshCw className={`h-4 w-4 ${autoRefresh ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={fetchContent}
            className={cn(
              "p-1.5 rounded-lg transition-all duration-200",
              "bg-white/5 hover:bg-white/10 backdrop-blur-sm",
              "border border-white/10 hover:border-white/20",
              "text-gray-400 hover:text-gray-200"
            )}
            title="Refresh now"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={onClose}
            className={cn(
              "p-1.5 rounded-lg transition-all duration-200",
              "bg-white/5 hover:bg-red-500/20 backdrop-blur-sm",
              "border border-white/10 hover:border-red-500/30",
              "text-gray-400 hover:text-red-400"
            )}
            title="Close terminal"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Terminal Content with glass effect */}
      <div className="flex-1 bg-black/50 overflow-hidden">
        <ScrollArea ref={scrollRef} className="h-full [&_[data-radix-scroll-area-viewport]]:scroll-smooth">
          <div className="p-4">
            {isLoading ? (
              <div className="text-cyan-400/70 text-sm animate-pulse">Loading terminal content...</div>
            ) : (
              <pre className="text-xs font-mono whitespace-pre-wrap break-words leading-relaxed text-gray-100 [text-shadow:0_0_1px_rgba(255,255,255,0.15)]">
                {content}
              </pre>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
