#!/usr/bin/env python3
"""
Generate WICKED_GARDEN_BUS_EVENTS.md from the static BUS_EVENT_MAP in _bus.py.

Run: python3 scripts/_bus_catalog_gen.py > WICKED_GARDEN_BUS_EVENTS.md
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _bus import BUS_EVENT_MAP, _PAYLOAD_DENY_LIST


def generate():
    lines = []
    lines.append("# wicked-garden Bus Event Catalog")
    lines.append("")
    lines.append("> Auto-generated from `scripts/_bus.py:BUS_EVENT_MAP`. Do not edit manually.")
    lines.append("> Regenerate: `python3 scripts/_bus_catalog_gen.py > WICKED_GARDEN_BUS_EVENTS.md`")
    lines.append("")
    lines.append("## Naming Convention")
    lines.append("")
    lines.append("```")
    lines.append("wicked.<noun>.<past-tense-verb>")
    lines.append("```")
    lines.append("")
    lines.append("Three segments. Always starts with `wicked.`. Noun = the thing that changed. Verb = past tense.")
    lines.append("`domain` field is always `wicked-garden`. `subdomain` identifies the functional area.")
    lines.append("")
    lines.append("## Payload Tiers")
    lines.append("")
    lines.append("| Tier | Contents | Rule |")
    lines.append("|------|----------|------|")
    lines.append("| **Tier 1** | IDs + outcomes | Always included |")
    lines.append("| **Tier 2** | Small categoricals (complexity_score, duration_secs, specialist) | Include when relevant |")
    lines.append("| **Tier 3** | Content, diffs, memory body, source code | **NEVER on bus** |")
    lines.append("")
    lines.append("## Payload Deny-List")
    lines.append("")
    lines.append("These fields are **stripped automatically** by `_bus.py` before emission:")
    lines.append("")
    for field in sorted(_PAYLOAD_DENY_LIST):
        lines.append(f"- `{field}`")
    lines.append("")
    lines.append("## Event Catalog")
    lines.append("")

    # Group by subdomain prefix (domain area)
    groups = {}
    for event_type, defn in sorted(BUS_EVENT_MAP.items()):
        area = defn["subdomain"].split(".")[0]
        groups.setdefault(area, []).append((event_type, defn))

    for area, events in sorted(groups.items()):
        lines.append(f"### {area.title()}")
        lines.append("")
        lines.append("| Event Type | Subdomain | Description |")
        lines.append("|------------|-----------|-------------|")
        for event_type, defn in events:
            lines.append(f"| `{event_type}` | `{defn['subdomain']}` | {defn['description']} |")
        lines.append("")

    lines.append("## chain_id")
    lines.append("")
    lines.append("All crew events carry `chain_id` in the `metadata` field (top-level, not buried in payload).")
    lines.append("Format: `{uuid8}.root` for project root, `{uuid8}.{phase}` for phase scope.")
    lines.append("Enables timeline reconstruction across phases without a graph DB.")
    lines.append("")
    lines.append("## Consumer Integration Examples")
    lines.append("")
    lines.append("### Slack Bot (5 events)")
    lines.append("")
    lines.append("Subscribe to: `wicked.gate.blocked`, `wicked.phase.transitioned`, `wicked.project.completed`,")
    lines.append("`wicked.session.synthesized`, `wicked.rework.triggered`")
    lines.append("")
    lines.append("```bash")
    lines.append("npx wicked-bus subscribe --plugin my-slack-bot --filter 'wicked.gate.*' --filter 'wicked.phase.*'")
    lines.append("```")
    lines.append("")
    lines.append("### Dashboard (all events)")
    lines.append("")
    lines.append("Subscribe to: `wicked.*@wicked-garden`")
    lines.append("")
    lines.append("```bash")
    lines.append("npx wicked-bus subscribe --plugin my-dashboard --filter 'wicked.*@wicked-garden'")
    lines.append("```")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(generate(), end="")
