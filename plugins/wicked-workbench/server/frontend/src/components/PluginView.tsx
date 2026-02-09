import { useEffect } from 'react'
import { usePluginStore } from '../stores/pluginStore'
import { useACPStore } from '../stores/acpStore'
import { useACP } from '../hooks/useACP'
import { AgentProgress } from './AgentProgress'

export function PluginView() {
  const { activePlugin, activeCommand, getActiveCommands } = usePluginStore()
  const { streaming, messages } = useACPStore()
  const { connected, sendPrompt } = useACP()
  const commands = getActiveCommands()

  // When a command is selected, invoke it via the agent
  useEffect(() => {
    if (!activeCommand || !connected) return
    sendPrompt(`/${activeCommand}`, activePlugin ?? undefined)
  }, [activeCommand, connected])

  if (!activePlugin) {
    return (
      <div className="p-8 text-center">
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-2">Welcome to Wicked Workbench</h2>
        <p className="text-sm text-[var(--text-muted)]">Select a plugin from the sidebar to get started.</p>
      </div>
    )
  }

  // Get the last agent message for the main content area
  const lastAgentMsg = [...messages].reverse().find(m => m.role === 'agent')

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[var(--border)] flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            {activePlugin.replace('wicked-', '')}
            {activeCommand && (
              <span className="text-[var(--text-muted)]"> / {activeCommand.split(':')[1] ?? activeCommand}</span>
            )}
          </h2>
          <p className="text-xs text-[var(--text-muted)]">
            {commands.length} commands available
          </p>
        </div>

        {/* Quick command buttons */}
        <div className="flex gap-2 flex-wrap justify-end max-w-[50%]">
          {commands.slice(0, 4).map(cmd => (
            <button
              key={cmd.fullName}
              onClick={() => sendPrompt(`/${cmd.fullName}`, activePlugin)}
              disabled={!connected || streaming}
              className={`px-3 py-1.5 text-xs border rounded-lg transition-colors disabled:opacity-50 ${
                activeCommand === cmd.fullName
                  ? 'bg-violet-500/20 border-violet-500/50 text-violet-400'
                  : 'bg-[var(--bg-secondary)] border-[var(--border)] text-[var(--text-secondary)] hover:border-violet-500/50 hover:text-violet-400'
              }`}
              title={cmd.description.split('\n')[0]}
            >
              /{cmd.name}
            </button>
          ))}
        </div>
      </div>

      {/* Agent progress indicator */}
      <AgentProgress />

      {/* Main content — agent's response */}
      <div className="flex-1 overflow-y-auto p-6">
        {lastAgentMsg ? (
          <div className="prose prose-invert max-w-none">
            <pre className="whitespace-pre-wrap font-sans text-sm text-[var(--text-secondary)]">
              {lastAgentMsg.content}
            </pre>
          </div>
        ) : !streaming ? (
          <div className="text-center text-[var(--text-muted)] py-12">
            <p className="text-sm mb-2">Click a command to ask the agent</p>
            <p className="text-xs">Commands are discovered from the ACP agent automatically</p>
          </div>
        ) : null}
      </div>
    </div>
  )
}
