#!/usr/bin/env python3
"""Phase-0 emitter — bindings.json -> a repo-native `wg_check_claims.py` lint.

This is the "compile" step under test: the SAME emitter, parameterized
only by detected bindings, must produce a lint that works in each repo
with no hand edits. The bindings are baked in as constants at the top of
the emitted file — that is the repo-specific "compiled" surface; the
checking logic below it is generic.

Stdlib-only. The emitted file is also stdlib-only so it can live in any
repo's pre-commit/CI with zero deps.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TEMPLATE = '''#!/usr/bin/env python3
"""wg_check_claims.py — EMITTED by wicked-garden phase-0 compiler.

Repo-native claim->evidence enforcement. Compiled bindings for THIS repo
are the constants directly below; everything under them is generic.

A claim that asserts success ("tests pass", "N/N pass", "done", "clean")
must point to an evidence artifact that exists, is non-empty, carries a
success signal, and is not dominated by a failure signal. A claim whose
evidence is missing / empty / contradictory is a fabricated claim and
fails the lint.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# ---- COMPILED BINDINGS (repo-specific; emitted, not hand-written) ----
REPO = {repo!r}
TEST_COMMAND = {test_command!r}
EVIDENCE_SINK = {evidence_sink!r}
CLAIMS_MODE = {claims_mode!r}        # "frontmatter" | "commit-msg"
CLAIMS_GLOB = {claims_glob!r}        # list of frontmatter docs (if mode=frontmatter)
# ----------------------------------------------------------------------

PASS_LANG = re.compile(
    r"\\b(tests?\\s+pass|passing|all\\s+green|\\d+\\s*/\\s*\\d+\\s+(?:tests?\\s+)?pass"
    r"|exit\\s*0|typecheck[- ]?clean|build[- ]?clean|\\bclean\\b|\\bdone\\b"
    r"|complete|fixed|merged)",
    re.IGNORECASE,
)
SUCCESS_SIG = re.compile(
    r"(\\bpass(?:ed|ing)?\\b|\\bok\\b|\\u2713|\\bexit\\s*(?:code\\s*)?0\\b"
    r"|\\b\\d+\\s+passed\\b|test files\\s+\\d+\\s+passed|no\\s+violations)",
    re.IGNORECASE,
)
# A nonzero-failure token DOMINATES a success claim even when partial
# "passed" counts are also present. "0 failed" must NOT trigger; bare
# lowercase "fail" in prose must NOT trigger (only uppercase FAIL token).
HARD_FAIL = re.compile(
    r"([1-9]\\d*\\s+(?:failed|errors?|failures?)"
    r"|(?-i:\\bFAIL\\b|\\u2717)"
    r"|exit\\s*(?:code\\s*)?[1-9]"
    r"|no test files found"
    r"|\\btraceback\\b"
    r"|failures?\\s*=\\s*[1-9])",
    re.IGNORECASE,
)


def _resolve_evidence(repo_root: Path, slug: str) -> Path | None:
    sink = repo_root / EVIDENCE_SINK
    cands = [sink / slug, sink / (slug + ".txt"), sink / (slug + ".md"),
             repo_root / slug]
    # also: evidence dir co-located next to the claims doc (common shape)
    for c in cands:
        if c.exists() and c.is_file():
            return c
    # last resort: glob the sink for the slug
    if sink.is_dir():
        for p in sink.rglob(slug + "*"):
            if p.is_file():
                return p
    return None


