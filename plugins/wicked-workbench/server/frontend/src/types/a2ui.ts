/** A2UI Document types */

export type A2UIDocument = A2UIMessage[]

export type A2UIMessage =
  | { createSurface: { surfaceId: string; catalogId?: string } }
  | { updateComponents: { surfaceId: string; components: A2UIComponent[] } }
  | { updateDataModel: { surfaceId: string; actorId: string; updates: DataUpdate[] } }

export interface A2UIComponent {
  id: string
  component: string
  children?: string[]
  [key: string]: unknown // props
}

export interface DataUpdate {
  path: string
  value: unknown
}

/** Resolved component tree (after processing flat list into tree) */
export interface ResolvedComponent {
  id: string
  component: string
  props: Record<string, unknown>
  children: ResolvedComponent[]
}
