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
  type: "instance_created" | "instance_started" | "instance_terminated" | "instance_error" | "instance_updated"
  message: string
}

export interface Stats {
  activeInstances: number
  totalTokens: number
  totalCost: number
}
