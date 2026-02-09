import { useRef, useEffect, useState, type FormEvent } from 'react'
import { useACPStore } from '../stores/acpStore'
import { useACP } from '../hooks/useACP'
import { usePluginStore } from '../stores/pluginStore'
import { ComponentRenderer } from './ComponentRenderer'

export function ChatPanel() {
  const { messages, streaming, renderedComponents } = useACPStore()
  const { connected, sendPrompt, cancel } = useACP()
  const { activePlugin } = usePluginStore()
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const text = input.trim()
    if (!text || !connected) return

    sendPrompt(text, activePlugin ?? undefined)
    setInput('')
  }

  return (
    <div className="flex flex-col h-full bg-[var(--bg-primary)]">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border)] flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Agent Chat</h2>
          <p className="text-[10px] text-[var(--text-muted)]">
            {connected ? (
              <span className="text-green-400">Connected</span>
            ) : (
              <span className="text-red-400">Disconnected</span>
            )}
            {activePlugin && <span> &middot; {activePlugin}</span>}
          </p>
        </div>
        {streaming && (
          <button
            onClick={cancel}
            className="px-2 py-1 text-xs bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors"
          >
            Stop
          </button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-[var(--text-muted)] text-sm py-12">
            <p className="mb-2">Ask anything about your plugins</p>
            <p className="text-xs">Try: "Show me recent memories" or "What tasks are blocked?"</p>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
              msg.role === 'user'
                ? 'bg-violet-500/20 text-violet-200'
                : msg.role === 'system'
                ? 'bg-red-500/10 text-red-300 border border-red-500/20'
                : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] border border-[var(--border)]'
            }`}>
              <pre className="whitespace-pre-wrap font-sans text-sm">{msg.content}</pre>
              {msg.components && msg.components.length > 0 && (
                <div className="mt-2 border-t border-[var(--border)] pt-2">
                  <ComponentRenderer components={msg.components} />
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Streaming indicator */}
        {streaming && (
          <div className="flex justify-start">
            <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg px-3 py-2">
              <div className="flex gap-1">
                <span className="w-2 h-2 rounded-full bg-violet-400 streaming-dot" style={{ animationDelay: '0s' }} />
                <span className="w-2 h-2 rounded-full bg-violet-400 streaming-dot" style={{ animationDelay: '0.2s' }} />
                <span className="w-2 h-2 rounded-full bg-violet-400 streaming-dot" style={{ animationDelay: '0.4s' }} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Inline rendered components from last agent response */}
      {renderedComponents.length > 0 && (
        <div className="border-t border-[var(--border)] max-h-64 overflow-y-auto">
          <ComponentRenderer components={renderedComponents} />
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-[var(--border)]">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={connected ? 'Ask your plugins anything...' : 'Connecting...'}
            disabled={!connected}
            className="flex-1 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-violet-500/50 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!connected || !input.trim() || streaming}
            className="px-4 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  )
}
