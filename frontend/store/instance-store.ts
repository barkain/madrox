import { create } from "zustand"
import type { AgentInstance, AuditLogEntry, Stats } from "@/types"

interface InstanceStore {
  instances: AgentInstance[]
  auditLogs: AuditLogEntry[]
  stats: Stats
  setInstances: (instances: AgentInstance[]) => void
  addInstance: (instance: AgentInstance) => void
  updateInstance: (id: string, updates: Partial<AgentInstance>) => void
  removeInstance: (id: string) => void
  addAuditLog: (log: AuditLogEntry) => void
  clearAuditLogs: () => void
  setStats: (stats: Stats) => void
}

export const useInstanceStore = create<InstanceStore>((set) => ({
  instances: [],
  auditLogs: [],
  stats: {
    activeInstances: 0,
    totalTokens: 0,
    totalCost: 0,
  },
  setInstances: (instances) =>
    set(() => {
      // Backend already filters out terminated instances, so count all received instances
      const activeCount = instances.length
      const totalTokens = instances.reduce((sum, i) => sum + i.totalTokens, 0)
      const totalCost = instances.reduce((sum, i) => sum + i.totalCost, 0)

      return {
        instances,
        stats: {
          activeInstances: activeCount,
          totalTokens,
          totalCost,
        },
      }
    }),
  addInstance: (instance) =>
    set((state) => {
      const instances = [...state.instances, instance]
      const activeCount = instances.length
      const totalTokens = instances.reduce((sum, i) => sum + i.totalTokens, 0)
      const totalCost = instances.reduce((sum, i) => sum + i.totalCost, 0)

      return {
        instances,
        stats: {
          activeInstances: activeCount,
          totalTokens,
          totalCost,
        },
      }
    }),
  updateInstance: (id, updates) =>
    set((state) => {
      const instances = state.instances.map((i) => (i.id === id ? { ...i, ...updates } : i))
      const activeCount = instances.length
      const totalTokens = instances.reduce((sum, i) => sum + i.totalTokens, 0)
      const totalCost = instances.reduce((sum, i) => sum + i.totalCost, 0)

      return {
        instances,
        stats: {
          activeInstances: activeCount,
          totalTokens,
          totalCost,
        },
      }
    }),
  removeInstance: (id) =>
    set((state) => {
      const instances = state.instances.filter((i) => i.id !== id)
      const activeCount = instances.length
      const totalTokens = instances.reduce((sum, i) => sum + i.totalTokens, 0)
      const totalCost = instances.reduce((sum, i) => sum + i.totalCost, 0)

      return {
        instances,
        stats: {
          activeInstances: activeCount,
          totalTokens,
          totalCost,
        },
      }
    }),
  addAuditLog: (log) =>
    set((state) => ({
      auditLogs: [log, ...state.auditLogs].slice(0, 100), // Keep last 100 logs
    })),
  clearAuditLogs: () => set({ auditLogs: [] }),
  setStats: (stats) => set({ stats }),
}))
