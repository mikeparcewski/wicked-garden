import type { A2UIComponent, ResolvedComponent } from '../types/a2ui'
import { Card, Badge, Table, StatCard, ProgressBar } from './primitives'

interface Props {
  components: A2UIComponent[]
}

/** Resolve flat A2UI component list into a tree structure */
function resolveTree(components: A2UIComponent[]): ResolvedComponent | null {
  const map = new Map<string, A2UIComponent>()
  for (const c of components) {
    map.set(c.id, c)
  }

  const root = components.find(c => c.id === 'root')
  if (!root) {
    // If no root, treat all components as children of an implicit column
    return {
      id: 'root',
      component: 'Column',
      props: {},
      children: components.map(c => resolveNode(c, map)),
    }
  }

  return resolveNode(root, map)
}

function resolveNode(comp: A2UIComponent, map: Map<string, A2UIComponent>): ResolvedComponent {
  const { id, component, children: childIds, ...props } = comp
  const children = (childIds ?? [])
    .map(cid => map.get(cid))
    .filter((c): c is A2UIComponent => c !== undefined)
    .map(c => resolveNode(c, map))

  return { id, component, props, children }
}

/** Render a resolved component tree */
function RenderNode({ node }: { node: ResolvedComponent }) {
  const { component, props, children } = node

  switch (component) {
    case 'Row':
      return (
        <div className="flex gap-4 flex-wrap" style={props.style as React.CSSProperties}>
          {children.map(c => <RenderNode key={c.id} node={c} />)}
        </div>
      )

    case 'Column':
      return (
        <div className="flex flex-col gap-4" style={props.style as React.CSSProperties}>
          {children.map(c => <RenderNode key={c.id} node={c} />)}
        </div>
      )

    case 'Grid':
      return (
        <div
          className="grid gap-4"
          style={{
            gridTemplateColumns: `repeat(${(props.columns as number) ?? 3}, minmax(0, 1fr))`,
            ...(props.style as React.CSSProperties ?? {}),
          }}
        >
          {children.map(c => <RenderNode key={c.id} node={c} />)}
        </div>
      )

    case 'Card':
      return (
        <Card
          title={props.title as string}
          subtitle={props.subtitle as string}
          accent={props.accent as 'default' | 'success' | 'warning' | 'error' | 'info'}
        >
          {children.length > 0
            ? children.map(c => <RenderNode key={c.id} node={c} />)
            : props.content && <p className="text-sm text-[var(--text-secondary)]">{String(props.content)}</p>
          }
        </Card>
      )

    case 'StatCard':
      return (
        <StatCard
          label={String(props.label ?? '')}
          value={props.value as string | number}
          change={props.change as string}
          trend={props.trend as 'up' | 'down' | 'neutral'}
        />
      )

    case 'Badge':
      return (
        <Badge
          label={String(props.label ?? '')}
          variant={props.variant as 'default' | 'success' | 'warning' | 'error' | 'info' | 'accent'}
        />
      )

    case 'Table':
      return (
        <Table
          columns={props.columns as { key: string; label: string }[]}
          rows={props.rows as Record<string, unknown>[]}
        />
      )

    case 'ProgressBar':
      return (
        <ProgressBar
          value={props.value as number}
          max={props.max as number}
          label={props.label as string}
          color={props.color as 'accent' | 'success' | 'warning' | 'error'}
        />
      )

    case 'Text':
      return (
        <p className={`text-sm ${
          props.variant === 'heading' ? 'text-lg font-semibold text-[var(--text-primary)]' :
          props.variant === 'muted' ? 'text-[var(--text-muted)]' :
          'text-[var(--text-secondary)]'
        }`}>
          {String(props.text ?? props.content ?? '')}
        </p>
      )

    case 'List':
      return (
        <div className="space-y-2">
          {props.title && <h3 className="text-sm font-semibold text-[var(--text-primary)]">{String(props.title)}</h3>}
          {children.map(c => <RenderNode key={c.id} node={c} />)}
        </div>
      )

    // Kanban-specific components
    case 'KanbanBoard':
      return (
        <div className="flex gap-4 overflow-x-auto pb-2">
          {children.map(c => <RenderNode key={c.id} node={c} />)}
        </div>
      )

    case 'Swimlane':
      return (
        <div className="flex-shrink-0 w-72 bg-[var(--bg-tertiary)] rounded-lg p-3">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            {String(props.title ?? props.status ?? '')}
            {props.count !== undefined && (
              <Badge label={String(props.count)} variant="default" />
            )}
          </h3>
          <div className="space-y-2">
            {children.map(c => <RenderNode key={c.id} node={c} />)}
          </div>
        </div>
      )

    case 'TaskCard':
      return (
        <Card
          title={String(props.title ?? props.name ?? '')}
          accent={props.priority === 'critical' || props.priority === 'high' ? 'warning' :
                  props.status === 'blocked' ? 'error' :
                  props.status === 'completed' ? 'success' : 'default'}
        >
          {props.description && (
            <p className="text-xs text-[var(--text-muted)] mb-2">{String(props.description)}</p>
          )}
          <div className="flex gap-1 flex-wrap">
            {props.priority && <Badge label={String(props.priority)} variant={
              props.priority === 'critical' ? 'error' :
              props.priority === 'high' ? 'warning' :
              'default'
            } />}
            {props.status && <Badge label={String(props.status)} variant={
              props.status === 'completed' ? 'success' :
              props.status === 'blocked' ? 'error' :
              props.status === 'in_progress' ? 'info' :
              'default'
            } />}
            {Array.isArray(props.tags) && props.tags.map((tag, i) => (
              <Badge key={i} label={String(tag)} variant="accent" />
            ))}
          </div>
        </Card>
      )

    case 'TaskList':
      return (
        <div className="space-y-2">
          {props.title && <h3 className="text-sm font-semibold text-[var(--text-primary)]">{String(props.title)}</h3>}
          {children.map(c => <RenderNode key={c.id} node={c} />)}
        </div>
      )

    // Memory-specific components
    case 'MemoryPanel':
      return (
        <div className="space-y-2">
          {props.title && <h3 className="text-sm font-semibold text-[var(--text-primary)]">{String(props.title)}</h3>}
          {children.map(c => <RenderNode key={c.id} node={c} />)}
        </div>
      )

    case 'MemoryItem':
      return (
        <Card
          title={String(props.title ?? props.content ?? '').slice(0, 80)}
          accent={props.type === 'decision' ? 'info' :
                  props.type === 'procedural' ? 'success' :
                  props.type === 'episodic' ? 'warning' : 'default'}
        >
          <div className="flex gap-1 mb-1">
            {props.type && <Badge label={String(props.type)} variant="accent" />}
            {props.importance && <Badge label={`★ ${props.importance}`} variant="default" />}
          </div>
          {props.content && (
            <p className="text-xs text-[var(--text-muted)]">{String(props.content).slice(0, 200)}</p>
          )}
        </Card>
      )

    // Fallback: render as generic card
    default:
      return (
        <Card title={`${component}`} subtitle={`Unknown component type`}>
          <pre className="text-xs text-[var(--text-muted)] overflow-auto">
            {JSON.stringify(props, null, 2)}
          </pre>
          {children.map(c => <RenderNode key={c.id} node={c} />)}
        </Card>
      )
  }
}

export function ComponentRenderer({ components }: Props) {
  if (components.length === 0) return null

  const tree = resolveTree(components)
  if (!tree) return null

  return (
    <div className="p-4">
      <RenderNode node={tree} />
    </div>
  )
}
