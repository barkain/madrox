"use client"

import { useState, useEffect, useRef } from "react"
import { useInstanceStore } from "@/store/instance-store"
import type { AuditLogEntry } from "@/types"

const WS_URL = "ws://localhost:8001/ws/monitor"
const RECONNECT_DELAY = 3000

interface WebSocketMessage {
  type: "initial_state" | "instance_update" | "audit_log"
  timestamp: string
  data: any
}

export function useWebSocket() {
  const [connectionStatus, setConnectionStatus] = useState<"connected" | "connecting" | "disconnected" | "error">(
    "connecting",
  )
  const { instances, stats, setInstances, updateInstance } = useInstanceStore()
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)

  useEffect(() => {
    const connect = () => {
      console.log("[Madrox] Connecting to WebSocket:", WS_URL)
      setConnectionStatus("connecting")

      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        console.log("[Madrox] WebSocket connected")
        setConnectionStatus("connected")
      }

      ws.onmessage = (event) => {
        const message: WebSocketMessage = JSON.parse(event.data)
        console.log("[Madrox] Received message:", message.type, message.data)

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
      }

      ws.onerror = (error) => {
        console.error("[Madrox] WebSocket error:", error)
        setConnectionStatus("error")
      }

      ws.onclose = () => {
        console.log("[Madrox] WebSocket closed, reconnecting in", RECONNECT_DELAY, "ms")
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
      console.log("[Madrox] WebSocket connection closed")
    }
  }, [setInstances, updateInstance])

  return {
    connectionStatus,
    instances,
    auditLogs,
    stats,
  }
}
