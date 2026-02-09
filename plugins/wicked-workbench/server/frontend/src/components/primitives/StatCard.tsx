interface StatCardProps {
  label: string
  value: string | number
  change?: string
  trend?: 'up' | 'down' | 'neutral'
  icon?: string
}

export function StatCard({ label, value, change, trend }: StatCardProps) {
  const trendColor = trend === 'up' ? 'text-green-400' : trend === 'down' ? 'text-red-400' : 'text-[var(--text-muted)]'

  return (
    <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg p-4">
      <p className="text-xs text-[var(--text-muted)] uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-[var(--text-primary)]">{value}</p>
      {change && (
        <p className={`text-xs mt-1 ${trendColor}`}>
          {trend === 'up' ? '+' : trend === 'down' ? '-' : ''}{change}
        </p>
      )}
    </div>
  )
}
