---
name: architecture-review
title: Agentic Architecture Review
description: Comprehensive review of an existing agentic system with framework detection and remediation roadmap
type: review
difficulty: intermediate
estimated_minutes: 15
---

# Agentic Architecture Review

This scenario validates that wicked-agentic can analyze an existing agentic codebase, detect the framework, map agent topology, identify issues, and produce an actionable remediation roadmap.

## Setup

Create a LangChain-based customer support agent system with common architectural issues:

```bash
mkdir -p ~/test-wicked-agentic/support-bot/src/agents
cd ~/test-wicked-agentic/support-bot

# Create a basic requirements file
cat > requirements.txt <<'EOF'
langchain==0.1.0
langchain-openai==0.0.5
openai==1.0.0
EOF

# Create orchestrator agent
cat > src/agents/orchestrator.py <<'EOF'
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain.tools import Tool
from src.agents.classifier import classify_intent
from src.agents.responder import generate_response
from src.agents.escalator import check_escalation

llm = ChatOpenAI(model="gpt-4")

def run_support_workflow(user_message: str) -> str:
    intent = classify_intent(user_message)
    response = generate_response(user_message, intent)
    if check_escalation(response):
        # No HITL gate here - just auto-escalates
        return f"Escalating to human: {response}"
    return response
EOF

# Create classifier with circular dependency
cat > src/agents/classifier.py <<'EOF'
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4")

def classify_intent(message: str) -> str:
    # No input validation
    result = llm.invoke(f"Classify this support message: {message}")
    return result.content
EOF

# Create responder
cat > src/agents/responder.py <<'EOF'
import subprocess
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4")

def generate_response(message: str, intent: str) -> str:
    # CRITICAL: Shell execution without sandbox or HITL
    if intent == "run_diagnostics":
        result = subprocess.run(message, shell=True, capture_output=True)
        return result.stdout.decode()

    response = llm.invoke(f"Respond to: {message} (intent: {intent})")
    return response.content
EOF
```

## Steps

### 1. Run Full Architecture Review

```bash
/wicked-agentic:review ~/test-wicked-agentic/support-bot
```

**Expected**:
- Framework detection runs and identifies LangChain (confidence >= 0.8)
- Agent topology analysis maps 3 agents (orchestrator, classifier, responder)
- Architecture assessment spawns `wicked-agentic:architect` agent
- Safety review spawns `wicked-agentic:safety-reviewer` agent
- Performance analysis spawns `wicked-agentic:performance-analyst` agent
- Pattern scorer runs against topology
- Unified report produced

### 2. Verify Framework Detection

The framework detection section should show:

```
## Framework Detection

**Primary**: LangChain (confidence: 85%+)
**Secondary**: OpenAI (confidence: 30%+)
```

### 3. Verify Agent Topology

The topology section should identify:
- 3 agents with their files and responsibilities
- Sequential control flow pattern
- `responder` agent has `subprocess` tool (critical risk)

### 4. Verify Safety Findings

The safety section should flag:

```
## Safety Audit

### Critical Vulnerabilities
- shell command execution in responder.py without sandbox or HITL gate
- No input validation before passing user message to subprocess

### Required Safeguards
- Human-in-the-loop gate for any diagnostic operations
- Input sanitization before subprocess calls
- Sandboxed execution environment
```

### 5. Quick Review Mode

```bash
/wicked-agentic:review ~/test-wicked-agentic/support-bot --quick
```

**Expected**:
- Structural review only (no deep agent spawning)
- Framework and topology reported
- No safety/performance deep dives
- Faster response (< 30 seconds)

### 6. Save Review to File

```bash
/wicked-agentic:review ~/test-wicked-agentic/support-bot --output ~/test-wicked-agentic/review-report.md
```

**Expected**:
- Full review runs as normal
- Report written to specified file
- Confirmation message: "Report written to ~/test-wicked-agentic/review-report.md"
- Brief summary shown inline (score, critical issue count)

## Expected Outcome

```markdown
# Agentic Architecture Review

**Project**: support-bot
**Framework**: LangChain v0.1.0
**Overall Score**: 4-5/10

## Executive Summary

System has a critical unprotected shell execution path in responder.py.
No human-in-the-loop gates for high-risk operations.

Key metrics:
- Agent count: 3
- Architecture pattern: Sequential chain
- Critical issues: 1 (shell execution without HITL)
- High severity issues: 2+

## Remediation Roadmap

**Phase 1: Critical Fixes** (1-2 days)
1. Add sandbox and HITL gate to subprocess call in responder.py
2. Add input validation before any shell-related code paths
```

## Success Criteria

- [ ] Framework detected as LangChain with >= 80% confidence
- [ ] All 3 agents identified with correct file paths
- [ ] Critical shell execution issue flagged as Critical severity
- [ ] Safety reviewer spawned via Task tool (not inline)
- [ ] Architect agent spawned via Task tool (not inline)
- [ ] Remediation roadmap has at least Phase 1 with specific fixes
- [ ] Quick mode (`--quick`) skips deep agent analysis
- [ ] `--output` flag writes report to file
- [ ] Overall score < 7/10 given the critical vulnerability

## Value Demonstrated

**Problem solved**: Agentic systems often ship with dangerous tool access patterns that aren't caught in standard code review. A reviewer unfamiliar with agent security may miss that `subprocess.run(user_input, shell=True)` inside an agent tool is a remote code execution vulnerability.

**Real-world value**:
- Catches critical agentic security patterns that static analysis misses
- Framework-aware review understands how agents communicate
- Topology analysis reveals trust boundary violations
- Remediation roadmap prioritizes fixes by risk, not effort

This replaces manual architecture review where reviewers check code without understanding agentic patterns, missing issues like missing HITL gates, circular agent dependencies, and prompt injection vulnerabilities.
