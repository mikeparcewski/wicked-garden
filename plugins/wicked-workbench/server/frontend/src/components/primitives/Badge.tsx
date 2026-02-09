interface BadgeProps {
  label: string
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info' | 'accent'
  size?: 'sm' | 'md'
}

const variantStyles = {
  default: 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]',
  success: 'bg-green-500/20 text-green-400',
  warning: 'bg-yellow-500/20 text-yellow-400',
  error: 'bg-red-500/20 text-red-400',
  info: 'bg-blue-500/20 text-blue-400',
  accent: 'bg-violet-500/20 text-violet-400',
}

export function Badge({ label, variant = 'default', size = 'sm' }: BadgeProps) {
  const sizeClass = size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-1'
  return (
    <span className={`inline-flex items-center rounded-full font-medium ${variantStyles[variant]} ${sizeClass}`}>
      {label}
    </span>
  )
}
