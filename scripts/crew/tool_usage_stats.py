#!/usr/bin/env python3
"""View tool usage statistics for agent refinement."""
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

USAGE_DIR = Path.home() / ".something-wicked" / "wicked-crew" / "tool-usage"

def load_usage(days: int = 7) -> list:
    """Load usage records from the last N days."""
    records = []
    if not USAGE_DIR.exists():
        return records

    for f in sorted(USAGE_DIR.glob("usage-*.jsonl")):
        try:
            date_str = f.stem.replace("usage-", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            age = (datetime.now() - file_date).days
            if age <= days:
                with open(f) as fp:
                    for line in fp:
                        if line.strip():
                            records.append(json.loads(line))
        except (ValueError, json.JSONDecodeError):
            continue
    return records

def print_stats(days: int = 7):
    """Print tool usage statistics."""
    records = load_usage(days)

    if not records:
        print(f"No tool usage data found in last {days} days.")
        print(f"Data location: {USAGE_DIR}")
        return

    # Aggregate by agent -> tools
    agent_tools = defaultdict(lambda: defaultdict(int))
    tool_counts = defaultdict(int)

    for r in records:
        agent = r.get("agent", "main")
        tool = r.get("tool", "unknown")
        agent_tools[agent][tool] += 1
        tool_counts[tool] += 1

    print(f"## Tool Usage Stats (last {days} days)")
    print(f"\nTotal records: {len(records)}")
    print()

    # By agent
    print("### By Agent")
    print("| Agent | Tools Used | Count |")
    print("|-------|------------|-------|")
    for agent in sorted(agent_tools.keys()):
        tools = agent_tools[agent]
        tool_list = ", ".join(sorted(tools.keys()))
        total = sum(tools.values())
        print(f"| {agent} | {tool_list} | {total} |")

    print()

    # By tool
    print("### By Tool")
    print("| Tool | Count |")
    print("|------|-------|")
    for tool, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
        print(f"| {tool} | {count} |")

    print()

    # Detailed breakdown
    print("### Agent -> Tool Matrix")
    all_tools = sorted(tool_counts.keys())
    header = "| Agent | " + " | ".join(all_tools) + " |"
    sep = "|-------|" + "|".join(["---"] * len(all_tools)) + "|"
    print(header)
    print(sep)
    for agent in sorted(agent_tools.keys()):
        row = f"| {agent} |"
        for tool in all_tools:
            count = agent_tools[agent].get(tool, 0)
            row += f" {count or '-'} |"
        print(row)

def main():
    days = 7
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except ValueError:
            pass

    print_stats(days)

if __name__ == "__main__":
    main()
