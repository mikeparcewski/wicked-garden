import { useEffect, useRef } from 'react'
import { usePluginStore } from '../stores/pluginStore'
import type { CommandsResponse } from '../types/plugin'

export function usePlugins() {
  const store = usePluginStore()
  const retryRef = useRef<number>()

  useEffect(() => {
    fetchCommands()
    return () => clearTimeout(retryRef.current)
  }, [])

  async function fetchCommands() {
    try {
      store.setLoading(true)
      const res = await fetch('/acp/commands')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: CommandsResponse = await res.json()

      if (data.count > 0) {
        store.setGrouped(data.grouped, data.count)

        if (!store.activePlugin) {
          const names = Object.keys(data.grouped).filter(n => n.startsWith('wicked-')).sort()
          if (names.length > 0) store.setActivePlugin(names[0])
        }
      } else {
        // Commands not yet discovered — the WebSocket available_commands_update
        // handler will populate them. Just clear loading so the UI shows.
        store.setLoading(false)
      }
    } catch (e) {
      store.setError(e instanceof Error ? e.message : 'Failed to load commands')
    }
  }

  return {
    loading: store.loading,
    error: store.error,
  }
}
