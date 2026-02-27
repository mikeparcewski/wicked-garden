#!/usr/bin/env python3
"""
Anti-pattern detection and scoring for agentic codebases.

Scores agent implementations against known good patterns and anti-patterns.
Produces findings with severity, evidence, and recommendations.

Usage:
    python3 pattern_scorer.py --agents AGENTS_JSON [--framework NAME]
"""

import json
import os
import re
import sys
import time


ANTI_PATTERNS = {
    "god_agent": {
        "severity": "critical",
        "category": "architecture",
        "title": "God Agent: agent has too many responsibilities",
        "check": "check_god_agent",
        "recommendation": "Split into focused agents with single responsibilities. Each agent should have 1-3 tools and a clear role.",
        "skill_ref": "agentic-patterns:single-responsibility",
    },
    "missing_guardrails": {
        "severity": "critical",
        "category": "safety",
        "title": "Missing guardrails: unsafe tool access without validation",
        "check": "check_missing_guardrails",
        "recommendation": "Add input validation, output filtering, and approval gates for high-risk operations (file writes, API calls, database mutations).",
        "skill_ref": "trust-and-safety:guardrails",
    },
    "no_human_in_loop": {
        "severity": "high",
        "category": "safety",
        "title": "No human-in-the-loop for high-risk operations",
        "check": "check_no_human_in_loop",
        "recommendation": "Add explicit human approval gates before irreversible actions (deployments, data deletion, financial transactions).",
        "skill_ref": "trust-and-safety:human-oversight",
    },
    "deep_nesting": {
        "severity": "high",
        "category": "architecture",
        "title": "Deep agent nesting exceeds recommended depth",
        "check": "check_deep_nesting",
        "recommendation": "Flatten agent hierarchy to max 3 levels. Use parallel coordination instead of deep delegation chains.",
        "skill_ref": "agentic-patterns:flat-hierarchies",
    },
    "circular_dependency": {
        "severity": "high",
        "category": "architecture",
        "title": "Circular dependency between agents",
        "check": "check_circular_dependency",
        "recommendation": "Break cycles by introducing a coordinator agent or using message queues for async communication.",
        "skill_ref": "agentic-patterns:coordination",
    },
    "missing_error_handling": {
        "severity": "high",
        "category": "reliability",
        "title": "Agent lacks error handling or retry logic",
        "check": "check_missing_error_handling",
        "recommendation": "Add try/except blocks, retry logic with backoff, and fallback strategies for LLM call failures.",
        "skill_ref": "agentic-patterns:resilience",
    },
    "no_observability": {
        "severity": "medium",
        "category": "observability",
        "title": "Agent lacks logging or tracing",
        "check": "check_no_observability",
        "recommendation": "Add structured logging for agent decisions, tool invocations, and state transitions. Consider OpenTelemetry traces.",
        "skill_ref": "five-layer-architecture:governance",
    },
    "redundant_agents": {
        "severity": "medium",
        "category": "architecture",
        "title": "Multiple agents with overlapping responsibilities",
        "check": "check_redundant_agents",
        "recommendation": "Merge agents with similar roles or clarify distinct responsibilities to eliminate redundant LLM calls.",
        "skill_ref": "agentic-patterns:single-responsibility",
    },
    "context_bloat": {
        "severity": "medium",
        "category": "performance",
        "title": "Excessive context accumulation across agent chain",
        "check": "check_context_bloat",
        "recommendation": "Implement context compression, selective state passing, and summarization between agent handoffs.",
        "skill_ref": "context-engineering:optimization",
    },
    "sequential_bottleneck": {
        "severity": "medium",
        "category": "performance",
        "title": "Sequential operations that could be parallelized",
        "check": "check_sequential_bottleneck",
        "recommendation": "Identify independent agent tasks and run them in parallel using asyncio.gather() or framework-native parallelism.",
        "skill_ref": "agentic-patterns:parallelization",
    },
    "hardcoded_prompts": {
        "severity": "low",
        "category": "maintainability",
        "title": "Prompts hardcoded inline rather than templated",
        "check": "check_hardcoded_prompts",
        "recommendation": "Extract prompts to templates or configuration files for easier iteration and A/B testing.",
        "skill_ref": "context-engineering:prompt-design",
    },
    "missing_timeout": {
        "severity": "medium",
        "category": "reliability",
        "title": "LLM calls without timeout or token limits",
        "check": "check_missing_timeout",
        "recommendation": "Set max_tokens, timeout, and cost limits on all LLM calls to prevent runaway costs and hangs.",
        "skill_ref": "context-engineering:cost-models",
    },
}


