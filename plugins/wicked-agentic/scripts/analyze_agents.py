#!/usr/bin/env python3
"""
Agent topology analysis for agentic codebases.

Extracts agent definitions, classifies roles, maps communication patterns,
and identifies structural characteristics like nesting depth and tool sharing.

Usage:
    python3 analyze_agents.py --path DIR [--framework NAME]
"""

import ast
import json
import os
import re
import sys
import time
from pathlib import Path

EXCLUDE_DIRS = {
    "node_modules", "venv", ".venv", "__pycache__", "dist", "build",
    ".git", ".tox", ".mypy_cache", ".pytest_cache",
}

ROLE_KEYWORDS = {
    "research": ["search", "research", "gather", "find", "retrieve", "scrape"],
    "analysis": ["analyze", "evaluate", "assess", "review", "score", "classify"],
    "coordination": ["supervisor", "manager", "orchestrat", "coordinate", "router", "planner"],
    "execution": ["execute", "perform", "run", "worker", "do", "process"],
    "safety": ["safety", "validate", "check", "guard", "moderate", "filter"],
    "synthesis": ["synthesize", "combine", "summarize", "aggregate", "merge", "report"],
    "creation": ["write", "create", "generate", "compose", "draft", "author"],
}


def find_python_files(root: str, max_files: int = 500) -> list:
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            if f.endswith(".py"):
                files.append(os.path.join(dirpath, f))
                if len(files) >= max_files:
                    return files
    return files


def extract_agents_generic(filepath: str) -> list:
    """Extract agent-like class/function definitions from any Python file."""
    agents = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except (SyntaxError, ValueError, OSError):
        return agents

    for node in ast.walk(tree):
        # Classes with "Agent" in the name
        if isinstance(node, ast.ClassDef) and "agent" in node.name.lower():
            agents.append({
                "name": node.name,
                "type": "class",
                "file": filepath,
                "line": node.lineno,
                "role": classify_role(node.name, _get_docstring(node)),
                "tools": _extract_tool_refs(node),
                "confidence": 0.7,
            })

        # Functions decorated with @agent or similar
        if isinstance(node, ast.FunctionDef):
            decorators = _get_decorator_names(node)
            if any(d in ("agent", "crew", "tool") for d in decorators):
                agents.append({
                    "name": node.name,
                    "type": "decorated_function",
                    "decorator": [d for d in decorators if d in ("agent", "crew", "tool")][0],
                    "file": filepath,
                    "line": node.lineno,
                    "role": classify_role(node.name, _get_docstring(node)),
                    "tools": _extract_tool_refs(node),
                    "confidence": 0.9,
                })

        # Agent() instantiation calls
        if isinstance(node, ast.Call):
            func_name = _get_call_name(node)
            if func_name and "agent" in func_name.lower():
                name = _infer_agent_name(node, source, filepath)
                agents.append({
                    "name": name,
                    "type": "instantiation",
                    "constructor": func_name,
                    "file": filepath,
                    "line": node.lineno,
                    "role": classify_role(name, _extract_kwargs_str(node, "role", "goal", "description")),
                    "tools": _extract_tools_kwarg(node),
                    "kwargs": _extract_kwargs_str(node, "role", "goal", "backstory", "model"),
                    "confidence": 0.8,
                })

    return agents


def classify_role(name: str, context: str = "") -> str:
    """Classify agent role based on name and context."""
    text = f"{name} {context}".lower()
    scores = {}
    for role, keywords in ROLE_KEYWORDS.items():
        scores[role] = sum(1 for kw in keywords if kw in text)
    if max(scores.values()) == 0:
        return "unknown"
    return max(scores, key=scores.get)


def map_communication(agents: list) -> dict:
    """Build a communication graph from agent references."""
    agent_names = {a["name"].lower() for a in agents}
    edges = []

    for agent in agents:
        filepath = agent["file"]
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
        except OSError:
            continue

        for other_name in agent_names:
            if other_name == agent["name"].lower():
                continue
            if other_name in source.lower():
                edges.append({
                    "from": agent["name"],
                    "to": other_name,
                    "file": filepath,
                })

    # Detect patterns
    nodes = [a["name"] for a in agents]
    pattern = "unknown"
    if not edges:
        pattern = "isolated"
    elif _has_cycle(nodes, edges):
        pattern = "circular"
    elif _is_hierarchical(nodes, edges):
        pattern = "hierarchical"
    elif _is_sequential(nodes, edges):
        pattern = "sequential"
    else:
        pattern = "collaborative"

    return {
        "nodes": nodes,
        "edges": edges,
        "pattern": pattern,
    }


