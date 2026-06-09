#!/usr/bin/env python3
"""sync_components.py — rebuild the derived blocks of .claude-plugin/components.json
from the actual filesystem, so the manifest can never silently drift again.

components.json documents the plugin's surface (Issue #328). Four of its blocks are
*derived* from the tree and were drifting badly (summary said 147 cmds / 69 agents /
88 skills when the real counts were ~92 / 53 / 71; ``agents_by_domain`` and the
``hooks`` list were stale too). Nothing gates on this file, so the drift went unseen.

This tool re-derives the four mechanical blocks and leaves the authored ones alone:

  derived (rebuilt from the tree)        authored (preserved verbatim)
  ----------------------------------     -----------------------------
  summary{commands,agents,skills,        _comment
          hooks,specialists}             domains
  agents_by_domain                       specialists
  skills_by_domain
  hooks  (event names, from hooks.json)

Conventions it reproduces:
  - agents live at  agents/<domain>/<name>.md          -> agents_by_domain[domain] += name
  - skills live at  skills/<domain>/[<skill>/...]SKILL.md
        depth 3  skills/<x>/SKILL.md            -> skills_by_domain[x] += x
        depth 4+ skills/<x>/<y>/.../SKILL.md    -> skills_by_domain[x] += y   (deduped)
  - hooks: the event-name keys of hooks/hooks.json, in lifecycle (insertion) order.

Usage:
  python3 scripts/ci/sync_components.py            # rewrite components.json in place
  python3 scripts/ci/sync_components.py --check    # exit 1 (+diff) if it would change

Stdlib-only. Deterministic output (so --check is stable once first synced).
"""

from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path
from typing import Dict, List

_REPO = Path(__file__).resolve().parents[2]
_COMPONENTS = _REPO / ".claude-plugin" / "components.json"
_HOOKS = _REPO / "hooks" / "hooks.json"
# top-level key order to emit (authored + derived, in the file's existing order)
_KEY_ORDER = ("_comment", "domains", "summary", "agents_by_domain",
              "skills_by_domain", "hooks", "specialists")


def _agents_by_domain() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for md in sorted((_REPO / "agents").glob("*/*.md")):
        out.setdefault(md.parent.name, []).append(md.stem)
    return {d: sorted(set(v)) for d, v in sorted(out.items())}


def _skills_by_domain() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for sk in sorted((_REPO / "skills").rglob("SKILL.md")):
        parts = sk.relative_to(_REPO / "skills").parts  # (<domain>, [<skill>, ...], SKILL.md)
        if len(parts) < 2:
            continue
        domain = parts[0]
        skill = parts[1] if len(parts) >= 3 else parts[0]
        out.setdefault(domain, []).append(skill)
    return {d: sorted(set(v)) for d, v in sorted(out.items())}


def _hook_events() -> List[str]:
    try:
        data = json.loads(_HOOKS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    hooks = data.get("hooks", data)
    return list(hooks.keys()) if isinstance(hooks, dict) else []


def _counts(authored_specialists: list) -> Dict[str, int]:
    return {
        "commands": len(list((_REPO / "commands").rglob("*.md"))),
        "agents": len(list((_REPO / "agents").rglob("*.md"))),
        "skills": len(list((_REPO / "skills").rglob("SKILL.md"))),
        "hooks": len(_hook_events()),
        "specialists": len(authored_specialists),
    }


def build(current: dict) -> dict:
    """Return components.json with the four derived blocks rebuilt from the tree;
    authored blocks copied through unchanged."""
    specialists = current.get("specialists", [])
    rebuilt = dict(current)  # preserve every authored key
    rebuilt["agents_by_domain"] = _agents_by_domain()
    rebuilt["skills_by_domain"] = _skills_by_domain()
    rebuilt["hooks"] = _hook_events()
    rebuilt["summary"] = _counts(specialists)
    return rebuilt


def _emit(d: dict) -> str:
    """Deterministic formatter that keeps leaf string-arrays on one line (matching the
    file's hand-authored style) so diffs stay legible."""
    def leaf_array(arr: list) -> str:
        return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in arr) + "]"

    lines = ["{"]
    keys = [k for k in _KEY_ORDER if k in d] + [k for k in d if k not in _KEY_ORDER]
    for ki, key in enumerate(keys):
        tail = "," if ki < len(keys) - 1 else ""
        val = d[key]
        if key in ("agents_by_domain", "skills_by_domain") and isinstance(val, dict):
            lines.append(f'  {json.dumps(key)}: {{')
            subkeys = list(val.keys())
            for si, sk in enumerate(subkeys):
                stail = "," if si < len(subkeys) - 1 else ""
                lines.append(f'    {json.dumps(sk)}: {leaf_array(val[sk])}{stail}')
            lines.append(f'  }}{tail}')
        elif key in ("domains", "hooks") and isinstance(val, list):
            lines.append(f'  {json.dumps(key)}: {leaf_array(val)}{tail}')
        else:
            block = json.dumps(val, indent=2, ensure_ascii=False)
            block = "\n".join(("  " + ln) if i else ln for i, ln in enumerate(block.splitlines()))
            lines.append(f'  {json.dumps(key)}: {block}{tail}')
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> int:
    check = "--check" in sys.argv[1:]
    current = json.loads(_COMPONENTS.read_text(encoding="utf-8"))
    new_text = _emit(build(current))
    old_text = _COMPONENTS.read_text(encoding="utf-8")
    if new_text == old_text:
        print("components.json: in sync")
        return 0
    if check:
        diff = difflib.unified_diff(old_text.splitlines(True), new_text.splitlines(True),
                                    fromfile="components.json (current)",
                                    tofile="components.json (filesystem)")
        sys.stdout.writelines(diff)
        print("\ncomponents.json: OUT OF SYNC — run `python3 scripts/ci/sync_components.py`")
        return 1
    _COMPONENTS.write_text(new_text, encoding="utf-8")
    print(f"components.json: rewritten from filesystem ({_COMPONENTS})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
