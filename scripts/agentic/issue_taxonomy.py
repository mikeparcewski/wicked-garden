#!/usr/bin/env python3
"""
Issue taxonomy and report generation for agentic codebases.

Takes pattern scoring results and generates structured reports with
categorized findings, severity rankings, and prioritized recommendations.

Usage:
    python3 issue_taxonomy.py --findings FINDINGS_JSON [--format markdown|json]
"""

import json
import sys
import time
from datetime import datetime, timezone


SEVERITY_WEIGHTS = {
    "critical": 10,
    "high": 5,
    "medium": 2,
    "low": 0.5,
}

MATURITY_LEVELS = {
    1: {"name": "Prototype", "description": "Single agent, hardcoded prompts, no error handling"},
    2: {"name": "Functional", "description": "Multi-agent, basic orchestration, some error handling"},
    3: {"name": "Reliable", "description": "Error handling, monitoring, retry logic, structured prompts"},
    4: {"name": "Production", "description": "Safety gates, observability, cost controls, human oversight"},
    5: {"name": "Optimized", "description": "Self-healing, adaptive prompts, continuous improvement, full governance"},
}


def categorize(findings: list, agents: list = None, framework: dict = None) -> dict:
    """Build full taxonomy from findings."""
    start = time.time()

    # Group by category
    by_category = {}
    for f in findings:
        cat = f.get("category", "other")
        by_category.setdefault(cat, []).append(f)

    # Group by severity
    by_severity = {}
    for f in findings:
        sev = f.get("severity", "low")
        by_severity.setdefault(sev, []).append(f)

    # Calculate risk score
    risk_score = sum(SEVERITY_WEIGHTS.get(f["severity"], 0) for f in findings)

    # Assess maturity
    maturity = _assess_maturity(findings, agents or [])

    # Generate recommendations
    recommendations = _generate_recommendations(findings)

    # Status determination
    critical_count = len(by_severity.get("critical", []))
    high_count = len(by_severity.get("high", []))
    if critical_count > 0:
        status = "critical_issues"
    elif high_count > 2:
        status = "needs_work"
    elif high_count > 0:
        status = "acceptable"
    else:
        status = "good"

    return {
        "report_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "summary": {
            "total_issues": len(findings),
            "by_severity": {k: len(v) for k, v in by_severity.items()},
            "by_category": {k: len(v) for k, v in by_category.items()},
            "risk_score": round(risk_score, 1),
            "maturity_level": maturity["level"],
            "maturity_name": maturity["name"],
        },
        "framework": framework,
        "agent_count": len(agents) if agents else 0,
        "categories": {
            cat: {
                "findings": items,
                "count": len(items),
                "severity_breakdown": _severity_breakdown(items),
            }
            for cat, items in by_category.items()
        },
        "recommendations": recommendations,
        "maturity": maturity,
        "stats": {
            "duration_ms": int((time.time() - start) * 1000),
        },
    }


def render_markdown(taxonomy: dict) -> str:
    """Render taxonomy as markdown report."""
    lines = []
    summary = taxonomy["summary"]
    status_emoji = {
        "critical_issues": "!!",
        "needs_work": "!",
        "acceptable": "-",
        "good": "+",
    }

    lines.append("# Agentic Architecture Review")
    lines.append("")
    lines.append(f"**Status**: {taxonomy['status'].replace('_', ' ').title()} [{status_emoji.get(taxonomy['status'], '')}]")
    lines.append(f"**Generated**: {taxonomy['generated_at']}")
    if taxonomy.get("framework"):
        fw = taxonomy["framework"]
        lines.append(f"**Framework**: {fw.get('primary_framework', 'Unknown')}")
    lines.append(f"**Agents Analyzed**: {taxonomy.get('agent_count', 0)}")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"- **Total Issues**: {summary['total_issues']}")
    lines.append(f"- **Risk Score**: {summary['risk_score']}")
    lines.append(f"- **Maturity Level**: {summary['maturity_level']}/5 ({summary['maturity_name']})")
    lines.append("")

    sev = summary.get("by_severity", {})
    if sev:
        lines.append("| Severity | Count |")
        lines.append("|----------|-------|")
        for s in ["critical", "high", "medium", "low"]:
            if s in sev:
                lines.append(f"| {s.title()} | {sev[s]} |")
        lines.append("")

    # Findings by Category
    lines.append("## Findings")
    lines.append("")
    for cat, data in taxonomy.get("categories", {}).items():
        lines.append(f"### {cat.title()} ({data['count']} issues)")
        lines.append("")
        for f in data["findings"]:
            severity_badge = f"[{f['severity'].upper()}]"
            lines.append(f"#### {severity_badge} {f['title']}")
            lines.append("")
            if f.get("description"):
                lines.append(f"{f['description']}")
                lines.append("")
            if f.get("evidence"):
                lines.append(f"**Evidence**: {f['evidence']}")
                lines.append("")
            if f.get("locations"):
                for loc in f["locations"][:3]:
                    parts = []
                    if loc.get("file"):
                        parts.append(loc["file"])
                    if loc.get("line"):
                        parts.append(f"line {loc['line']}")
                    if loc.get("agent"):
                        parts.append(f"agent: {loc['agent']}")
                    if parts:
                        lines.append(f"- {', '.join(parts)}")
                lines.append("")
            if f.get("recommendation"):
                lines.append(f"**Recommendation**: {f['recommendation']}")
                lines.append("")
            lines.append("---")
            lines.append("")

    # Recommendations
    recs = taxonomy.get("recommendations", [])
    if recs:
        lines.append("## Remediation Roadmap")
        lines.append("")
        lines.append("| Priority | Action | Effort | Impact | Related |")
        lines.append("|----------|--------|--------|--------|---------|")
        for i, rec in enumerate(recs, 1):
            lines.append(
                f"| {i} | {rec['title']} | {rec.get('effort', 'medium')} | "
                f"{rec.get('impact', 'high')} | {', '.join(rec.get('related_findings', []))} |"
            )
        lines.append("")

    # Maturity Assessment
    mat = taxonomy.get("maturity", {})
    if mat:
        lines.append("## Maturity Assessment")
        lines.append("")
        lines.append(f"**Current Level**: {mat['level']}/5 - {mat['name']}")
        lines.append("")
        if mat.get("next_level_actions"):
            lines.append(f"**To reach Level {mat['level'] + 1}**:")
            lines.append("")
            for action in mat["next_level_actions"]:
                lines.append(f"- {action}")
            lines.append("")

    return "\n".join(lines)


