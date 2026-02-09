import { useCallback, useEffect, useRef } from 'react'
import { useACPStore, createMessageId } from '../stores/acpStore'
import { usePluginStore } from '../stores/pluginStore'
import type { ClientMessage, ServerMessage, SessionUpdate } from '../types/acp'

const WS_URL = `ws://${window.location.hostname}:${window.location.port || '18889'}/acp/ws`
const RECONNECT_BASE_DELAY = 1000
const RECONNECT_MAX_DELAY = 30000
const MAX_RECONNECT_ATTEMPTS = 20

export function useACP() {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<number>()
  const reconnectAttempts = useRef(0)
  const store = useACPStore()

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) {
      console.warn('[ACP] Max reconnect attempts reached')
      return
    }

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      store.setConnected(true)
      reconnectAttempts.current = 0
      console.log('[ACP] Connected')
    }

    ws.onclose = () => {
      store.setConnected(false)
      store.setSessionId(null)
      reconnectAttempts.current++

      const delay = Math.min(
        RECONNECT_BASE_DELAY * Math.pow(2, reconnectAttempts.current - 1) + Math.random() * 1000,
        RECONNECT_MAX_DELAY
      )
      console.log(`[ACP] Disconnected, reconnecting in ${Math.round(delay)}ms (attempt ${reconnectAttempts.current}/${MAX_RECONNECT_ATTEMPTS})`)
      reconnectTimer.current = window.setTimeout(connect, delay)
    }

    ws.onerror = (e) => {
      console.error('[ACP] WebSocket error', e)
    }

    ws.onmessage = (event) => {
      try {
        const msg: ServerMessage = JSON.parse(event.data)
        handleMessage(msg)
      } catch (e) {
        console.error('[ACP] Failed to parse message', e)
      }
    }
  }, [])

  const handleMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case 'session_created':
        store.setSessionId(msg.sessionId)
        console.log('[ACP] Session created:', msg.sessionId)
        break

      case 'update':
        handleSessionUpdate(msg.update)
        break

      case 'complete':
        store.setStreaming(false)
        store.addMessage({
          id: createMessageId(),
          role: 'system',
          content: `Turn complete (${msg.stopReason})`,
          timestamp: Date.now(),
        })
        console.log('[ACP] Prompt complete:', msg.stopReason)
        break

      case 'permission_request':
        store.addMessage({
          id: createMessageId(),
          role: 'system',
          content: `Permission requested: ${msg.tool} — ${msg.action}`,
          timestamp: Date.now(),
        })
        break

      case 'error':
        store.addMessage({
          id: createMessageId(),
          role: 'system',
          content: `Error: ${msg.message}`,
          timestamp: Date.now(),
        })
        store.setStreaming(false)
        break

      case 'pong':
        break
    }
  }, [])

  const handleSessionUpdate = useCallback((update: SessionUpdate) => {
    switch (update.sessionUpdate) {
      case 'agent_message_chunk': {
        const block = update.content
        if (block.type === 'text' && block.text) {
          store.appendToLastAgent(block.text)
        }
        break
      }

      case 'agent_thought_chunk': {
        // Could display thinking indicator; skip for now
        break
      }

      case 'user_message_chunk': {
        // Echo from server; skip
        break
      }

      case 'tool_call': {
        store.addToolCall({
          id: update.toolCallId,
          name: update.title,
          status: update.status === 'completed' ? 'completed' : 'in_progress',
        })
        break
      }

      case 'tool_call_update': {
        const status = update.status === 'completed' ? 'completed' as const
          : update.status === 'incomplete' ? 'completed' as const
          : 'in_progress' as const
        store.updateToolCall(update.toolCallId, {
          status,
          ...(update.title ? { name: update.title } : {}),
        })
        break
      }

      case 'plan': {
        store.setCurrentPlan(update.entries.map(e => ({
          description: e.description,
          status: e.status,
          priority: e.priority,
        })))
        break
      }

      case 'session_info_update': {
        // Could update session title in the UI
        break
      }

      case 'available_commands_update': {
        // Commands discovered — update plugin store dynamically
        // ACP sends availableCommands at the update level
        const cmds: any[] = (update as any).availableCommands ?? (update as any).commands ?? []
        if (cmds.length > 0) {
          // Parse into grouped structure (same logic as /acp/commands endpoint)
          const grouped: Record<string, any[]> = {}
          for (const cmd of cmds) {
            const name = cmd.name ?? ''
            if (name.includes(':')) {
              const [plugin, ...rest] = name.split(':')
              const cmdName = rest.join(':')
              if (!grouped[plugin]) grouped[plugin] = []
              grouped[plugin].push({
                name: cmdName,
                fullName: name,
                description: cmd.description ?? '',
                input: cmd.input ?? null,
              })
            } else {
              if (!grouped['_project']) grouped['_project'] = []
              grouped['_project'].push({
                name, fullName: name,
                description: cmd.description ?? '',
                input: cmd.input ?? null,
              })
            }
          }
          const ps = usePluginStore.getState()
          ps.setGrouped(grouped, cmds.length)
          // Auto-select first wicked-* plugin if none selected
          if (!ps.activePlugin) {
            const names = Object.keys(grouped).filter(n => n.startsWith('wicked-')).sort()
            if (names.length > 0) ps.setActivePlugin(names[0])
          }
          console.log(`[ACP] Commands discovered: ${cmds.length}`)
        }
        break
      }

      default:
        // usage_update, current_mode_update, config_option_update
        break
    }
  }, [])

  const send = useCallback((message: ClientMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  const sendPrompt = useCallback((text: string, plugin?: string, view?: string) => {
    store.addMessage({
      id: createMessageId(),
      role: 'user',
      content: text,
      timestamp: Date.now(),
    })
    store.setStreaming(true)
    send({ type: 'prompt', text, plugin, view })
  }, [send])

  const cancel = useCallback(() => {
    send({ type: 'cancel' })
    store.setStreaming(false)
  }, [send])

  const respondToPermission = useCallback((requestId: string, approved: boolean) => {
    send({ type: 'permission_response', requestId, approved })
  }, [send])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return {
    connected: store.connected,
    sessionId: store.sessionId,
    streaming: store.streaming,
    sendPrompt,
    cancel,
    respondToPermission,
  }
}
