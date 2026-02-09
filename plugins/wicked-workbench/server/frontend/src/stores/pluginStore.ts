import { create } from 'zustand'
import type { AgentCommand } from '../types/plugin'

interface PluginState {
  /** Plugin name → commands mapping from ACP agent */
  grouped: Record<string, AgentCommand[]>
  /** Total command count */
  commandCount: number
  /** Currently selected plugin group */
  activePlugin: string | null
  /** Currently selected command within the plugin */
  activeCommand: string | null
  loading: boolean
  error: string | null

  setGrouped: (grouped: Record<string, AgentCommand[]>, count: number) => void
  setActivePlugin: (name: string | null) => void
  setActiveCommand: (cmd: string | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  getActiveCommands: () => AgentCommand[]
  getPluginNames: () => string[]
}

/** Wicked-* plugins that should appear at the top of the sidebar */
const PLUGIN_PREFIX = 'wicked-'

export const usePluginStore = create<PluginState>((set, get) => ({
  grouped: {},
  commandCount: 0,
  activePlugin: null,
  activeCommand: null,
  loading: true,
  error: null,

  setGrouped: (grouped, count) => set({ grouped, commandCount: count, loading: false }),

  setActivePlugin: (name) => {
    set({ activePlugin: name, activeCommand: null })
  },

  setActiveCommand: (cmd) => set({ activeCommand: cmd }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error, loading: false }),

  getActiveCommands: () => {
    const { grouped, activePlugin } = get()
    if (!activePlugin) return []
    return grouped[activePlugin] ?? []
  },

  getPluginNames: () => {
    const { grouped } = get()
    const names = Object.keys(grouped).filter(n => n !== '_project')
    // Sort: wicked-* plugins first (alphabetical), then others
    return names.sort((a, b) => {
      const aW = a.startsWith(PLUGIN_PREFIX)
      const bW = b.startsWith(PLUGIN_PREFIX)
      if (aW && !bW) return -1
      if (!aW && bW) return 1
      return a.localeCompare(b)
    })
  },
}))
