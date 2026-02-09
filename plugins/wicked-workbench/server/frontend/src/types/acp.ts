/** ACP WebSocket message types (browser ↔ server) */

/** Messages FROM browser TO server */
export type ClientMessage =
  | { type: 'prompt'; text: string; plugin?: string; view?: string }
  | { type: 'cancel' }
  | { type: 'permission_response'; requestId: string; approved: boolean }

/** Messages FROM server TO browser */
export type ServerMessage =
  | { type: 'session_created'; sessionId: string }
  | { type: 'update'; sessionId: string; update: SessionUpdate }
  | { type: 'error'; message: string }
  | { type: 'complete'; sessionId: string; stopReason: string }
  | { type: 'permission_request'; sessionId: string; requestId: string; tool: string; action: string; details: Record<string, unknown> }
  | { type: 'pong' }

/**
 * ACP SessionUpdate — discriminated union on `sessionUpdate` field.
 * Maps directly to the @agentclientprotocol/sdk SessionUpdate type.
 */
export type SessionUpdate =
  | { sessionUpdate: 'user_message_chunk'; content: ContentBlock }
  | { sessionUpdate: 'agent_message_chunk'; content: ContentBlock }
  | { sessionUpdate: 'agent_thought_chunk'; content: ContentBlock }
  | { sessionUpdate: 'tool_call'; toolCallId: string; title: string; status?: ToolCallStatus; kind?: string; content?: ToolCallContent[]; rawInput?: unknown }
  | { sessionUpdate: 'tool_call_update'; toolCallId: string; title?: string; status?: ToolCallStatus; content?: ToolCallContent[]; rawInput?: unknown; rawOutput?: unknown }
  | { sessionUpdate: 'plan'; entries: PlanEntry[] }
  | { sessionUpdate: 'available_commands_update'; commands: unknown[] }
  | { sessionUpdate: 'current_mode_update'; mode: string }
  | { sessionUpdate: 'session_info_update'; title?: string }
  | { sessionUpdate: 'usage_update'; cost?: { amount: number; currency: string } }

export type ToolCallStatus = 'running' | 'completed' | 'incomplete'

/** ACP ContentBlock — a single piece of content */
export type ContentBlock =
  | { type: 'text'; text: string }
  | { type: 'image'; data: string; mimeType: string }
  | { type: 'resource'; uri: string; mimeType?: string; text?: string }

/** ACP ToolCallContent */
export type ToolCallContent =
  | { type: 'content'; content: ContentBlock[] }
  | { type: 'diff'; path: string; diff: string }
  | { type: 'terminal'; terminalId: string }

export interface PlanEntry {
  description: string
  status: 'pending' | 'in_progress' | 'completed'
  priority?: 'high' | 'medium' | 'low'
}
