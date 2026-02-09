interface ProgressBarProps {
  value: number
  max?: number
  label?: string
  color?: 'accent' | 'success' | 'warning' | 'error'
  size?: 'sm' | 'md'
}

const colorMap = {
  accent: 'bg-violet-500',
  success: 'bg-green-500',
  warning: 'bg-yellow-500',
  error: 'bg-red-500',
}

export function ProgressBar({ value, max = 100, label, color = 'accent', size = 'sm' }: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const height = size === 'sm' ? 'h-1.5' : 'h-2.5'

  return (
    <div>
      {label && (
        <div className="flex justify-between text-xs text-[var(--text-muted)] mb-1">
          <span>{label}</span>
          <span>{Math.round(pct)}%</span>
        </div>
      )}
      <div className={`w-full ${height} bg-[var(--bg-tertiary)] rounded-full overflow-hidden`}>
        <div
          className={`${height} ${colorMap[color]} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
