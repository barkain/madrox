"use client"

import { useEffect, useRef, useState } from "react"
import { useLogStore } from "@/store/log-store"
import type { LogWebSocketMessage, SystemLog, AuditLog } from "@/types"

const WS_URL = "ws://localhost:8001/ws/logs" // Adjust to match backend endpoint
const RECONNECT_DELAY = 3000

export function useLogWebSocket() {
  const [connectionStatus, setConnectionStatus] = useState<
    "connected" | "connecting" | "disconnected" | "error"
  >("connecting")

  const { addSystemLog, addAuditLog, systemPaused, auditPaused } = useLogStore()
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)

  useEffect(() => {
    const connect = () => {
      console.log("[DualPanelLogs] Connecting to WebSocket:", WS_URL)
      setConnectionStatus("connecting")

      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        console.log("[DualPanelLogs] WebSocket connected")
        setConnectionStatus("connected")
      }

      ws.onmessage = (event) => {
        try {
          const message: LogWebSocketMessage = JSON.parse(event.data)

          switch (message.type) {
            case "system_log": {
              // Add unique ID and store
              const systemLog: SystemLog = {
                id: `sys-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                ...message.data,
              }
              addSystemLog(systemLog)
              break
            }

            case "audit_log": {
              // Add unique ID and store
              const auditLog: AuditLog = {
                id: `audit-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                ...message.data,
              }
              addAuditLog(auditLog)
              break
            }

            default:
              console.warn("[DualPanelLogs] Unknown message type:", message)
          }
        } catch (error) {
          console.error("[DualPanelLogs] Error parsing WebSocket message:", error)
        }
      }

      ws.onerror = (error) => {
        console.error("[DualPanelLogs] WebSocket error:", error)
        setConnectionStatus("error")
      }

      ws.onclose = () => {
        console.log("[DualPanelLogs] WebSocket closed, reconnecting in", RECONNECT_DELAY, "ms")
        setConnectionStatus("disconnected")
        wsRef.current = null

        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect()
        }, RECONNECT_DELAY)
      }
    }

    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
      console.log("[DualPanelLogs] WebSocket connection closed")
    }
  }, [addSystemLog, addAuditLog])

  return {
    connectionStatus,
    systemPaused,
    auditPaused,
  }
}
