# Test Scenarios for wicked-startah

This directory contains real-world test scenarios that validate functionality and demonstrate the value of wicked-startah.

## Scenario Overview

| Scenario | Type | Difficulty | Time | Purpose |
|----------|------|------------|------|---------|
| [01-fresh-install.md](01-fresh-install.md) | Integration | Basic | 10 min | Validates installation flow and first-session experience |
| [02-multi-ai-design-review.md](02-multi-ai-design-review.md) | Workflow | Advanced | 20 min | Demonstrates multi-model design review with kanban |
| [03-code-review-comparison.md](03-code-review-comparison.md) | Feature | Intermediate | 15 min | Tests multi-model code review and consensus analysis |
| [04-mcp-server-integration.md](04-mcp-server-integration.md) | Integration | Intermediate | 15 min | Validates MCP server configuration and functionality |

## Running Scenarios

### Prerequisites

**Required:**
- Claude Code installed
- wicked-garden marketplace added
- wicked-startah plugin installed

**Optional (for multi-AI scenarios):**
- Gemini CLI installed and authenticated
- Codex CLI installed and authenticated
- OpenCode CLI installed and authenticated
- wicked-kanban plugin installed (for scenarios 02-03)

### Execution Order

1. **Start with 01-fresh-install.md** - Validates basic installation
2. **Then 04-mcp-server-integration.md** - Confirms MCP servers work
3. **Next 03-code-review-comparison.md** - Tests AI CLI skills (works with Claude only)
4. **Finally 02-multi-ai-design-review.md** - Tests full workflow integration

## What Each Scenario Tests

### 01: Fresh Installation
**Tests:**
- Plugin installation process
- MCP server auto-configuration
- SessionStart hook execution
- First-session setup prompt
- Setup marker behavior

**Value:** Proves zero-configuration onboarding experience

### 02: Multi-AI Design Review
**Tests:**
- Integration with wicked-kanban
- Multiple AI model coordination
- Shared context management
- Consensus identification
- Synthesis and ADR creation

**Value:** Proves multi-model collaboration for design decisions

### 03: Code Review Comparison
**Tests:**
- AI CLI integrations (gemini, codex, opencode)
- Multi-model code analysis
- Consensus vs. unique insights
- Prioritization based on agreement

**Value:** Proves high-confidence code review through consensus

### 04: MCP Server Integration
**Tests:**
- MCP server configuration
- context7 functionality (documentation retrieval)
- atlassian authentication flow
- Error handling
- Version strategy (@latest)

**Value:** Proves zero-config access to essential MCP servers

## Success Metrics

All scenarios must demonstrate:
- **Functional correctness** - All features work as documented
- **Real-world applicability** - Scenarios reflect actual use cases
- **Objective verification** - Success criteria can be checked
- **Clear value proposition** - Obvious benefit over manual setup

## Notes

### AI CLI Availability
Scenarios 02 and 03 work with Claude alone but are enhanced with additional AI CLIs:
- **Claude only:** Scenarios still work; you get documentation/guides
- **+ Gemini:** Get Google's perspective on reviews
- **+ Codex:** Get OpenAI's code-focused analysis
- **+ OpenCode:** Get multi-provider flexibility

### MCP Server Authentication
Scenario 04 (atlassian) requires authentication. If not authenticated:
- Test verifies that auth is required (expected behavior)
- Instructions provided for authentication setup
- context7 works without auth and is fully testable

### Time Estimates
- Times assume Claude only (no additional AI CLIs)
- Add 2-3 minutes per additional AI model
- First-time MCP authentication adds 5 minutes

## Maintenance

When updating scenarios:
1. Keep real-world focus (no toy examples)
2. Ensure success criteria are objectively verifiable
3. Update time estimates based on actual runs
4. Test with Claude-only configuration (baseline)
5. Test with full AI CLI suite (enhanced experience)
