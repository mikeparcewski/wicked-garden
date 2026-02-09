interface TableProps {
  columns: { key: string; label: string; width?: string }[]
  rows: Record<string, unknown>[]
  onRowClick?: (row: Record<string, unknown>) => void
}

export function Table({ columns, rows, onRowClick }: TableProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-[var(--bg-tertiary)]">
            {columns.map(col => (
              <th
                key={col.key}
                className="text-left text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider px-4 py-2"
                style={col.width ? { width: col.width } : undefined}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border)]">
          {rows.map((row, i) => (
            <tr
              key={i}
              className={`bg-[var(--bg-secondary)] ${onRowClick ? 'cursor-pointer hover:bg-[var(--bg-tertiary)] transition-colors' : ''}`}
              onClick={() => onRowClick?.(row)}
            >
              {columns.map(col => (
                <td key={col.key} className="px-4 py-2.5 text-[var(--text-secondary)]">
                  {String(row[col.key] ?? '')}
                </td>
              ))}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-4 py-8 text-center text-[var(--text-muted)]">
                No data
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
