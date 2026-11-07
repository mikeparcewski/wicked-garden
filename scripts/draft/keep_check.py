#!/usr/bin/env python3
"""keep_check.py — a refine keeps the person's own edits (DES-CHAT-ARTIFACTS-001 §6.2).

Two commands, both deterministic and stdlib-only:

``map``: the PROTECTED-EDITS MAP of a document, recomputed from its version lineage (never from
operation logs, so it cannot drift). The host walks the parent chain root → head and hands each step
in a lineage file::

    {"steps": [{"version": 0, "html": "/abs/_v0.html", "step": "root"},
               {"version": 1, "html": "/abs/_v1.html", "step": "job", "allow": []},
               {"version": 2, "html": "/abs/_v2.html", "step": "hand"}, …]}

- ``hand`` (a version no run made, not a theme): the parent → child diff is upserted, keyed by the
  ``data-wid`` anchors interactive never reassigns: a leaf's text; the attributes of the node that
  changed; a TOMBSTONE for a removed node (it replaces every entry of the node and its descendants and
  takes a removed slide out of the protected order); presence for an added node with its initial text
  and attributes; ONE slide-order entry, only when the relative order of the slides both versions hold
  changed. A later hand step overwrites the same entry: the newest choice wins.
- ``theme``: no change (a document theme is re-applied at every version).
- ``job`` (a run made it): no change, except the entries that run's accepted ``allow`` released.
- ``unknown`` (a version from before runs were recorded): no change — never claimed as kept.
- Undo and restore are forks: the chain follows the restored parent, so nothing undone is protected.

Each entry has an id that carries a hash of its value (``text:<wid>#<h8>``, ``attr:<wid>:<name>#<h8>``,
``gone:<wid>``, ``added:<wid>``, ``order#<h8>``): a person's "Let this change it" names one exact value,
so a value edited again later is kept again.

``check``: a candidate document against a map (minus the attempt's ``allow``): text compared at leaf
level, attributes on the node that was edited, tombstoned nodes absent, added and protected nodes
present, the protected slides in their order (a new slide anywhere is fine). Nothing else is
constrained.

Exit: 0 = map written / every edit kept; 1 = an edit was not kept; 2 = usage / unreadable input.

CLI:
    keep_check.py map --lineage <lineage.json> [--touch <wid> …] [--json]
    keep_check.py check --map <map.json> <candidate.html> [--allow <id> …] [--json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from draft._dom import Node, parse  # noqa: E402

MAX_HTML_BYTES = 8 * 1024 * 1024
MAX_STEPS = 1000
STEP_KINDS = ("root", "hand", "theme", "job", "unknown")
SLIDE_TAGS = frozenset({"section"})
_WS = re.compile(r"\s+")
_LABEL_CHARS = 48
_ROLE = {"h1": "heading", "h2": "heading", "h3": "heading", "h4": "heading", "h5": "heading", "h6": "heading",
         "p": "paragraph", "li": "list item", "td": "table cell", "th": "table cell", "img": "image",
         "blockquote": "quote", "figcaption": "caption", "a": "link", "button": "button", "aside": "speaker notes"}


class KeepError(ValueError):
    """Unusable input: the caller must treat the check as not run (never as a pass)."""


def _h8(value: str | None) -> str:
    return hashlib.sha256(("\0none" if value is None else value).encode("utf-8")).hexdigest()[:8]


def _text(node: Node) -> str:
    out: list[str] = []
    for n in node.walk():
        if n.tag == "#text" and not any(a.tag in ("script", "style") for a in n.ancestors()):
            out.append(n.text)
    return _WS.sub(" ", " ".join(out)).strip()


class Version:
    """One parsed version: its anchored nodes, which of them are leaves, and its slides in order."""

    def __init__(self, html: str) -> None:
        self.doc = parse(html)
        self.nodes: dict[str, Node] = {}
        for el in self.doc.elements():
            wid = el.attrs.get("data-wid")
            if wid and wid not in self.nodes:
                self.nodes[wid] = el
        self.leaves = {w for w, n in self.nodes.items()
                       if not any(d is not n and d.attrs.get("data-wid") for d in n.walk() if d.tag and not d.tag.startswith("#"))}
        self.slides = self._slides()

    def _is_slide(self, el: Node) -> bool:
        return "data-slide-id" in el.attrs or "data-slide" in el.attrs or el.tag in SLIDE_TAGS or "slide" in el.classes()

    def _slides(self) -> list[str]:
        """Top-level slide keys in document order: `data-slide-id` (a deck), else the container's `data-wid`."""
        out: list[str] = []
        for el in self.doc.elements():
            if not self._is_slide(el) or any(self._is_slide(a) for a in el.ancestors()):
                continue
            key = el.attrs.get("data-slide-id") or el.attrs.get("data-wid")
            if key and key not in out:
                out.append(key)
        return out

    def slide_node(self, key: str) -> Node | None:
        for el in self.doc.elements():
            if el.attrs.get("data-slide-id") == key or (el.attrs.get("data-wid") == key and self._is_slide(el)):
                return el
        return None

    def attrs(self, wid: str) -> dict[str, str]:
        return {k: v for k, v in self.nodes[wid].attrs.items() if k != "data-wid"}

    def descendants(self, wid: str) -> set[str]:
        node = self.nodes[wid]
        return {d.attrs["data-wid"] for d in node.walk() if d is not node and d.tag and not d.tag.startswith("#") and d.attrs.get("data-wid")}

    def slide_key_of(self, wid: str) -> str | None:
        node = self.nodes[wid]
        if self._is_slide(node):
            return node.attrs.get("data-slide-id") or wid
        return None

    def label(self, wid: str) -> str:
        node = self.nodes[wid]
        role = "slide" if self._is_slide(node) else _ROLE.get(node.tag, "block")
        where = ""
        for i, key in enumerate(self.slides):
            s = self.slide_node(key)
            if s is not None and (s is node or any(a is s for a in node.ancestors())):
                where = f"slide {i + 1} · " if len(self.slides) > 1 else ""
                if s is node:
                    return f"slide {i + 1}"
                break
        text = _text(node)
        quoted = f" “{text[:_LABEL_CHARS]}{'…' if len(text) > _LABEL_CHARS else ''}”" if text else ""
        return f"{where}{role}{quoted}"