def score(agents: list, communication: dict = None, framework: str = None) -> dict:
    """Score agents against all patterns. Returns findings list."""
    start = time.time()
    findings = []

    for pattern_id, pattern in ANTI_PATTERNS.items():
        checker = globals().get(pattern["check"])
        if not checker:
            continue
        matches = checker(agents, communication or {}, framework)
        for match in matches:
            findings.append({
                "id": f"AP-{len(findings)+1:03d}",
                "pattern": pattern_id,
                "severity": pattern["severity"],
                "category": pattern["category"],
                "title": pattern["title"],
                "description": match.get("description", ""),
                "locations": match.get("locations", []),
                "evidence": match.get("evidence", ""),
                "recommendation": pattern["recommendation"],
                "skill_ref": pattern["skill_ref"],
                "confidence": match.get("confidence", 0.8),
            })

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: severity_order.get(f["severity"], 4))

    by_severity = {}
    by_category = {}
    for f in findings:
        by_severity[f["severity"]] = by_severity.get(f["severity"], 0) + 1
        by_category[f["category"]] = by_category.get(f["category"], 0) + 1

    return {
        "findings": findings,
        "summary": {
            "total_findings": len(findings),
            "by_severity": by_severity,
            "by_category": by_category,
        },
        "stats": {
            "agents_scored": len(agents),
            "patterns_checked": len(ANTI_PATTERNS),
            "duration_ms": int((time.time() - start) * 1000),
        },
    }


# --- Pattern Checkers ---

def check_god_agent(agents, comm, fw) -> list:
    results = []
    for a in agents:
        tools = a.get("tools", [])
        if len(tools) > 5:
            results.append({
                "description": f"Agent '{a['name']}' has {len(tools)} tools (threshold: 5)",
                "locations": [{"file": a.get("file", ""), "line": a.get("line", 0), "agent": a["name"]}],
                "evidence": f"Tools: {', '.join(tools[:8])}{'...' if len(tools) > 8 else ''}",
                "confidence": min(0.5 + len(tools) * 0.05, 1.0),
            })
    return results


def check_missing_guardrails(agents, comm, fw) -> list:
    results = []
    dangerous_patterns = ["subprocess", "os.system", "exec(", "eval(", "shell=True", "rm ", "DROP TABLE"]
    for a in agents:
        filepath = a.get("file", "")
        if not filepath or not os.path.isfile(filepath):
            continue
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue
        for pattern in dangerous_patterns:
            if pattern in content:
                results.append({
                    "description": f"Agent '{a['name']}' uses dangerous operation '{pattern}' without visible guardrails",
                    "locations": [{"file": filepath, "agent": a["name"]}],
                    "evidence": f"Found '{pattern}' in agent source",
                    "confidence": 0.7,
                })
                break
    return results


def check_no_human_in_loop(agents, comm, fw) -> list:
    results = []
    high_risk_keywords = ["deploy", "delete", "drop", "send_email", "transfer", "payment", "publish"]
    for a in agents:
        tools = [t.lower() for t in a.get("tools", [])]
        risky = [t for t in tools if any(kw in t for kw in high_risk_keywords)]
        if risky:
            results.append({
                "description": f"Agent '{a['name']}' has high-risk tools without apparent human approval gate",
                "locations": [{"file": a.get("file", ""), "agent": a["name"]}],
                "evidence": f"High-risk tools: {', '.join(risky)}",
                "confidence": 0.6,
            })
    return results


def check_deep_nesting(agents, comm, fw) -> list:
    edges = comm.get("edges", [])
    if not edges:
        return []
    # Calculate max depth via BFS
    adj = {}
    for e in edges:
        adj.setdefault(e["from"], []).append(e["to"])
    in_degree = {}
    for e in edges:
        in_degree[e["to"]] = in_degree.get(e["to"], 0) + 1
    roots = [a["name"] for a in agents if in_degree.get(a["name"], 0) == 0]

    max_depth = 0
    for root in roots:
        depth = _bfs_depth(root, adj)
        max_depth = max(max_depth, depth)

    if max_depth > 3:
        return [{
            "description": f"Agent hierarchy depth is {max_depth} (recommended max: 3)",
            "locations": [{"agent": r} for r in roots],
            "evidence": f"Max delegation chain: {max_depth} levels",
            "confidence": 0.9,
        }]
    return []


def check_circular_dependency(agents, comm, fw) -> list:
    if comm.get("pattern") == "circular":
        return [{
            "description": "Circular dependency detected in agent communication graph",
            "locations": [{"agent": e["from"], "file": e.get("file", "")} for e in comm.get("edges", [])[:5]],
            "evidence": "Cycle found in directed agent graph",
            "confidence": 0.95,
        }]
    return []


