#!/usr/bin/env python3
"""
Framework detection for agentic codebases.

Identifies which agentic framework(s) are in use by scanning imports,
dependency files, config files, and code patterns. Returns JSON with
framework name, confidence score, and evidence.

Usage:
    python3 detect_framework.py [--path DIR] [--quick] [--threshold 0.6]
"""

import ast
import json
import os
import re
import sys
import time
from pathlib import Path

FRAMEWORK_SIGNATURES = {
    "google-adk": {
        "imports": ["google.adk", "google.genai", "google_genai"],
        "config_files": ["agent.yaml", "adk.yaml"],
        "patterns": [
            r"from google\.adk import",
            r"from google\.genai import",
            r"@agent\.tool",
            r"Agent\([^)]*model\s*=",
        ],
        "dependencies": {
            "python": ["google-adk", "google-genai"],
            "node": ["@google/generative-ai"],
        },
    },
    "langchain": {
        "imports": ["langchain", "langchain_openai", "langchain_community", "langchain_core"],
        "config_files": [],
        "patterns": [
            r"from langchain import",
            r"from langchain_openai import",
            r"from langchain_community",
            r"from langchain_core",
            r"from langchain\.agents import",
            r"AgentExecutor\(",
            r"create_openai_tools_agent\(",
            r"ChatOpenAI\(",
        ],
        "dependencies": {
            "python": ["langchain", "langchain-openai", "langchain-community", "langchain-core"],
            "node": ["langchain", "@langchain/openai", "@langchain/community"],
        },
    },
    "langgraph": {
        "imports": ["langgraph", "langgraph.graph", "langgraph.prebuilt"],
        "config_files": ["langgraph.json"],
        "patterns": [
            r"from langgraph",
            r"StateGraph\(",
            r"\.add_node\(",
            r"\.add_edge\(",
            r"\.compile\(\)",
        ],
        "dependencies": {
            "python": ["langgraph"],
            "node": ["@langchain/langgraph"],
        },
    },
    "crewai": {
        "imports": ["crewai"],
        "config_files": ["crew.yaml", "crew.yml"],
        "patterns": [
            r"from crewai import",
            r"Agent\([^)]*role\s*=",
            r"Task\([^)]*description\s*=",
            r"Crew\([^)]*agents\s*=",
            r"@agent",
            r"@task",
        ],
        "dependencies": {"python": ["crewai"]},
    },
    "autogen": {
        "imports": ["autogen", "pyautogen"],
        "config_files": [],
        "patterns": [
            r"from autogen import",
            r"AssistantAgent\(",
            r"UserProxyAgent\(",
            r"ConversableAgent\(",
            r"GroupChat\(",
        ],
        "dependencies": {"python": ["pyautogen", "autogen"]},
    },
    "semantic-kernel": {
        "imports": ["semantic_kernel"],
        "config_files": [],
        "patterns": [
            r"from semantic_kernel import",
            r"import semantic_kernel",
            r"Kernel\(\)",
            r"@kernel_function",
        ],
        "dependencies": {
            "python": ["semantic-kernel"],
            "node": ["@microsoft/semantic-kernel"],
        },
    },
    "dspy": {
        "imports": ["dspy"],
        "config_files": [],
        "patterns": [
            r"import dspy",
            r"from dspy import",
            r"class\s+\w+\(dspy\.Module\)",
            r"dspy\.ChainOfThought",
            r"dspy\.Predict",
        ],
        "dependencies": {"python": ["dspy-ai", "dspy"]},
    },
    "pydantic-ai": {
        "imports": ["pydantic_ai"],
        "config_files": [],
        "patterns": [
            r"from pydantic_ai import",
            r"import pydantic_ai",
            r"agent\.run_sync\(",
        ],
        "dependencies": {"python": ["pydantic-ai"]},
    },
    "openai-agents-sdk": {
        "imports": ["openai.agents", "agents"],
        "config_files": [],
        "patterns": [
            r"from agents import Agent",
            r"from openai\.agents import",
            r"Runner\.run\(",
            r"@function_tool",
        ],
        "dependencies": {"python": ["openai-agents"]},
    },
    "llama-index": {
        "imports": ["llama_index"],
        "config_files": [],
        "patterns": [
            r"from llama_index import",
            r"from llama_index\.core import",
            r"from llama_index\.agent import",
            r"ReActAgent\.from_tools",
        ],
        "dependencies": {"python": ["llama-index"]},
    },
    "haystack": {
        "imports": ["haystack"],
        "config_files": [],
        "patterns": [
            r"from haystack import Pipeline",
            r"from haystack\.agents import",
            r"\.add_component\(",
        ],
        "dependencies": {"python": ["haystack-ai"]},
    },
    "mastra": {
        "imports": ["mastra", "@mastra/core"],
        "config_files": ["mastra.config.ts", "mastra.config.js"],
        "patterns": [
            r"from ['\"]@mastra/core['\"]",
            r"import.*from ['\"]@mastra",
            r"new Agent\(",
        ],
        "dependencies": {"node": ["@mastra/core"]},
    },
    "vercel-ai-sdk": {
        "imports": ["ai"],
        "config_files": [],
        "patterns": [
            r"from ['\"]ai['\"]",
            r"import.*streamText.*from ['\"]ai['\"]",
            r"import.*generateText.*from ['\"]ai['\"]",
            r"streamText\(",
            r"generateText\(",
        ],
        "dependencies": {"node": ["ai"]},
    },
}