def _load(path: str) -> Version:
    p = Path(path)
    if not p.is_file():
        raise KeepError(f"version file not found: {p.name}")
    if p.stat().st_size > MAX_HTML_BYTES:
        raise KeepError(f"{p.name} is over {MAX_HTML_BYTES // (1024 * 1024)} MB")
    return Version(p.read_text(encoding="utf-8", errors="replace"))


def empty_map() -> dict:
    return {"texts": {}, "attrs": {}, "gone": [], "added": [], "order": None, "labels": {}}


def entry_ids(m: dict) -> list[dict]:
    """Every protected entry with its id, kind and label."""
    out: list[dict] = []
    for wid, text in sorted(m["texts"].items()):
        out.append({"id": f"text:{wid}#{_h8(text)}", "kind": "text", "wid": wid, "label": m["labels"].get(wid, wid)})
    for wid, attrs in sorted(m["attrs"].items()):
        for name, value in sorted(attrs.items()):
            out.append({"id": f"attr:{wid}:{name}#{_h8(value)}", "kind": "attr", "wid": wid, "name": name,
                        "label": f"{m['labels'].get(wid, wid)} ({name})"})
    for wid in sorted(m["added"]):
        out.append({"id": f"added:{wid}", "kind": "added", "wid": wid, "label": f"added {m['labels'].get(wid, wid)}"})
    for wid in sorted(m["gone"]):
        out.append({"id": f"gone:{wid}", "kind": "gone", "wid": wid, "label": f"removed {m['labels'].get(wid, wid)}"})
    if m["order"] is not None:
        out.append({"id": f"order#{_h8(chr(10).join(m['order']))}", "kind": "order", "wid": None, "label": "your slide order"})
    return out