def _parse_frontmatter_claims(text: str):
    """Return list of {{id,text,evidence}} from a `claims:` frontmatter block."""
    if not text.startswith("---"):
        return []
    end = text.find("\\n---", 3)
    fm = text[3:end] if end != -1 else text
    lines = fm.splitlines()
    claims, cur, in_block = [], None, False
    for ln in lines:
        if re.match(r"^claims:\\s*$", ln):
            in_block = True
            continue
        if in_block:
            if re.match(r"^\\S", ln):  # next top-level key ends the block
                break
            m_id = re.match(r"^\\s*-\\s*id:\\s*(.+)$", ln)
            if m_id:
                if cur:
                    claims.append(cur)
                cur = {{"id": m_id.group(1).strip(), "text": "", "evidence": ""}}
                continue
            m_ev = re.match(r"^\\s*evidence:\\s*(.+)$", ln)
            if m_ev and cur is not None:
                cur["evidence"] = m_ev.group(1).strip().strip('"\\'')
                continue
            m_tx = re.match(r"^\\s*text:\\s*(.+)$", ln)
            if m_tx and cur is not None:
                cur["text"] = m_tx.group(1).strip().strip('"\\'')
                continue
    if cur:
        claims.append(cur)
    return claims


def _evaluate(repo_root: Path, claims, source_label: str):
    violations = []
    checked = 0
    for c in claims:
        text = c.get("text", "")
        if not PASS_LANG.search(text):
            continue  # not a success-claim; nothing to back
        checked += 1
        slug = c.get("evidence", "").strip()
        if not slug:
            violations.append((c.get("id", "?"), "success claim has NO evidence pointer", text))
            continue
        ev = _resolve_evidence(repo_root, slug)
        if ev is None:
            violations.append((c.get("id", "?"), f"evidence '{{slug}}' not found under {{EVIDENCE_SINK}}/", text))
            continue
        body = ev.read_text(errors="ignore")
        if not body.strip():
            violations.append((c.get("id", "?"), f"evidence '{{slug}}' is empty", text))
            continue
        has_pass = bool(SUCCESS_SIG.search(body))
        has_fail = bool(HARD_FAIL.search(body))
        if has_fail:
            violations.append((c.get("id", "?"), f"evidence '{{slug}}' shows FAILURE, claim asserts success", text))
        elif not has_pass:
            violations.append((c.get("id", "?"), f"evidence '{{slug}}' has no success signal", text))
    return checked, violations


def main(argv):
    repo_root = Path(".").resolve()
    docs = []
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--repo-root":
            repo_root = Path(args.pop(0)).resolve()
        elif a == "--claims-file":
            docs.append(Path(args.pop(0)))
        else:
            docs.append(Path(a))

    if not docs:
        if CLAIMS_MODE == "frontmatter" and CLAIMS_GLOB:
            docs = [repo_root / g for g in CLAIMS_GLOB]
        else:
            print("wg_check_claims: commit-msg mode requires a claims source; "
                  "pass --claims-file <doc>", file=sys.stderr)
            return 0

    total_checked, all_v = 0, []
    for d in docs:
        if not d.exists():
            continue
        text = d.read_text(errors="ignore")
        claims = _parse_frontmatter_claims(text)
        checked, v = _evaluate(repo_root, claims, d.name)
        total_checked += checked
        all_v.extend((d.name, *row) for row in v)

    if all_v:
        print(f"wg_check_claims: FAIL ({{len(all_v)}} unbacked claim(s)) in {{REPO}}")
        for doc, cid, why, text in all_v:
            print(f"  [{{doc}}] claim {{cid}}: {{why}}")
            print(f"      claim text: {{text[:100]}}")
        print(f"  test_command for re-verification: {{TEST_COMMAND}}")
        return 1
    print(f"wg_check_claims: PASS ({{total_checked}} success-claim(s) all evidence-backed) in {{REPO}}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''


def render_lint(bindings: dict) -> str:
    """Render the claims-vs-evidence lint source for a repo's bindings.

    Single source of the lint logic — both the phase-0 ``emit()`` and the
    ``compile`` emit stage (which writes it as ``.wicked/claims_lint.py``)
    render through here. Stdlib-only output.
    """
    tc = bindings["test_command"]
    es = bindings["evidence_sink"]
    cs = bindings["claims_surface"]
    return TEMPLATE.format(
        repo=bindings["repo"],
        test_command=tc.get("value") or "(none-detected)",
        evidence_sink=es.get("value") or ".wg/evidence",
        claims_mode=cs.get("value"),
        claims_glob=cs.get("glob", []),
    )


def emit(bindings: dict, out_dir: str) -> str:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "wg_check_claims.py"
    target.write_text(render_lint(bindings))
    return str(target)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: emit.py <bindings.json> <out_dir>", file=sys.stderr)
        sys.exit(2)
    b = json.loads(Path(sys.argv[1]).read_text())
    print(emit(b, sys.argv[2]))
