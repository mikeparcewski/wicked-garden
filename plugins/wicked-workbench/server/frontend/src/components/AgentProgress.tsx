import { useACPStore } from '../stores/acpStore'
import { Badge } from './primitives'

export function AgentProgress() {
  const { streaming, activeToolCalls, currentPlan } = useACPStore()

  if (!streaming && activeToolCalls.length === 0 && currentPlan.length === 0) {
    return null
  }

  return (
    <div className="border-b border-[var(--border)] bg-[var(--bg-tertiary)] px-4 py-2">
      {/* Streaming indicator */}
      {streaming && (
        <div className="flex items-center gap-2 mb-1">
          <div className="flex gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 streaming-dot" style={{ animationDelay: '0s' }} />
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 streaming-dot" style={{ animationDelay: '0.3s' }} />
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 streaming-dot" style={{ animationDelay: '0.6s' }} />
          </div>
          <span className="text-xs text-[var(--text-muted)]">Agent is working...</span>
        </div>
      )}

      {/* Active tool calls */}
      {activeToolCalls.filter(tc => tc.status !== 'completed').map(tc => (
        <div key={tc.id} className="flex items-center gap-2 text-xs py-0.5">
          <Badge
            label={tc.status === 'in_progress' ? 'running' : tc.status}
            variant={tc.status === 'in_progress' ? 'info' : 'default'}
          />
          <span className="text-[var(--text-secondary)] font-mono">{tc.name}</span>
          {tc.requiresPermission && (
            <Badge label="needs approval" variant="warning" />
          )}
        </div>
      ))}

      {/* Plan progress */}
      {currentPlan.length > 0 && (
        <div className="mt-1 space-y-0.5">
          {currentPlan.map((entry, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span className={
                entry.status === 'completed' ? 'text-green-400' :
                entry.status === 'in_progress' ? 'text-blue-400' :
                'text-[var(--text-muted)]'
              }>
                {entry.status === 'completed' ? '✓' : entry.status === 'in_progress' ? '→' : '○'}
              </span>
              <span className={
                entry.status === 'completed' ? 'text-[var(--text-muted)] line-through' :
                entry.status === 'in_progress' ? 'text-[var(--text-primary)]' :
                'text-[var(--text-secondary)]'
              }>
                {entry.description}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
