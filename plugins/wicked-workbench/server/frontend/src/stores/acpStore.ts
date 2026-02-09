import { create } from 'zustand'
import type { ServerMessage, PlanEntry } from '../types/acp'
import type { A2UIComponent } from '../types/a2ui'

export interface ChatMessage {
  id: string
  role: 'user' | 'agent' | 'system'
  content: string
  timestamp: number
  components?: A2UIComponent[]
}

export interface ToolCallInfo {
  id: string
  name: string
  status: 'pending' | 'in_progress' | 'completed'
  requiresPermission?: boolean
}

interface ACPState {
  connected: boolean
  sessionId: string | null
  streaming: boolean
  messages: ChatMessage[]
  currentPlan: PlanEntry[]
  activeToolCalls: ToolCallInfo[]
  renderedComponents: A2UIComponent[]
  pendingText: string

  setConnected: (connected: boolean) => void
  setSessionId: (id: string | null) => void
  setStreaming: (streaming: boolean) => void
  addMessage: (msg: ChatMessage) => void
  appendToLastAgent: (text: string) => void
  setCurrentPlan: (plan: PlanEntry[]) => void
  addToolCall: (tc: ToolCallInfo) => void
  updateToolCall: (id: string, updates: Partial<ToolCallInfo>) => void
  setRenderedComponents: (components: A2UIComponent[]) => void
  clearMessages: () => void
  setPendingText: (text: string) => void
}

// Message ID generation

export const useACPStore = create<ACPState>((set, get) => ({
  connected: false,
  sessionId: null,
  streaming: false,
  messages: [],
  currentPlan: [],
  activeToolCalls: [],
  renderedComponents: [],
  pendingText: '',

  setConnected: (connected) => set({ connected }),
  setSessionId: (sessionId) => set({ sessionId }),
  setStreaming: (streaming) => set({ streaming }),

  addMessage: (msg) => set(s => ({ messages: [...s.messages, msg] })),

  appendToLastAgent: (text) => set(s => {
    const msgs = [...s.messages]
    const last = msgs[msgs.length - 1]
    if (last?.role === 'agent') {
      msgs[msgs.length - 1] = { ...last, content: last.content + text }
    } else {
      msgs.push({
        id: createMessageId(),
        role: 'agent',
        content: text,
        timestamp: Date.now(),
      })
    }
    return { messages: msgs }
  }),

  setCurrentPlan: (currentPlan) => set({ currentPlan }),

  addToolCall: (tc) => set(s => ({
    activeToolCalls: [...s.activeToolCalls, tc],
  })),

  updateToolCall: (id, updates) => set(s => ({
    activeToolCalls: s.activeToolCalls.map(tc =>
      tc.id === id ? { ...tc, ...updates } : tc
    ),
  })),

  setRenderedComponents: (renderedComponents) => set({ renderedComponents }),
  clearMessages: () => set({ messages: [], currentPlan: [], activeToolCalls: [], renderedComponents: [] }),
  setPendingText: (pendingText) => set({ pendingText }),
}))

/** Generate unique message ID */
export function createMessageId(): string {
  return `msg-${crypto.randomUUID()}`
}