def _assess_maturity(findings: list, agents: list) -> dict:
    """Assess maturity level based on findings."""
    severities = [f["severity"] for f in findings]
    categories = [f["category"] for f in findings]

    has_critical = "critical" in severities
    has_safety_issues = "safety" in categories
    has_observability_issues = "observability" in categories
    has_reliability_issues = "reliability" in categories

    if has_critical:
        level = 1
    elif has_safety_issues and has_reliability_issues:
        level = 2
    elif has_safety_issues or has_observability_issues:
        level = 3
    elif len(findings) > 0:
        level = 4
    else:
        level = 5

    mat = MATURITY_LEVELS[level]
    next_actions = []
    if level < 5:
        next_level = MATURITY_LEVELS[level + 1]
        if has_critical:
            next_actions.append("Fix all critical issues (god agents, missing guardrails)")
        if has_safety_issues:
            next_actions.append("Add human-in-the-loop gates for high-risk operations")
        if has_observability_issues:
            next_actions.append("Add structured logging and tracing to all agents")
        if has_reliability_issues:
            next_actions.append("Add error handling, retries, and timeouts to LLM calls")
        if not next_actions:
            next_actions.append(f"Achieve: {next_level['description']}")

    return {
        "level": level,
        "name": mat["name"],
        "description": mat["description"],
        "next_level_actions": next_actions,
    }


def _generate_recommendations(findings: list) -> list:
    """Generate prioritized recommendations from findings."""
    recs = []
    seen_patterns = set()

    for f in findings:
        pattern = f.get("pattern", "")
        if pattern in seen_patterns:
            continue
        seen_patterns.add(pattern)

        effort = "small" if f["severity"] in ("low",) else "medium" if f["severity"] in ("medium",) else "large"
        impact = "high" if f["severity"] in ("critical", "high") else "medium"

        recs.append({
            "title": f["recommendation"],
            "effort": effort,
            "impact": impact,
            "related_findings": [f["id"]],
            "skill_ref": f.get("skill_ref", ""),
        })

    # Sort: high impact + small effort first
    impact_order = {"high": 0, "medium": 1, "low": 2}
    effort_order = {"small": 0, "medium": 1, "large": 2}
    recs.sort(key=lambda r: (impact_order.get(r["impact"], 2), effort_order.get(r["effort"], 2)))

    return recs


def _severity_breakdown(items: list) -> dict:
    breakdown = {}
    for item in items:
        sev = item.get("severity", "low")
        breakdown[sev] = breakdown.get(sev, 0) + 1
    return breakdown


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate issue taxonomy")
    parser.add_argument("--findings", required=True, help="Path to findings JSON from pattern_scorer.py")
    parser.add_argument("--agents", default=None, help="Path to agents JSON from analyze_agents.py")
    parser.add_argument("--framework", default=None, help="Path to framework JSON from detect_framework.py")
    parser.add_argument("--format", choices=["markdown", "json", "both"], default="markdown")
    args = parser.parse_args()

    try:
        with open(args.findings) as f:
            findings_data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"error": f"Failed to read findings: {e}"}), file=sys.stderr)
        sys.exit(1)

    agents_data = []
    if args.agents:
        try:
            with open(args.agents) as f:
                agents_data = json.load(f).get("agents", [])
        except (OSError, json.JSONDecodeError):
            pass

    framework_data = None
    if args.framework:
        try:
            with open(args.framework) as f:
                framework_data = json.load(f)
        except (OSError, json.JSONDecodeError):
            pass

    taxonomy = categorize(
        findings=findings_data.get("findings", []),
        agents=agents_data,
        framework=framework_data,
    )

    if args.format in ("markdown", "both"):
        print(render_markdown(taxonomy))
    if args.format in ("json", "both"):
        print(json.dumps(taxonomy, indent=2, default=str))


if __name__ == "__main__":
    main()
