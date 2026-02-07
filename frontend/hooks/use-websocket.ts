"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { useInstanceStore } from "@/store/instance-store"
import type { AuditLogEntry } from "@/types"

const WS_URL = "ws://localhost:8001/ws/monitor"
const RECONNECT_DELAY = 3000
const MAX_RECONNECT_DELAY = 30000

interface WebSocketMessage {
  type: "initial_state" | "instance_update" | "audit_log"
  timestamp: string
  data: any
}

export function useWebSocket() {
  const [connectionStatus, setConnectionStatus] = useState<"connected" | "connecting" | "disconnected" | "error">(
    "disconnected",
  )
  const { instances, stats, setInstances, updateInstance } = useInstanceStore()
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const reconnectDelayRef = useRef(RECONNECT_DELAY)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    let intentionallyClosed = false

    const connect = () => {
      if (!mountedRef.current) return

      setConnectionStatus("connecting")

      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        if (!mountedRef.current) return
        console.log("[Madrox] WebSocket connected")
        setConnectionStatus("connected")
        reconnectDelayRef.current = RECONNECT_DELAY
      }

      ws.onmessage = (event) => {
        if (!mountedRef.current) return
        try {
          const message: WebSocketMessage = JSON.parse(event.data)

          switch (message.type) {
            case "initial_state":
              if (message.data.instances) {
                setInstances(message.data.instances)
              }
              break

            case "instance_update":
              if (message.data.instances) {
                setInstances(message.data.instances)
              }
              break

            case "audit_log":
              if (message.data.log) {
                setAuditLogs((prev) => [message.data.log, ...prev].slice(0, 100))
              }
              break
          }
        } catch {
          // Ignore malformed messages
        }
      }

      ws.onerror = () => {
        if (!mountedRef.current) return
        // onerror always fires before onclose; avoid noisy logging since
        // the browser Event object contains no actionable info.
        setConnectionStatus("error")
      }

      ws.onclose = () => {
        if (!mountedRef.current || intentionallyClosed) return
        wsRef.current = null
        setConnectionStatus("disconnected")

        const delay = reconnectDelayRef.current
        console.warn(`[Madrox] WebSocket disconnected, retrying in ${delay / 1000}s`)
        reconnectDelayRef.current = Math.min(delay * 1.5, MAX_RECONNECT_DELAY)

        reconnectTimeoutRef.current = window.setTimeout(connect, delay)
      }
    }

    connect()

    return () => {
      mountedRef.current = false
      intentionallyClosed = true
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [setInstances, updateInstance])

  return {
    connectionStatus,
    instances,
    auditLogs,
    stats,
  }
}
