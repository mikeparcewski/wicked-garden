# Cross CLI/IDE Platform Strategy

> Competitive analysis: `affaan-m/everything-claude-code` (ECC) vs `wicked-garden` (WG)
> Date: 2026-03-30

## How ECC Handles Cross-Platform

ECC supports **5 platforms** with dedicated configuration directories:

```
everything-claude-code/
├── .claude/          # Claude Code CLI (primary)
├── .claude-plugin/   # Claude Code plugin system
├── .cursor/          # Cursor IDE
├── .codex/           # Codex CLI
├── .codex-plugin/    # Codex macOS app
├── .opencode/        # OpenCode
├── .kiro/            # Kiro
├── .trae/            # Trae IDE
└── .antigravity/     # Antigravity IDE (via flattened rules)
```

### Platform-Specific Adaptations

| Platform | Hooks | Commands | Agents | Rules | Notes |
|----------|-------|----------|--------|-------|-------|
| Claude Code | 15 events | 60 | 30 | 34 | Primary target |
| Cursor | 15 events (DRY adapter) | Shared | Shared | Flattened | DRY adapter pattern reuses Claude hooks |
| Codex | Reference config | Subset | Subset | Embedded | macOS app + CLI |
| OpenCode | 11 events | 31 | Shared | Shared | Full plugin support |
| Antigravity | Limited | Limited | Limited | Flattened into single file | Rules must be flattened |

### Key Patterns

1. **DRY Adapter Pattern (Cursor)**: Rather than duplicating hooks, Cursor config references the same hook scripts but adapts the event model. This avoids maintaining parallel implementations.

2. **Flattened Rules (Antigravity)**: Some IDEs don't support directory-based rules. ECC flattens its rules hierarchy into single files for these platforms.

3. **Plugin vs. Manual Install**: Claude Code and OpenCode get full plugin support. Other platforms require manual component copying.

4. **Shared Core**: Agents, skills, and commands are shared across platforms. Only the hook/config layer differs per platform.

## Current WG Approach

WG is **Claude Code only** with no cross-platform support:

- Plugin structure targets `.claude-plugin/` exclusively
- Hooks use Python scripts (via `_python.sh` shim for cross-OS compatibility)
- No Cursor, Codex, OpenCode, or other IDE configurations
- Cross-OS support (Windows/macOS/Linux) via `_python.sh` and `tempfile.gettempdir()`

## Assessment: Should WG Go Cross-Platform?

### Arguments For

- **Market reach**: Cursor has a massive user base; supporting it expands addressable market
- **Low-hanging fruit**: Commands and agents are markdown — they work anywhere with minimal adaptation
- **Competitive pressure**: If ECC supports 5 platforms, users may choose it for portability alone

### Arguments Against

- **Complexity tax**: Each platform has different event models, tool APIs, and configuration formats
- **Dilution risk**: Our strength is deep integration (smaht, crew, gates) that depends on Claude Code's specific capabilities
- **Maintenance burden**: 5x the config surface area to maintain and test
- **Architecture mismatch**: Our Python hook scripts, DomainStore, and SqliteStore are tightly integrated with Claude Code's plugin system

### Recommendation: Selective, Layered Approach

**Phase 1 — Cross-OS hardening (already done)**
- `_python.sh` shim for Python resolution
- `tempfile.gettempdir()` instead of hardcoded `/tmp`
- `${CLAUDE_PLUGIN_ROOT}` for all paths

**Phase 2 — Portable knowledge layer**
- Skills (markdown) and commands (markdown) are inherently portable
- Consider a `wicked-garden-lite` package that exports just skills + commands for other platforms
- No hooks, no Python scripts, no DomainStore — just the knowledge

**Phase 3 — Cursor adapter (if demand exists)**
- Create `.cursor/` config that references our commands and agents
- Adapt hook events using DRY adapter pattern (like ECC does)
- Accept that crew/smaht/gates won't work in Cursor — offer degraded mode

**Phase 4 — Codex/OpenCode (only if justified)**
- Only pursue if marketplace demand is clear
- Same portable layer approach as Phase 2

## Specific Lessons to Adopt

### 1. DRY Adapter Pattern

ECC's approach of writing hooks once and adapting per platform is smart. If we ever go cross-platform:

```
hooks/
├── scripts/          # Shared hook implementations (Python)
├── hooks.json        # Claude Code event bindings
├── cursor.json       # Cursor event bindings → same scripts
└── opencode.json     # OpenCode event bindings → same scripts
```

### 2. Rules as Portable Artifacts

ECC's rules system (`rules/common/` + `rules/{language}/`) is inherently portable — plain markdown files with guidelines. We could adopt a similar extractable rules system that works in any IDE's configuration.

### 3. Graceful Degradation Tiers

Document what works where:

| Capability | Claude Code | Cursor | Codex | Standalone |
|------------|------------|--------|-------|------------|
| Skills (knowledge) | Full | Full | Full | Read manually |
| Commands | Full | Adapted | Subset | N/A |
| Agents | Full | Full | Subset | N/A |
| Hooks | Full | Adapted events | Limited | N/A |
| Crew workflow | Full | N/A | N/A | N/A |
| smaht context | Full | N/A | N/A | N/A |
| Gate enforcement | Full | N/A | N/A | N/A |
| DomainStore | Full | N/A | N/A | N/A |

### 4. Installation Script

ECC provides `install.sh` and `install.ps1` for manual setup. If we offer a portable layer, a similar installer would reduce friction:

```bash
# Hypothetical
curl -fsSL https://wicked.garden/install.sh | sh -s -- --platform cursor
```

## Key Takeaway

ECC's cross-platform breadth is impressive but shallow — most platforms get degraded functionality. Our deep Claude Code integration is a stronger foundation. The pragmatic move is to **keep Claude Code as primary** while making our knowledge layer (skills, commands) exportable for users who also work in other IDEs.

Don't chase platform count. Chase depth of integration on our primary platform while keeping the knowledge layer portable.