def release(m: dict, allow: list[str]) -> dict:
    """The map without the entries whose exact ids a person let change."""
    let = set(allow)
    if not let:
        return m
    out = json.loads(json.dumps(m))
    for e in entry_ids(m):
        if e["id"] not in let:
            continue
        if e["kind"] == "text":
            out["texts"].pop(e["wid"], None)
        elif e["kind"] == "attr":
            held = out["attrs"].get(e["wid"])
            if held is not None:
                held.pop(e["name"], None)
                if not held:
                    out["attrs"].pop(e["wid"])
        elif e["kind"] == "added":
            out["added"].remove(e["wid"])
        elif e["kind"] == "gone":
            out["gone"].remove(e["wid"])
        elif e["kind"] == "order":
            out["order"] = None
    return out


def _forget(m: dict, wids: set[str]) -> None:
    for w in wids:
        m["texts"].pop(w, None)
        m["attrs"].pop(w, None)
        if w in m["added"]:
            m["added"].remove(w)


def hand_step(m: dict, parent: Version, child: Version) -> None:
    """Upsert one hand step's parent → child diff into the map (in place)."""
    removed = [w for w in parent.nodes if w not in child.nodes]
    # A removed ancestor's tombstone covers its descendants: only the outermost removed nodes are tombstoned.
    covered: set[str] = set()
    for w in removed:
        covered |= parent.descendants(w)
    for w in removed:
        if w in covered:
            continue
        _forget(m, {w} | parent.descendants(w))
        for d in parent.descendants(w):
            if d in m["gone"]:
                m["gone"].remove(d)
        if w not in m["gone"]:
            m["gone"].append(w)
        m["labels"][w] = parent.label(w)
        key = parent.slide_key_of(w)
        if m["order"] is not None and key is not None and key in m["order"]:
            m["order"].remove(key)
        for d in parent.descendants(w):
            dk = parent.slide_key_of(d)
            if m["order"] is not None and dk is not None and dk in m["order"]:
                m["order"].remove(dk)
    for w, node in child.nodes.items():
        if w not in parent.nodes:
            # Added (or re-added: its tombstone is cleared): present, with its initial text and attributes.
            if w in m["gone"]:
                m["gone"].remove(w)
            if w not in m["added"]:
                m["added"].append(w)
            if w in child.leaves:
                m["texts"][w] = _text(node)
            if child.attrs(w):
                m["attrs"][w] = dict(child.attrs(w))
            m["labels"][w] = child.label(w)
            continue
        if w in child.leaves and _text(node) != _text(parent.nodes[w]):
            m["texts"][w] = _text(node)
            m["labels"][w] = child.label(w)
        before, after = parent.attrs(w), child.attrs(w)
        for name in sorted(set(before) | set(after)):
            if before.get(name) != after.get(name):
                m["attrs"].setdefault(w, {})[name] = after.get(name)
                m["labels"][w] = child.label(w)
    common = [k for k in parent.slides if k in child.slides]
    if common != [k for k in child.slides if k in parent.slides]:
        m["order"] = list(child.slides)


def build_map(steps: list[dict]) -> tuple[dict, Version | None]:
    if not isinstance(steps, list) or not steps or len(steps) > MAX_STEPS:
        raise KeepError("the lineage must list 1 to 1000 steps, root first")
    m = empty_map()
    prev: Version | None = None
    for i, s in enumerate(steps):
        kind = s.get("step") if isinstance(s, dict) else None
        if kind not in STEP_KINDS or not isinstance(s.get("html"), str):
            raise KeepError(f"step {i} must be {{html, step: {'|'.join(STEP_KINDS)}}}")
        cur = _load(s["html"])
        if kind == "hand" and prev is not None:
            hand_step(m, prev, cur)
        elif kind == "job":
            allow = s.get("allow") or []
            if not isinstance(allow, list) or not all(isinstance(a, str) for a in allow):
                raise KeepError(f"step {i}: allow must be a list of entry ids")
            m = release(m, allow)
        prev = cur
    return m, prev