def check_missing_error_handling(agents, comm, fw) -> list:
    results = []
    for a in agents:
        filepath = a.get("file", "")
        if not filepath or not os.path.isfile(filepath):
            continue
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue
        has_try = "try:" in content or "except" in content
        has_retry = "retry" in content.lower() or "backoff" in content.lower()
        if not has_try and not has_retry:
            results.append({
                "description": f"Agent '{a['name']}' has no visible error handling (no try/except or retry logic)",
                "locations": [{"file": filepath, "agent": a["name"]}],
                "evidence": "No try/except or retry/backoff patterns found",
                "confidence": 0.6,
            })
    return results


def check_no_observability(agents, comm, fw) -> list:
    results = []
    for a in agents:
        filepath = a.get("file", "")
        if not filepath or not os.path.isfile(filepath):
            continue
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue
        has_logging = any(kw in content for kw in ["logging", "logger", "log.", "print(", "trace", "opentelemetry", "span"])
        if not has_logging:
            results.append({
                "description": f"Agent '{a['name']}' has no logging, tracing, or observability",
                "locations": [{"file": filepath, "agent": a["name"]}],
                "evidence": "No logging/tracing imports or usage found",
                "confidence": 0.5,
            })
    return results


def check_redundant_agents(agents, comm, fw) -> list:
    results = []
    role_groups = {}
    for a in agents:
        role = a.get("role", "unknown")
        if role != "unknown":
            role_groups.setdefault(role, []).append(a)
    for role, group in role_groups.items():
        if len(group) > 2:
            names = [a["name"] for a in group]
            results.append({
                "description": f"{len(group)} agents share the '{role}' role: {', '.join(names)}",
                "locations": [{"file": a.get("file", ""), "agent": a["name"]} for a in group],
                "evidence": f"Role '{role}' assigned to {len(group)} agents",
                "confidence": 0.5,
            })
    return results


def check_context_bloat(agents, comm, fw) -> list:
    # Heuristic: long chains without summarization
    edges = comm.get("edges", [])
    if len(edges) > 5 and comm.get("pattern") in ("sequential", "hierarchical"):
        return [{
            "description": f"Long agent chain ({len(edges)} edges) risks context accumulation without compression",
            "locations": [],
            "evidence": f"Communication pattern: {comm.get('pattern')}, edges: {len(edges)}",
            "confidence": 0.5,
        }]
    return []


def check_sequential_bottleneck(agents, comm, fw) -> list:
    if comm.get("pattern") == "sequential" and len(agents) > 3:
        return [{
            "description": f"{len(agents)} agents in sequential chain; some may be parallelizable",
            "locations": [],
            "evidence": f"Sequential pattern with {len(agents)} agents",
            "confidence": 0.4,
        }]
    return []


def check_hardcoded_prompts(agents, comm, fw) -> list:
    results = []
    for a in agents:
        filepath = a.get("file", "")
        if not filepath or not os.path.isfile(filepath):
            continue
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue
        long_strings = re.findall(r'"""[^"]{200,}"""', content) + re.findall(r"'''[^']{200,}'''", content)
        if long_strings:
            results.append({
                "description": f"Agent '{a['name']}' has {len(long_strings)} long inline prompt(s)",
                "locations": [{"file": filepath, "agent": a["name"]}],
                "evidence": f"Found {len(long_strings)} string(s) >200 chars that may be prompts",
                "confidence": 0.4,
            })
    return results


def check_missing_timeout(agents, comm, fw) -> list:
    results = []
    for a in agents:
        filepath = a.get("file", "")
        if not filepath or not os.path.isfile(filepath):
            continue
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue
        has_llm_call = any(kw in content for kw in [".invoke(", ".run(", ".chat(", ".complete(", "openai.", "anthropic."])
        has_timeout = "timeout" in content or "max_tokens" in content
        if has_llm_call and not has_timeout:
            results.append({
                "description": f"Agent '{a['name']}' makes LLM calls without visible timeout or token limits",
                "locations": [{"file": filepath, "agent": a["name"]}],
                "evidence": "LLM call patterns found without timeout/max_tokens",
                "confidence": 0.5,
            })
    return results


def _bfs_depth(root, adj):
    depth = 0
    level = [root]
    visited = {root}
    while level:
        next_level = []
        for node in level:
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_level.append(neighbor)
        if next_level:
            depth += 1
        level = next_level
    return depth


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Score agent patterns")
    parser.add_argument("--agents", required=True, help="Path to agents JSON from analyze_agents.py")
    parser.add_argument("--framework", default=None, help="Framework name")
    args = parser.parse_args()

    with open(args.agents) as f:
        data = json.load(f)

    result = score(
        agents=data.get("agents", []),
        communication=data.get("communication", {}),
        framework=args.framework,
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
