import { create } from "zustand"
import type { SystemLog, AuditLog, LogFilters } from "@/types"

interface LogStore {
  // System logs
  systemLogs: SystemLog[]
  systemFilters: LogFilters
  systemAutoScroll: boolean
  systemPaused: boolean

  // Audit logs
  auditLogs: AuditLog[]
  auditFilters: LogFilters
  auditAutoScroll: boolean
  auditPaused: boolean

  // System log actions
  addSystemLog: (log: SystemLog) => void
  clearSystemLogs: () => void
  setSystemFilters: (filters: Partial<LogFilters>) => void
  toggleSystemLevel: (level: string) => void
  setSystemSearch: (search: string) => void
  toggleSystemModule: (module: string) => void
  setSystemAutoScroll: (enabled: boolean) => void
  toggleSystemPause: () => void

  // Audit log actions
  addAuditLog: (log: AuditLog) => void
  clearAuditLogs: () => void
  setAuditFilters: (filters: Partial<LogFilters>) => void
  toggleAuditLevel: (level: string) => void
  setAuditSearch: (search: string) => void
  setAuditAutoScroll: (enabled: boolean) => void
  toggleAuditPause: () => void
}

const MAX_LOGS = 1000 // Keep last 1000 logs

export const useLogStore = create<LogStore>((set) => ({
  // Initial state
  systemLogs: [],
  systemFilters: {
    levels: new Set(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    search: "",
    modules: new Set(),
  },
  systemAutoScroll: true,
  systemPaused: false,

  auditLogs: [],
  auditFilters: {
    levels: new Set(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    search: "",
    modules: new Set(),
  },
  auditAutoScroll: true,
  auditPaused: false,

  // System log actions
  addSystemLog: (log) =>
    set((state) => {
      if (state.systemPaused) return state
      return {
        systemLogs: [log, ...state.systemLogs].slice(0, MAX_LOGS),
      }
    }),

  clearSystemLogs: () => set({ systemLogs: [] }),

  setSystemFilters: (filters) =>
    set((state) => ({
      systemFilters: { ...state.systemFilters, ...filters },
    })),

  toggleSystemLevel: (level) =>
    set((state) => {
      const newLevels = new Set(state.systemFilters.levels)
      if (newLevels.has(level)) {
        newLevels.delete(level)
      } else {
        newLevels.add(level)
      }
      return {
        systemFilters: { ...state.systemFilters, levels: newLevels },
      }
    }),

  setSystemSearch: (search) =>
    set((state) => ({
      systemFilters: { ...state.systemFilters, search },
    })),

  toggleSystemModule: (module) =>
    set((state) => {
      const newModules = new Set(state.systemFilters.modules)
      if (newModules.has(module)) {
        newModules.delete(module)
      } else {
        newModules.add(module)
      }
      return {
        systemFilters: { ...state.systemFilters, modules: newModules },
      }
    }),

  setSystemAutoScroll: (enabled) => set({ systemAutoScroll: enabled }),

  toggleSystemPause: () =>
    set((state) => ({ systemPaused: !state.systemPaused })),

  // Audit log actions
  addAuditLog: (log) =>
    set((state) => {
      if (state.auditPaused) return state
      return {
        auditLogs: [log, ...state.auditLogs].slice(0, MAX_LOGS),
      }
    }),

  clearAuditLogs: () => set({ auditLogs: [] }),

  setAuditFilters: (filters) =>
    set((state) => ({
      auditFilters: { ...state.auditFilters, ...filters },
    })),

  toggleAuditLevel: (level) =>
    set((state) => {
      const newLevels = new Set(state.auditFilters.levels)
      if (newLevels.has(level)) {
        newLevels.delete(level)
      } else {
        newLevels.add(level)
      }
      return {
        auditFilters: { ...state.auditFilters, levels: newLevels },
      }
    }),

  setAuditSearch: (search) =>
    set((state) => ({
      auditFilters: { ...state.auditFilters, search },
    })),

  setAuditAutoScroll: (enabled) => set({ auditAutoScroll: enabled }),

  toggleAuditPause: () =>
    set((state) => ({ auditPaused: !state.auditPaused })),
}))
