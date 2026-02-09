import type { ReactNode } from 'react'

interface CardProps {
  title?: string
  subtitle?: string
  accent?: 'default' | 'success' | 'warning' | 'error' | 'info'
  children?: ReactNode
  className?: string
  onClick?: () => void
}

const accentColors = {
  default: 'border-[var(--border)]',
  success: 'border-green-500/40',
  warning: 'border-yellow-500/40',
  error: 'border-red-500/40',
  info: 'border-blue-500/40',
}

export function Card({ title, subtitle, accent = 'default', children, className = '', onClick }: CardProps) {
  return (
    <div
      className={`bg-[var(--bg-secondary)] border ${accentColors[accent]} rounded-lg p-4 ${onClick ? 'cursor-pointer hover:border-[var(--border-hover)] transition-colors' : ''} ${className}`}
      onClick={onClick}
    >
      {title && (
        <div className="mb-2">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
          {subtitle && <p className="text-xs text-[var(--text-muted)] mt-0.5">{subtitle}</p>}
        </div>
      )}
      {children}
    </div>
  )
}
