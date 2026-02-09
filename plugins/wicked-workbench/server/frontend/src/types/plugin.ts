/** Plugin and command types — derived from ACP available_commands_update */

export interface AgentCommand {
  name: string
  fullName: string
  description: string
  input: { hint?: string } | null
}

/** Grouped response from /acp/commands */
export interface CommandsResponse {
  commands: unknown[]
  grouped: Record<string, AgentCommand[]>
  count: number
}
