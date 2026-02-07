"use client"

import { useEffect, useRef, useState } from "react"
import { useLogStore } from "@/store/log-store"
import type { LogWebSocketMessage, SystemLog, AuditLog } from "@/types"

const WS_URL = "ws://localhost:8001/ws/logs"
const RECONNECT_DELAY = 3000
const MAX_RECONNECT_DELAY = 30000

export function useLogWebSocket() {
  const [connectionStatus, setConnectionStatus] = useState<
    "connected" | "connecting" | "disconnected" | "error"
  >("disconnected")

  const { addSystemLog, addAuditLog, systemPaused, auditPaused } = useLogStore()
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
        console.log("[DualPanelLogs] WebSocket connected")
        setConnectionStatus("connected")
        reconnectDelayRef.current = RECONNECT_DELAY
      }

      ws.onmessage = (event) => {
        if (!mountedRef.current) return
        try {
          const message: LogWebSocketMessage = JSON.parse(event.data)

          switch (message.type) {
            case "system_log": {
              const systemLog: SystemLog = {
                id: `sys-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                ...message.data,
              }
              addSystemLog(systemLog)
              break
            }

            case "audit_log": {
              const auditLog: AuditLog = {
                id: `audit-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                ...message.data,
              }
              addAuditLog(auditLog)
              break
            }

            default:
              break
          }
        } catch {
          // Ignore malformed messages
        }
      }

      ws.onerror = () => {
        if (!mountedRef.current) return
        setConnectionStatus("error")
      }

      ws.onclose = () => {
        if (!mountedRef.current || intentionallyClosed) return
        wsRef.current = null
        setConnectionStatus("disconnected")

        const delay = reconnectDelayRef.current
        console.warn(`[DualPanelLogs] WebSocket disconnected, retrying in ${delay / 1000}s`)
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
  }, [addSystemLog, addAuditLog])

  return {
    connectionStatus,
    systemPaused,
    auditPaused,
  }
}
