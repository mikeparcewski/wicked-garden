# Outcome: wicked-smaht

## Desired Outcome

wicked-smaht acts as the "prefrontal cortex" for Claude Code, intelligently assembling relevant context from across the wicked-garden ecosystem (wicked-mem, wicked-jam, wicked-kanban, wicked-search) before Claude responds to user queries or hands off to specialized agents. It delivers fast, relevant context by default while allowing deeper analysis on demand, ensuring Claude has the right memories, brainstorm sessions, tasks, and code references to provide informed, contextually-aware responses.

## Success Criteria

1. **Fast Default Context Assembly** - 90% of turn-level context gathering completes in <2 seconds, providing at least 3 relevant items from any combination of sources (memories, jam sessions, tasks, code refs).

2. **Multi-Source Integration** - Successfully queries and ranks results from all four data sources (wicked-mem, wicked-jam, wicked-kanban, wicked-search) using a unified relevance scoring algorithm that combines semantic similarity, recency, project context, and explicit links.

3. **Adaptive Depth Control** - Supports three context modes: (a) session-level context via SessionStart hook, (b) optional per-turn enrichment via UserPromptSubmit hook (off by default), and (c) explicit deep analysis via `/smaht` command that can take 5-10 seconds for thorough cross-source analysis.

4. **Agent Handoff Context** - When wicked-crew orchestrator switches between agents (e.g., facilitator → implementer, or generic → wicked-engineering specialist), automatically assembles relevant context packet containing recent decisions, related tasks, and implementation references.

5. **Configurable Behavior** - Users can enable/disable per-turn enrichment, set relevance thresholds, specify preferred sources, and configure ranking weights through a simple configuration file or `/smaht config` command.

6. **Context Overload Prevention** - Implements ranking and summarization to limit context injection to ≤1500 tokens per turn by default, with clear truncation indicators when more context is available via `/smaht` command.

7. **Graceful Degradation** - If any data source is unavailable (e.g., wicked-jam not installed), continues to function using available sources and logs which sources were skipped.

## Scope

### In Scope

- **Hook-based automatic context gathering** at SessionStart (always) and UserPromptSubmit (configurable)
- **Multi-source querying** across wicked-mem, wicked-jam, wicked-kanban, wicked-search
- **Unified relevance ranking** using configurable multi-factor scoring (semantic, temporal, project, explicit links)
- **Progressive context enhancement** - fast initial pass, deeper analysis on demand
- **Agent handoff context packets** for wicked-crew orchestrator transitions
- **Configuration system** for user preferences (auto-enrichment, thresholds, source weights)
- **Context summarization** to prevent overload (ranking, truncation, token limits)
- **Explicit `/smaht` command** for deep context analysis with detailed output
- **Graceful degradation** when data sources are unavailable
- **Query type detection** to adjust ranking weights (debugging vs planning vs research)

### Out of Scope

- **New data storage** - wicked-smaht does NOT store data, only queries existing systems
- **Real-time indexing** - relies on source systems' existing indexes (wicked-search FAISS, wicked-mem embeddings, etc.)
- **Context prediction/pre-fetching** - does not attempt to predict future context needs
- **Cross-conversation learning** - does not learn user preferences across sessions (uses explicit config only)
- **Natural language context queries** - `/smaht` uses structured queries, not "tell me about X" natural language
- **Context editing/filtering UI** - no interactive context selection interface
- **External data sources** - only integrates with wicked-garden ecosystem plugins
- **Automatic hook installation** - user must manually enable UserPromptSubmit hook if desired

## Constraints

- **Performance budget**: Default context gathering must complete in <2 seconds to avoid turn latency
- **Token budget**: Context injection limited to ≤1500 tokens by default (configurable up to 4000)
- **Dependency management**: Must gracefully handle missing plugins (not all users have all four sources)
- **Hook conflicts**: UserPromptSubmit hook is optional and off by default to avoid conflicts with other plugins
- **Privacy**: Respects wicked-mem privacy settings and does not expose redacted memories
- **Backward compatibility**: Does not modify or depend on internal implementation details of source systems

## Key Design Questions

Before moving to design phase, these questions need answers:

1. **Relevance Scoring Algorithm**: What's the specific formula for multi-factor ranking? How are semantic similarity, recency, project context, and explicit links weighted? Should weights be static or dynamic based on query type?

2. **Query Type Detection**: How does wicked-smaht detect whether a user query is about debugging, planning, research, or general conversation? Pattern matching on keywords? LLM classification? Heuristics?

3. **Context Packet Format**: What's the structured format for context injected into Claude's turn? JSON? Markdown sections? How should conflicting information from different sources be presented?

4. **Agent Handoff Mechanism**: How does wicked-smaht detect agent transitions in wicked-crew? Does it hook into crew's orchestration, or does crew explicitly call wicked-smaht?

5. **Caching Strategy**: Should wicked-smaht cache assembled context for the session? If yes, what's the invalidation strategy (time-based, event-based, manual)?

6. **Semantic Search Implementation**: Does wicked-smaht use wicked-search's existing FAISS index for semantic similarity, or does it need its own cross-source embedding index? If the latter, where are embeddings stored?

7. **Configuration Scope**: Should configuration be per-repository (`.claude/smaht-config.json`) or global user settings (`~/.config/claude/smaht.json`)? Or both with override hierarchy?

8. **Context Summarization Method**: When context exceeds token limits, how is it summarized? Truncate by relevance score? Use LLM to create summary? Template-based extraction?

9. **Source Query Interface**: Do source plugins need new APIs (e.g., `wicked-mem query --semantic "bug in auth"`), or can wicked-smaht use existing commands? If new APIs, what's the standardization approach?

10. **Failure Modes**: What happens when multiple sources fail simultaneously? Fall back to wicked-search only? Show error to user? Silent degradation with warning log?