EXCLUDE_DIRS = {
    "node_modules", "venv", ".venv", "__pycache__", "dist", "build",
    ".git", ".tox", "egg-info", ".mypy_cache", ".pytest_cache",
}


def find_source_files(root: str, quick: bool = False) -> list:
    """Find Python and TypeScript/JavaScript source files."""
    extensions = {".py", ".ts", ".tsx", ".js", ".jsx"}
    files = []
    max_files = 50 if quick else 500

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            if Path(f).suffix in extensions:
                files.append(os.path.join(dirpath, f))
                if len(files) >= max_files:
                    return files
    return files


def scan_imports(files: list) -> dict:
    """Scan Python files for framework imports using AST."""
    import_hits = {}

    for filepath in files:
        if not filepath.endswith(".py"):
            continue
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
            tree = ast.parse(source, filename=filepath)
        except (SyntaxError, ValueError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _record_import(import_hits, alias.name, filepath, node.lineno)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    _record_import(import_hits, node.module, filepath, node.lineno)

    return import_hits


def _record_import(hits: dict, module: str, filepath: str, line: int):
    """Record an import match against known frameworks."""
    for fw_name, sig in FRAMEWORK_SIGNATURES.items():
        for known_import in sig["imports"]:
            if module == known_import or module.startswith(known_import + "."):
                hits.setdefault(fw_name, []).append({
                    "type": "import",
                    "module": module,
                    "file": filepath,
                    "line": line,
                    "strength": 0.5,
                })


def scan_patterns(files: list) -> dict:
    """Scan source files for framework-specific code patterns."""
    pattern_hits = {}

    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue

        for fw_name, sig in FRAMEWORK_SIGNATURES.items():
            for pattern in sig["patterns"]:
                matches = list(re.finditer(pattern, content))
                for m in matches[:3]:  # cap at 3 per pattern per file
                    line = content[:m.start()].count("\n") + 1
                    pattern_hits.setdefault(fw_name, []).append({
                        "type": "pattern",
                        "pattern": pattern,
                        "file": filepath,
                        "line": line,
                        "match": m.group()[:80],
                        "strength": 0.3,
                    })

    return pattern_hits


def scan_dependencies(root: str) -> dict:
    """Check dependency files for framework packages."""
    dep_hits = {}
    dep_files = {
        "requirements.txt": "python",
        "pyproject.toml": "python",
        "setup.cfg": "python",
        "Pipfile": "python",
        "package.json": "node",
    }

    for filename, lang in dep_files.items():
        filepath = os.path.join(root, filename)
        if not os.path.isfile(filepath):
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue

        for fw_name, sig in FRAMEWORK_SIGNATURES.items():
            for dep in sig.get("dependencies", {}).get(lang, []):
                if dep in content:
                    dep_hits.setdefault(fw_name, []).append({
                        "type": "dependency",
                        "package": dep,
                        "file": filepath,
                        "strength": 0.5,
                    })

    return dep_hits


def scan_config_files(root: str) -> dict:
    """Check for framework-specific config files."""
    config_hits = {}

    for fw_name, sig in FRAMEWORK_SIGNATURES.items():
        for config_file in sig.get("config_files", []):
            for dirpath, _, filenames in os.walk(root):
                if any(d in dirpath for d in EXCLUDE_DIRS):
                    continue
                if config_file in filenames:
                    config_hits.setdefault(fw_name, []).append({
                        "type": "config",
                        "file": os.path.join(dirpath, config_file),
                        "strength": 0.4,
                    })

    return config_hits


def calculate_confidence(evidence: list) -> float:
    """
    Calculate confidence score from evidence list.

    Formula:
      evidence_strength: max individual strength (0.0-0.5)
      evidence_count: 1=0.1, 2-3=0.2, 4+=0.3
      evidence_diversity: types/3 * 0.2
    """
    if not evidence:
        return 0.0

    strength = max(e["strength"] for e in evidence)
    count = len(evidence)
    count_score = 0.1 if count == 1 else 0.2 if count <= 3 else 0.3
    types = len(set(e["type"] for e in evidence))
    diversity_score = min(types / 3.0, 1.0) * 0.2

    return min(1.0, strength + count_score + diversity_score)


def detect(root: str, quick: bool = False, threshold: float = 0.6) -> dict:
    """Run full detection pipeline."""
    start = time.time()
    root = os.path.abspath(root)

    files = find_source_files(root, quick=quick)
    if not files:
        return {
            "frameworks_detected": [],
            "primary_framework": None,
            "scan_stats": {
                "files_scanned": 0,
                "duration_ms": int((time.time() - start) * 1000),
            },
        }

    # Gather evidence from all sources
    import_hits = scan_imports(files)
    pattern_hits = {} if quick else scan_patterns(files)
    dep_hits = scan_dependencies(root)
    config_hits = scan_config_files(root)

    # Merge evidence per framework
    all_evidence = {}
    for source in [import_hits, pattern_hits, dep_hits, config_hits]:
        for fw, hits in source.items():
            all_evidence.setdefault(fw, []).extend(hits)

    # Score and filter
    results = []
    for fw_name, evidence in all_evidence.items():
        confidence = calculate_confidence(evidence)
        if confidence >= threshold:
            results.append({
                "name": fw_name,
                "confidence": round(confidence, 2),
                "evidence_count": len(evidence),
                "evidence": evidence[:10],  # cap detail output
            })

    results.sort(key=lambda x: x["confidence"], reverse=True)

    # Mark primary
    primary = results[0]["name"] if results else None
    for r in results:
        r["primary"] = r["name"] == primary

    return {
        "frameworks_detected": results,
        "primary_framework": primary,
        "scan_stats": {
            "files_scanned": len(files),
            "duration_ms": int((time.time() - start) * 1000),
        },
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Detect agentic frameworks")
    parser.add_argument("--path", default=".", help="Directory to scan")
    parser.add_argument("--quick", action="store_true", help="Fast scan (fewer files)")
    parser.add_argument("--threshold", type=float, default=0.6, help="Confidence threshold")
    args = parser.parse_args()

    result = detect(args.path, quick=args.quick, threshold=args.threshold)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
