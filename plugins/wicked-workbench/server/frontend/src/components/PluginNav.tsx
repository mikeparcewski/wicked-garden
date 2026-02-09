import { usePluginStore } from '../stores/pluginStore'

const pluginIcons: Record<string, string> = {
  'wicked-agentic': '🤖',
  'wicked-cache': '💾',
  'wicked-crew': '👥',
  'wicked-data': '📊',
  'wicked-delivery': '📦',
  'wicked-engineering': '🔧',
  'wicked-jam': '🎸',
  'wicked-kanban': '📋',
  'wicked-mem': '🧠',
  'wicked-patch': '🩹',
  'wicked-platform': '🛡️',
  'wicked-product': '💡',
  'wicked-search': '🔍',
  'wicked-smaht': '🧩',
  'wicked-workbench': '🖥️',
  'hookify': '🪝',
  'plugin-dev': '🔌',
}

export function PluginNav() {
  const { activePlugin, setActivePlugin, activeCommand, setActiveCommand, getPluginNames, getActiveCommands, commandCount } = usePluginStore()

  const pluginNames = getPluginNames()
  const activeCommands = getActiveCommands()

  return (
    <nav className="flex flex-col h-full">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-[var(--border)]">
        <h1 className="text-sm font-bold text-violet-400 tracking-wider">WICKED WORKBENCH</h1>
        <p className="text-[10px] text-[var(--text-muted)] mt-0.5">Agent-Driven UI</p>
      </div>

      {/* Plugin list */}
      <div className="flex-1 overflow-y-auto py-2">
        <p className="px-4 py-1 text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
          Plugins
        </p>

        {pluginNames.map(name => {
          const isActive = activePlugin === name
          const icon = pluginIcons[name] ?? '📦'
          const label = name.replace('wicked-', '')

          return (
            <div key={name}>
              <button
                className={`w-full flex items-center gap-2 px-4 py-2 text-sm text-left transition-colors ${
                  isActive
                    ? 'bg-violet-500/10 text-violet-400 border-r-2 border-violet-500'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]'
                }`}
                onClick={() => setActivePlugin(name)}
              >
                <span className="text-base">{icon}</span>
                <span className="capitalize">{label}</span>
              </button>

              {/* Commands as sub-items */}
              {isActive && activeCommands.length > 0 && (
                <div className="ml-8 border-l border-[var(--border)]">
                  {activeCommands.map(cmd => (
                    <button
                      key={cmd.name}
                      className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${
                        activeCommand === cmd.fullName
                          ? 'text-violet-400'
                          : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
                      }`}
                      onClick={() => setActiveCommand(cmd.fullName)}
                      title={cmd.description.split('\n')[0]}
                    >
                      {cmd.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Status */}
      <div className="px-4 py-2 border-t border-[var(--border)] text-[10px] text-[var(--text-muted)]">
        {commandCount} commands · {pluginNames.length} plugins
      </div>
    </nav>
  )
}
