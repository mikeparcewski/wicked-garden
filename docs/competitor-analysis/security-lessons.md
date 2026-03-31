# Security Lessons from Everything Claude Code

> Competitive analysis: `affaan-m/everything-claude-code` (ECC) vs `wicked-garden` (WG)
> Date: 2026-03-30

## ECC's Security Posture

ECC has a comprehensive security guide (`the-security-guide.md`) that covers agentic security as infrastructure-level concern. Key components:

### 1. AgentShield Scanning Tool

ECC integrates **AgentShield**, an automated security scanner:
- 1,282 tests with 98% coverage
- 102 static analysis rules across 5 categories
- Scans for secrets, permission auditing, hook injection analysis
- Output formats: terminal, JSON, Markdown, HTML

**WG gap**: We have no equivalent security scanning tool. Our `platform:security-engineer` agent performs manual review but has no automated scanning infrastructure.

### 2. Secret Detection in Hooks

ECC has a `PreToolUse` hook that scans prompts for secrets before they reach the model:
- Detects API keys, tokens, passwords in user input
- Blocks submission of sensitive data
- Runs on every tool invocation

**WG gap**: Our PreToolUse hooks validate task creation and guard Write/Edit, but don't scan for secrets. We fail-open by design, which is correct for availability but leaves a security gap.

### 3. Deny Rules for Sensitive Paths

ECC documents explicit deny rules:
- Block reads from `~/.ssh`, `~/.aws`, `.env` files
- Block dangerous bash commands: `curl|bash`, `ssh`, `scp`, `nc`
- Restrict writes outside designated workspace
- Deny production environment access

**WG gap**: We mention security in CLAUDE.md (quote variables, use `tempfile.gettempdir()`, use `${CLAUDE_PLUGIN_ROOT}`) but don't have explicit deny rules.

### 4. Supply Chain Security

ECC treats skills, hooks, and MCP configs as supply-chain artifacts:
- 36% of 3,984 public skills contained prompt injection
- 1,467 malicious payloads identified
- Recommends scanning all imported components

**WG gap**: Our `wg-check` validates structure but doesn't scan for injection patterns.

## ECC's Security Framework (Key Concepts)

### Simon Willison's Lethal Trifecta

Three conditions that create dangerous attack surfaces when combined:
1. **Private/sensitive data access**
2. **Untrusted content ingestion**
3. **External communication capabilities**

WG's smaht context assembly touches all three when it intercepts prompts and routes to adapters. We should explicitly audit our trifecta exposure.

### Least Agency Principle

> "The safety boundary is the policy between model and action, not the system prompt."

ECC recommends required approvals before:
- Unsandboxed shell execution
- Network egress
- Reading secret-bearing paths
- Writes outside the repository
- Workflow dispatch or deployment

### Memory Poisoning Risk

ECC documents memory poisoning as a real threat:
- Persistent memory can store hostile payloads
- Payloads can "plant fragments, wait, then assemble later"
- 31 companies across 14 industries affected

**WG relevance**: Our wicked-mem stores cross-session data. We should consider:
- Memory sanitization on ingest
- Separation of project memory from user-global memory
- Memory rotation after untrusted runs

## What We Should Adopt

### Tier 1: High Priority

#### 1.1 Secret Detection Hook

Add a `PreToolUse` hook that scans for common secret patterns before tool execution:

```python
# hooks/scripts/secret_scanner.py
PATTERNS = [
    r'(?:api[_-]?key|token|secret|password)\s*[=:]\s*["\']?[a-zA-Z0-9]{16,}',
    r'(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}',  # AWS keys
    r'ghp_[a-zA-Z0-9]{36}',                     # GitHub PATs
    r'sk-[a-zA-Z0-9]{48}',                       # OpenAI/Anthropic keys
]
```

This fits our fail-open philosophy — warn but don't block by default.

#### 1.2 Supply Chain Scanning in wg-check

Enhance `/wg-check` to scan for:
- Prompt injection patterns in skill/command markdown
- Suspicious shell commands in hook scripts
- Overly broad tool permissions in agent definitions
- Hidden Unicode characters (zero-width, bidi overrides)

#### 1.3 Memory Sanitization

Add sanitization to wicked-mem ingest:
- Strip hidden Unicode before storage
- Flag entries containing shell commands or URL patterns
- Separate project-scoped from global memory

### Tier 2: Medium Priority

#### 2.1 Sensitive Path Deny List

Document and optionally enforce deny rules for common sensitive paths:

```json
{
  "deny_read": ["~/.ssh", "~/.aws", "~/.gnupg", ".env", ".env.local"],
  "deny_write": ["outside workspace"],
  "deny_commands": ["curl|bash", "wget|sh", "ssh", "scp"]
}
```

This could be a configurable security profile in the platform domain.

#### 2.2 Security Audit Skill

Create a `platform:security-audit` ref that documents:
- How to audit trifecta exposure in a project
- Common agentic attack vectors
- Checklist for production agent deployments
- MCP server security assessment criteria

#### 2.3 Process Control Documentation

ECC's guidance on kill switches and heartbeat monitoring is practical:
- Use SIGKILL (not SIGTERM) for immediate stops
- Kill process groups, not just parent
- Implement heartbeat-based dead-man switches
- Auto-terminate on 30-second check-in stalls

### Tier 3: Nice-to-Have

#### 3.1 Container Isolation Guidance

ECC documents Docker-based isolation for untrusted work:

```yaml
cap_drop:
  - ALL
networks:
  agent-internal:
    internal: true
```

We could document this in a platform skill ref for users running agents in production.

#### 3.2 Observability Logging

ECC recommends structured logging for all tool calls:

```json
{
  "timestamp": "...",
  "session_id": "...",
  "tool": "Bash",
  "approval": "blocked",
  "risk_score": 0.94
}
```

Our hook infrastructure could emit structured logs, useful for security teams.

## Current WG Security Strengths

We shouldn't overlook what we already do well:

1. **Fail-open design** — Hooks never block the user unexpectedly
2. **`${CLAUDE_PLUGIN_ROOT}` enforcement** — No hardcoded paths
3. **`_python.sh` shim** — Cross-platform Python resolution prevents path injection
4. **Shell variable quoting** — Enforced in CLAUDE.md
5. **Gate enforcement** — Quality gates prevent unsafe code from advancing through crew phases
6. **Graceful degradation** — Plugin works standalone with no external dependencies
7. **Banned reviewers** — `just-finish-auto`, `fast-pass` patterns rejected in gate enforcement

## Risk Assessment

| Attack Vector | ECC Defense | WG Defense | Gap |
|--------------|------------|-----------|-----|
| Secret leakage | Hook-based scanning | None | **HIGH** |
| Prompt injection in skills | AgentShield scanning | wg-check structural validation | **MEDIUM** |
| Memory poisoning | Documentation + rotation | wicked-mem stores unsanitized | **MEDIUM** |
| Sensitive path access | Explicit deny rules | No deny rules | **MEDIUM** |
| Supply chain (MCP) | MCP health checks | Integration-discovery (no scanning) | **LOW** |
| Process escape | Kill switch + heartbeat | Not applicable (plugin scope) | **LOW** |

## Action Plan

1. **Immediate**: Add secret pattern scanning to a PreToolUse hook
2. **Next release**: Enhance wg-check with injection pattern detection
3. **Next release**: Add memory sanitization to wicked-mem ingest
4. **Backlog**: Create platform:security-audit skill with comprehensive guidance
5. **Backlog**: Document sensitive path deny list as configurable security profile
