export interface AgentInstance {
  id: string
  name: string
  type: "claude" | "codex"
  status: "running" | "pending" | "terminated" | "error"
  role: string
  parentId: string | null
  createdAt: string
  lastActivity: string
  totalTokens: number
  totalCost: number
}

export interface AuditLogEntry {
  id: string
  timestamp: string
  type:
    | "instance_spawn"
    | "instance_created"
    | "instance_started"
    | "instance_terminated"
    | "instance_terminate"
    | "instance_error"
    | "instance_updated"
    | "message_exchange"
    | "message_sent"
    | "message_received"
    | "state_change"
    | "error"
    | "timeout"
  message: string
  metadata?: {
    from_instance?: string
    to_instance?: string
    message_id?: string
  }
}

export interface MessageFlow {
  id: string
  fromId: string
  toId: string
  timestamp: Date
  active: boolean
}

export interface Stats {
  activeInstances: number
  totalTokens: number
  totalCost: number
}

// System log types
export type SystemLogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"

export interface SystemLog {
  id: string
  timestamp: string // ISO 8601
  level: SystemLogLevel
  logger: string
  message: string
  module: string
  function: string
  line: number
}

// Audit log types (extended from existing)
export type AuditLogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"

export interface AuditLog {
  id: string
  timestamp: string // ISO 8601
  level: AuditLogLevel
  logger: string
  message: string
  action?: string
  metadata?: Record<string, any>
}

// WebSocket message types for dual-panel logging
export interface SystemLogMessage {
  type: "system_log"
  data: Omit<SystemLog, "id">
}

export interface AuditLogMessage {
  type: "audit_log"
  data: Omit<AuditLog, "id">
}

export type LogWebSocketMessage = SystemLogMessage | AuditLogMessage

// Log filter types
export interface LogFilters {
  levels: Set<string>
  search: string
  modules: Set<string>
}