def analyze(root: str, framework: str = None) -> dict:
    """Run full agent analysis."""
    start = time.time()
    root = os.path.abspath(root)
    files = find_python_files(root)

    all_agents = []
    for f in files:
        all_agents.extend(extract_agents_generic(f))

    # Deduplicate by name+file
    seen = set()
    unique = []
    for a in all_agents:
        key = (a["name"], a["file"])
        if key not in seen:
            seen.add(key)
            unique.append(a)

    comm_graph = map_communication(unique)

    # Collect shared tools
    tool_usage = {}
    for agent in unique:
        for tool in agent.get("tools", []):
            tool_usage.setdefault(tool, []).append(agent["name"])
    shared_tools = {t: agents for t, agents in tool_usage.items() if len(agents) > 1}

    # Role distribution
    role_dist = {}
    for a in unique:
        role = a.get("role", "unknown")
        role_dist[role] = role_dist.get(role, 0) + 1

    return {
        "agents": unique,
        "agent_count": len(unique),
        "communication": comm_graph,
        "shared_tools": shared_tools,
        "role_distribution": role_dist,
        "stats": {
            "files_scanned": len(files),
            "duration_ms": int((time.time() - start) * 1000),
        },
    }


# --- Helpers ---

def _get_decorator_names(node: ast.FunctionDef) -> list:
    names = []
    for d in node.decorator_list:
        if isinstance(d, ast.Name):
            names.append(d.id)
        elif isinstance(d, ast.Attribute):
            names.append(d.attr)
        elif isinstance(d, ast.Call):
            if isinstance(d.func, ast.Name):
                names.append(d.func.id)
            elif isinstance(d.func, ast.Attribute):
                names.append(d.func.attr)
    return names


def _get_call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _get_docstring(node) -> str:
    if node.body and isinstance(node.body[0], ast.Expr):
        if isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            return node.body[0].value.value
    return ""


def _extract_tool_refs(node) -> list:
    """Extract tool references from a class or function body."""
    tools = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            val = child.value.lower()
            if "tool" in val and len(child.value) < 50:
                tools.append(child.value)
    return tools[:10]


def _extract_tools_kwarg(node: ast.Call) -> list:
    """Extract tools from Agent(tools=[...]) kwarg."""
    for kw in node.keywords:
        if kw.arg == "tools":
            if isinstance(kw.value, ast.List):
                items = []
                for elt in kw.value.elts:
                    if isinstance(elt, ast.Name):
                        items.append(elt.id)
                    elif isinstance(elt, ast.Constant):
                        items.append(str(elt.value))
                return items
    return []


def _extract_kwargs_str(node: ast.Call, *keys) -> str:
    """Extract string kwargs from a Call node."""
    parts = []
    for kw in node.keywords:
        if kw.arg in keys and isinstance(kw.value, ast.Constant):
            parts.append(str(kw.value.value))
    return " ".join(parts)


def _infer_agent_name(node: ast.Call, source: str, filepath: str) -> str:
    """Try to infer agent name from variable assignment or kwargs."""
    for kw in node.keywords:
        if kw.arg in ("name", "role") and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    # Fall back to variable name from assignment context
    lines = source.split("\n")
    if node.lineno <= len(lines):
        line = lines[node.lineno - 1]
        match = re.match(r"(\w+)\s*=", line)
        if match:
            return match.group(1)
    return f"agent_at_{Path(filepath).stem}_{node.lineno}"


def _has_cycle(nodes: list, edges: list) -> bool:
    adj = {n: [] for n in nodes}
    for e in edges:
        if e["from"] in adj:
            adj[e["from"]].append(e["to"])
    visited = set()
    rec_stack = set()

    def dfs(node):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                return True
        rec_stack.discard(node)
        return False

    for n in nodes:
        if n not in visited:
            if dfs(n):
                return True
    return False


def _is_hierarchical(nodes: list, edges: list) -> bool:
    in_degree = {n: 0 for n in nodes}
    for e in edges:
        to = e["to"]
        if to in in_degree:
            in_degree[to] += 1
    roots = [n for n, d in in_degree.items() if d == 0]
    return len(roots) == 1 and len(edges) >= len(nodes) - 1


def _is_sequential(nodes: list, edges: list) -> bool:
    if len(edges) != len(nodes) - 1:
        return False
    out_degree = {}
    for e in edges:
        out_degree[e["from"]] = out_degree.get(e["from"], 0) + 1
    return all(d <= 1 for d in out_degree.values())


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze agent topology")
    parser.add_argument("--path", default=".", help="Directory to scan")
    parser.add_argument("--framework", default=None, help="Framework hint")
    args = parser.parse_args()

    result = analyze(args.path, framework=args.framework)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