def entries_for(m: dict, head: Version | None, touch: list[str]) -> list[dict]:
    """The entries with `touched`: the seat's or the person's anchors overlap it by subtree."""
    touched: set[str] = set()
    if head is not None:
        for t in touch:
            if t in head.nodes:
                touched |= {t} | head.descendants(t)
    out = []
    for e in entry_ids(m):
        out.append({**e, "touched": e["wid"] is not None and e["wid"] in touched})
    return out


def check(m: dict, candidate: Version, allow: list[str]) -> dict:
    eff = release(m, allow)
    violations: list[dict] = []
    missing: set[str] = set()

    def lost(wid: str) -> None:
        if wid not in missing:
            missing.add(wid)
            violations.append({"kind": "missing", "wid": wid, "label": eff["labels"].get(wid, wid),
                               "sentence": f"your edit to {eff['labels'].get(wid, wid)} was removed"})

    for wid, text in eff["texts"].items():
        if wid not in candidate.nodes:
            lost(wid)
        elif _text(candidate.nodes[wid]) != text:
            violations.append({"kind": "changed", "wid": wid, "label": eff["labels"].get(wid, wid),
                               "sentence": f"your text in {eff['labels'].get(wid, wid)} was changed"})
    for wid, attrs in eff["attrs"].items():
        if wid not in candidate.nodes:
            lost(wid)
            continue
        now = candidate.attrs(wid)
        for name, value in attrs.items():
            if now.get(name) != value:
                violations.append({"kind": "changed", "wid": wid, "name": name, "label": eff["labels"].get(wid, wid),
                                   "sentence": f"your {name} on {eff['labels'].get(wid, wid)} was changed"})
    for wid in eff["added"]:
        if wid not in candidate.nodes:
            lost(wid)
    for wid in eff["gone"]:
        if wid in candidate.nodes:
            violations.append({"kind": "reappeared", "wid": wid, "label": eff["labels"].get(wid, wid),
                               "sentence": f"{eff['labels'].get(wid, wid)} that you removed is back"})
    if eff["order"] is not None:
        present = [k for k in eff["order"] if k in candidate.slides]
        for k in eff["order"]:
            if k not in candidate.slides:
                violations.append({"kind": "missing", "wid": k, "label": "a slide in your order",
                                   "sentence": "a slide you placed was removed"})
        if [k for k in candidate.slides if k in eff["order"]] != present:
            violations.append({"kind": "order", "wid": None, "label": "your slide order",
                               "sentence": "your slide order was changed"})
    kept = len(entry_ids(eff))
    ok = not violations
    return {"check": "keep", "ok": ok, "kept": kept, "violations": violations,
            "summary": (f"keep: all {kept} of your edits kept" if ok else
                        f"keep: {len(violations)} of your edits not kept — {violations[0]['sentence']}")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    mp = sub.add_parser("map")
    mp.add_argument("--lineage", required=True)
    mp.add_argument("--touch", action="append", default=[])
    mp.add_argument("--json", action="store_true")
    cp = sub.add_parser("check")
    cp.add_argument("--map", required=True)
    cp.add_argument("html")
    cp.add_argument("--allow", action="append", default=[])
    cp.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "map":
            lineage = json.loads(Path(args.lineage).read_text(encoding="utf-8"))
            m, head = build_map(lineage.get("steps") if isinstance(lineage, dict) else None)
            report = {"check": "keep-map", "ok": True, "map": m, "entries": entries_for(m, head, args.touch)}
            print(json.dumps(report, indent=2 if not args.json else None))
            return 0
        raw = json.loads(Path(args.map).read_text(encoding="utf-8"))
        m = raw.get("map", raw) if isinstance(raw, dict) else None
        if not isinstance(m, dict) or not all(k in m for k in ("texts", "attrs", "gone", "added", "order", "labels")):
            raise KeepError("the map file is not a keep_check map")
        report = check(m, _load(args.html), args.allow)
    except (OSError, ValueError) as exc:
        print(json.dumps({"check": "keep", "ok": False, "error": str(exc)}))
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report["summary"])
        for v in report["violations"][1:]:
            print("  " + v["sentence"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
