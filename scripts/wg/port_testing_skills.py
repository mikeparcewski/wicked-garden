#!/usr/bin/env python3
"""port_testing_skills.py — Phase 6b: port wicked-testing's skills into the
wicked-garden `qe` domain (per scratch/SKILL-RATIONALIZATION.md §2.2 / §6).

Shape (the taxonomy ruling):
  - The 8 Tier-1 orchestrators become ACTIONS of ONE domain router
    (`wicked-garden-qe`, authored by hand at skills/qe/SKILL.md). This script
    converts each orchestrator body into the router's action ref:
        skills/qe/refs/{setup,plan,author,execute,review,insight,accept}.md
    `update` dies (per-product updater retires with the product — 6c).
  - The 40 fork specialists move mechanically to
        skills/qe-{role}/SKILL.md  with  name: wicked-garden-qe-{role}
    EXCEPT `semantic-reviewer`, which does NOT move — garden's existing
    `wicked-garden-qe-semantic-reviewer` wins (overlap #1); its unique value
    is merged by hand.
  - `tier:` / `color:` frontmatter is dropped; tier maps to relevance breadth
    (tier 1 → broader phase_relevance, tier 2 → narrower) via RELEVANCE below.
  - Cross-references are rewritten: `wicked-testing:{role}` →
    `wicked-garden-qe-{role}`; orchestrator refs → `wicked-garden-qe {action}`.
  - `.wicked-testing/` evidence/config/db paths are a DATA CONTRACT shared
    with wicked-ledger/crew and are deliberately NOT rewritten (6c decision).
  - `lib/*.mjs` helper refs become `{WT_LIB}/*.mjs` + a resolution note (the
    helpers stay in the wicked-testing npm package until the 6c extraction).

Re-runnable + parameterized: to drop a skill late, add it to SKIP and re-run;
to merge one, add it to NO_MOVE and fold its body by hand. The script deletes
exactly the files it generates before regenerating, so a re-run is clean.

Usage:  python3 scripts/wg/port_testing_skills.py [--src <wicked-testing/skills>]
Stdlib-only, cross-platform.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SRC = REPO.parent / "wicked-testing" / "skills"

# ---------------------------------------------------------------------------
# Parameterization (the taxonomy knobs)
# ---------------------------------------------------------------------------

DOMAIN = "qe"
PREFIX = "wicked-garden"
ROUTER_NAME = f"{PREFIX}-{DOMAIN}"                     # wicked-garden-qe

# Orchestrators → router actions (ruling: ONE router, 7 actions; update dies).
ORCH_TO_ACTION = {
    "setup": "setup",
    "plan": "plan",
    "authoring": "author",
    "execution": "execute",
    "review": "review",
    "insight": "insight",
    "acceptance-testing": "accept",
}

SKIP = {"update", "wicked-vault"}       # die with the package (6c)
NO_MOVE = {"semantic-reviewer"}         # merged into existing garden skill

# Colon-token aliases that don't match a directory name 1:1.
COLON_ALIASES = {
    "acceptance": ("orch", "accept"),          # historical alias
    "oracle": ("worker", "test-oracle"),       # legacy envelope meta name
}

# Backticked bare single-word orchestrator tokens that are safe to rewrite
# (unambiguous). `plan`/`review`/`setup` are ambiguous English words — they
# are left alone and reported for manual review.
SAFE_BARE_ORCH = {"authoring", "execution", "insight", "acceptance",
                  "acceptance-testing"}

# ---------------------------------------------------------------------------
# Relevance mapping (tier → breadth; ruling §2.2 phase hints)
# ---------------------------------------------------------------------------

TIER1_DEFAULT = ('["build", "test", "review"]', '["*"]')
TIER2_DEFAULT = ('["test", "review"]', '["*"]')

RELEVANCE_OVERRIDES = {
    # planning-side tier-1 workers live earlier in the lifecycle
    "test-strategist": ('["clarify", "design", "build"]', '["specify", "build"]'),
    "testability-reviewer": ('["design", "review"]', '["specify", "build", "review"]'),
    "requirements-quality-analyst": ('["clarify", "design"]', '["specify", "build"]'),
    "risk-assessor": ('["clarify", "design", "review"]', '["*"]'),
    # operate/ship-facing specialists
    "production-quality-engineer": ('["operate", "review"]', '["ship", "incident", "review"]'),
    "release-readiness-engineer": ('["review", "operate"]', '["ship", "review"]'),
    "incident-to-scenario-synthesizer": ('["operate", "review"]', '["incident", "build"]'),
    "chaos-test-engineer": ('["test", "operate"]', '["ship", "incident", "build"]'),
    "observability-test-engineer": ('["test", "operate"]', '["*"]'),
    "load-performance-engineer": ('["test", "operate"]', '["*"]'),
    "test-oracle": ('["review", "operate"]', '["*"]'),
    "coverage-archaeologist": ('["review", "operate"]', '["*"]'),
}

ACTION_RELEVANCE = {
    "setup": ('["bootstrap"]', '["*"]'),
    "plan": ('["clarify", "design", "build"]', '["specify", "build"]'),
    "author": ('["design", "build"]', '["build", "specify"]'),
    "execute": ('["build", "test", "review"]', '["build", "ship", "review"]'),
    "review": ('["review"]', '["review", "build"]'),
    "insight": ('["review", "operate"]', '["review", "ship", "incident"]'),
    "accept": ('["build", "test", "review"]', '["build", "review", "ship"]'),
}

# ---------------------------------------------------------------------------
# Twin-pair NOT-THIS-WHEN description blocks (overlaps #13–17, #22 — 6b gate).
# Appended to the qe side's description; the garden twins are edited by hand.
# ---------------------------------------------------------------------------

TWIN_NOTES = {
    "a11y-test-engineer": [
        "NOT THIS WHEN: design/review-phase accessibility judgment without",
        "running tools — use `wicked-garden-product-a11y-expert` (advisor).",
        "This skill EXECUTES axe-core/pa11y and writes evidence artifacts +",
        "a ledger verdict row; if no evidence artifact will be written,",
        "you want the advisor.",
    ],
    "security-test-engineer": [
        "NOT THIS WHEN: DevSecOps posture review, pipeline/secrets-management",
        "advice, or security architecture guidance — use",
        "`wicked-garden-platform-security-engineer` (advisor). Both skills may",
        "run semgrep; the contract differs — THIS skill runs scenario-driven",
        "SAST/DAST/secrets scans that produce evidence artifacts + a ledger",
        "verdict row. If no evidence artifact will be written, use the advisor.",
    ],
    "compliance-test-engineer": [
        "NOT THIS WHEN: regulatory analysis, sensitive-data-handling review,",
        "or remediation planning — use",
        "`wicked-garden-platform-compliance-officer` (advisor). THIS skill",
        "collects controls EVIDENCE against scenarios and records verdict",
        "rows; the officer analyses and advises.",
    ],
    "requirements-quality-analyst": [
        "NOT THIS WHEN: eliciting or documenting requirements/user stories",
        "(clarify-phase authorship) — use",
        "`wicked-garden-product-requirements-analyst` (author/advisor).",
        "THIS skill EVALUATES already-drafted ACs for SMART+T quality.",
    ],
    "code-analyzer": [
        "NOT THIS WHEN: senior-engineer code review (quality, patterns,",
        "architecture) — use the `wicked-garden-engineering` skill's review",
        "action; in-run crew review — `wicked-garden-crew-reviewer`.",
        "THIS skill analyses testability + static quality signals for QE.",
    ],
    "ai-feature-test-engineer": [
        "Cross-ref: design-time agent-safety review (guardrails, HITL gates,",
        "architecture) is `wicked-garden-agentic-safety-reviewer`; THIS skill",
        "EXECUTES probes (injection/jailbreak/refusal/drift) with evidence.",
    ],
}

# ---------------------------------------------------------------------------
# Targeted exact-string replacements (documented judgment edits)
# ---------------------------------------------------------------------------

TARGETED = {
    "plan": [
        (
            "Tier-2 names are internal — see [docs/NAMESPACE.md](../../docs/NAMESPACE.md).\n"
            "Consumers (wicked-garden) depend only on Tier-1 names.",
            "Every specialist above is an in-catalog garden fork worker — "
            "dispatch it with the Skill tool.",
        ),
    ],
    "release-readiness-engineer": [
        (
            "- New `/wicked-testing:release` command dispatches this agent (see\n"
            "  `commands/release.md` — added in a follow-up once the gate code stabilizes).\n",
            "- The `wicked-garden-qe` review / insight actions route release-gate\n"
            "  questions to this worker.\n",
        ),
    ],
    "setup": [
        (
            "## wicked-testing Setup Complete",
            "## QE Setup Complete",
        ),
        (   # datetime.utcnow() is deprecated since Python 3.12
            "'created_at': __import__('datetime').datetime.utcnow().isoformat() + 'Z',",
            "'created_at': __import__('datetime').datetime.now(__import__('datetime')"
            ".timezone.utc).isoformat().replace('+00:00', 'Z'),",
        ),
        (   # PR #1047 Copilot: bare npx can prompt/download — detection must be side-effect-free
            'npx playwright --version > /dev/null 2>&1 && echo "npx-playwright: true" || echo "npx-playwright: false"\n'
            'npx cypress --version > /dev/null 2>&1 && echo "npx-cypress: true" || echo "npx-cypress: false"',
            'npx --no-install playwright --version > /dev/null 2>&1 && echo "npx-playwright: true" || echo "npx-playwright: false"\n'
            'npx --no-install cypress --version > /dev/null 2>&1 && echo "npx-cypress: true" || echo "npx-cypress: false"',
        ),
        (   # PR #1047 Copilot: the canonical evidence root must be scaffolded too
            "mkdir -p .wicked-testing/projects .wicked-testing/strategies .wicked-testing/scenarios \\\n"
            "         .wicked-testing/runs .wicked-testing/verdicts .wicked-testing/tasks",
            "mkdir -p .wicked-testing/projects .wicked-testing/strategies .wicked-testing/scenarios \\\n"
            "         .wicked-testing/runs .wicked-testing/verdicts .wicked-testing/tasks \\\n"
            "         .wicked-testing/evidence",
        ),
        (   # PR #1047 Copilot: snippet must actually write config.json (and a real fallback)
            'sys.stdout.write(json.dumps(config, indent=2))\n" 2>/dev/null || python -c "..."',
            'open(\'.wicked-testing/config.json\', \'w\').write(json.dumps(config, indent=2))\n'
            '" 2>/dev/null || python -c "<same script>"',
        ),
    ],
    "a11y-test-engineer": [
        (   # PR #1047 Copilot: rule contradicted the DomainStore block (N-A vs CONDITIONAL)
            "- **Zero axe violations ≠ compliant.** Always render the verdict as\n"
            "  `N-A` (pending human review) unless the scenario explicitly waives it.",
            "- **Zero axe violations ≠ compliant.** Always render the verdict as\n"
            "  `CONDITIONAL` (approve with the manual checklist as the listed fixes)\n"
            "  unless the scenario explicitly waives manual review — never `N-A`:\n"
            "  the a11y item always applies (see the DomainStore write above).",
        ),
        (
            "VERDICT=N-A REVIEWER=",
            "VERDICT=CONDITIONAL REVIEWER=",
        ),
    ],
    "test-oracle": [
        (   # PR #1047 Copilot: example contradicted the no-interpolation contract
            "```bash\n"
            'sqlite3 -json ".wicked-testing/wicked-testing.db" "\n'
            "  SELECT s.id, s.name, s.format_version, s.source_path, s.created_at\n"
            "  FROM scenarios s\n"
            "  JOIN projects p ON s.project_id = p.id\n"
            "  WHERE p.name = '{project_name}'\n"
            "    AND s.deleted = 0\n"
            "  ORDER BY s.created_at DESC\n"
            '"\n'
            "```",
            "```bash\n"
            "# Bind filter values as sqlite3 parameters — never splice them into the\n"
            "# SQL text. The value must already have passed the sanitization gate below.\n"
            'sqlite3 -json ".wicked-testing/wicked-testing.db" \\\n'
            "  \".parameter set :project_name '{validated project_name}'\" \\\n"
            '  "SELECT s.id, s.name, s.format_version, s.source_path, s.created_at\n'
            "   FROM scenarios s\n"
            "   JOIN projects p ON s.project_id = p.id\n"
            "   WHERE p.name = :project_name\n"
            "     AND s.deleted = 0\n"
            '   ORDER BY s.created_at DESC"\n'
            "```",
        ),
    ],
    "execution": [
        (   # PR #1047 Copilot: 3-segment event names — known wire contract, 6c rebrand
            "- Bus events emitted (when bus present): `wicked.testrun.started`,\n"
            "  `wicked.test.run.completed`, `wicked.evidence.captured`, and finally\n"
            "  `wicked.test.verdict.created`",
            "- Bus events emitted (when bus present): `wicked.testrun.started`,\n"
            "  `wicked.test.run.completed`, `wicked.evidence.captured`, and finally\n"
            "  `wicked.test.verdict.created`. These names are the wicked-ledger\n"
            "  emitter's existing wire contract; the 3-segment stragglers get the\n"
            "  4-segment `wicked.qe.*` rebrand at the bus-emit seam in Phase 6c —\n"
            "  do not rename them in this playbook first",
        ),
    ],
    "acceptance-test-executor": [
        (   # PR #1047 Copilot: same wire-contract note for the step emit
            "If wicked-bus is installed on PATH, emit progress events so downstream tools\n"
            "(wicked-garden crew gates, dashboards) can react in real time:",
            "If wicked-bus is installed on PATH, emit progress events so downstream tools\n"
            "(wicked-garden crew gates, dashboards) can react in real time:\n"
            "\n"
            "> `wicked.testrun.step` and `--domain wicked-testing` are the emitter's\n"
            "> existing wire contract, consumed by current ledger/dashboard tooling.\n"
            "> The 4-segment `wicked.qe.*` rebrand lands at the bus-emit seam in\n"
            "> Phase 6c — do not rename the emit here first.",
        ),
    ],
    "authoring": [
        (
            "detection via `setup`",
            "detection via the `wicked-garden-qe` setup action",
        ),
        (
            "tool *detection* lives in `setup`",
            "tool *detection* lives in the `wicked-garden-qe` setup action",
        ),
    ],
}

WT_LIB_NOTE = """
## Helper resolution (`{WT_LIB}`)

`{WT_LIB}` is the wicked-testing npm package's `lib/` directory — the helper
modules stay in that package until the 6c extraction. Resolve it (cross-platform):

```bash
WT_LIB="$(npm root -g 2>/dev/null)/wicked-testing/lib"
[ -d "$WT_LIB" ] || WT_LIB="$(npm root 2>/dev/null)/wicked-testing/lib"
```
"""

LEDGER_NOTE = """
## wicked-ledger resolution

`wicked-ledger` (npm) is the QE data layer — DomainStore, oracle queries, and
manifest building. Import-style snippets above must run where the package
resolves: the target project's `node_modules` (`npm i --no-save wicked-ledger`)
or any directory with it installed. The pinned range lives in
`.claude-plugin/plugin.json` → `wicked_ledger_version`.
"""

FRONTMATTER_RE = re.compile(r"^---\n(.*?\n)---\n", re.DOTALL)


def discover(src: Path):
    orch, workers = {}, {}
    for d in sorted(src.iterdir()):
        if not d.is_dir() or d.name in SKIP or not (d / "SKILL.md").is_file():
            continue
        if d.name in ORCH_TO_ACTION:
            orch[d.name] = d / "SKILL.md"
        elif d.name in NO_MOVE:
            continue
        else:
            workers[d.name] = d / "SKILL.md"
    return orch, workers


def load_tiers(src: Path):
    pj = src.parent / ".claude-plugin" / "plugin.json"
    tiers = {}
    for entry in json.loads(pj.read_text(encoding="utf-8")).get("skills", []):
        tiers[entry["name"].split(":", 1)[1]] = entry.get("tier")
    return tiers


class Rewriter:
    def __init__(self, orch, workers):
        self.orch = orch
        self.workers = workers
        self.log = []
        self.manual_review = []

    def _note(self, path, rule, frm, to):
        self.log.append(f"{path}: [{rule}] {frm!r} -> {to!r}")

    def worker_name(self, role):
        return f"{PREFIX}-{DOMAIN}-{role}"

    def path_for(self, name, from_dir: str):
        """New relative path of a former sibling skill, from `from_dir`
        ('worker' = skills/qe-x/, 'refs' = skills/qe/refs/)."""
        if name in ORCH_TO_ACTION:
            action = ORCH_TO_ACTION[name]
            return (f"refs/{action}.md" if from_dir == "refs"
                    else f"../qe/refs/{action}.md")
        if name in NO_MOVE:  # semantic-reviewer → garden's existing skill
            return ("../../qe-semantic-reviewer/SKILL.md" if from_dir == "refs"
                    else "../qe-semantic-reviewer/SKILL.md")
        return (f"../../qe-{name}/SKILL.md" if from_dir == "refs"
                else f"../qe-{name}/SKILL.md")

    def rewrite_body(self, text: str, src_name: str, from_dir: str) -> str:
        path_label = src_name

        # 0. targeted judgment replacements
        for frm, to in TARGETED.get(src_name, []):
            if frm in text:
                text = text.replace(frm, to)
                self._note(path_label, "targeted", frm[:40] + "…", to[:40] + "…")

        # 1. lib helper refs → {WT_LIB}
        text = re.sub(r"\.\./\.\./lib/", "{WT_LIB}/", text)
        text = re.sub(r"(?<![\w/.{])lib/(?=[\w./-]+\.mjs)", "{WT_LIB}/", text)

        # 2. markdown links into the old repo root → plain package refs
        def _doclink(m):
            target = m.group(2)
            self._note(path_label, "doclink", m.group(0), target)
            return f"`{target}` (wicked-testing npm package)"

        text = re.sub(
            r"\[`?[^\]]+?`?\]\(\.\./\.\./((docs/[\w.-]+|SCENARIO-FORMAT\.md|schemas/[\w.-]+))(?:[^)]*)\)",
            lambda m: _doclink(m),
            text,
        )

        # 3. cross-skill path refs (link or plain) → new locations
        all_names = set(self.orch) | set(self.workers) | set(NO_MOVE)

        def _skillpath(m):
            name = m.group(1)
            if name not in all_names:
                return m.group(0)
            new = self.path_for(name, from_dir)
            self._note(path_label, "skillpath", m.group(0), new)
            return new

        text = re.sub(r"(?:\.\./)+skills/([a-z0-9-]+)/SKILL\.md", _skillpath, text)
        text = re.sub(r"\.\./([a-z0-9-]+)/SKILL\.md", _skillpath, text)
        text = re.sub(r"(?<![\w/.])skills/([a-z0-9-]+)/SKILL\.md", _skillpath, text)

        # 4. orchestrator colon tokens → router action phrases (longest first)
        orch_tokens = sorted(ORCH_TO_ACTION, key=len, reverse=True)
        for tok in orch_tokens:
            action = ORCH_TO_ACTION[tok]
            pat = re.compile(rf"/?wicked-testing:{re.escape(tok)}(?![\w-])")
            text, n = pat.subn(f"{ROUTER_NAME} {action}", text)
            if n:
                self._note(path_label, "orch-token", f"wicked-testing:{tok}", f"{ROUTER_NAME} {action}")
        for alias, (kind, target) in COLON_ALIASES.items():
            pat = re.compile(rf"/?wicked-testing:{re.escape(alias)}(?![\w-])")
            repl = (f"{ROUTER_NAME} {target}" if kind == "orch"
                    else self.worker_name(target))
            text, n = pat.subn(repl, text)
            if n:
                self._note(path_label, "alias-token", f"wicked-testing:{alias}", repl)

        # 5. worker colon tokens → new fork-skill names (longest first)
        for role in sorted(set(self.workers) | set(NO_MOVE), key=len, reverse=True):
            pat = re.compile(rf"/?wicked-testing:{re.escape(role)}(?![\w-])")
            text, n = pat.subn(self.worker_name(role), text)
            if n:
                self._note(path_label, "worker-token", f"wicked-testing:{role}", self.worker_name(role))

        # 6. backticked bare sibling names → new names
        def _bare(m):
            name = m.group(1)
            if name in self.workers or name in NO_MOVE:
                new = f"`{self.worker_name(name)}`"
            elif name in ORCH_TO_ACTION and name in SAFE_BARE_ORCH:
                new = f"`{ROUTER_NAME}` {ORCH_TO_ACTION[name]}"
            elif name in ORCH_TO_ACTION:
                self.manual_review.append(f"{path_label}: ambiguous backtick `{name}` left as-is")
                return m.group(0)
            else:
                return m.group(0)
            self._note(path_label, "bare-name", m.group(0), new)
            return new

        text = re.sub(r"`([a-z][a-z0-9-]+)`", _bare, text)
        return text

    def convert_worker(self, role: str, src_path: Path, tiers) -> str:
        raw = src_path.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(raw)
        if not m:
            raise SystemExit(f"{src_path}: no frontmatter")
        fm_lines = m.group(1).splitlines()
        body = raw[m.end():]

        phase, arch = RELEVANCE_OVERRIDES.get(
            role, TIER1_DEFAULT if tiers.get(role) == 1 else TIER2_DEFAULT)

        out = ["---"]
        in_desc = False
        for line in fm_lines:
            key = line.split(":", 1)[0].strip() if not line.startswith((" ", "\t")) else None
            if key in ("tier", "color"):
                in_desc = False
                continue
            if key == "name":
                out.append(f"name: {self.worker_name(role)}")
                in_desc = False
                continue
            if key == "description":
                in_desc = True
                out.append(line)
                continue
            if line.startswith((" ", "\t")) or not line.strip():
                out.append(line)
                continue
            # a new top-level key ends the description block — inject the
            # twin note (if any) as the description's last lines first.
            if in_desc and role in TWIN_NOTES:
                out.append("")
                out.extend("  " + t for t in TWIN_NOTES[role])
                del TWIN_NOTES[role]
            in_desc = False
            out.append(line)
        if in_desc and role in TWIN_NOTES:  # description was the last key
            out.append("")
            out.extend("  " + t for t in TWIN_NOTES[role])
            del TWIN_NOTES[role]
        out.append(f"phase_relevance: {phase}")
        out.append(f"archetype_relevance: {arch}")
        out.append("---")

        fm_text = "\n".join(out) + "\n"
        fm_text = self.rewrite_body(fm_text, role, "worker")
        body = self.rewrite_body(body, role, "worker")
        if "{WT_LIB}" in body or "{WT_LIB}" in fm_text:
            body = body.rstrip() + "\n" + WT_LIB_NOTE
        if re.search(r"from ['\"]wicked-ledger", body):
            body = body.rstrip() + "\n" + LEDGER_NOTE
        return fm_text + body

    def convert_action_ref(self, orch_name: str, src_path: Path) -> str:
        raw = src_path.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(raw)
        if not m:
            raise SystemExit(f"{src_path}: no frontmatter")
        body = raw[m.end():]
        action = ORCH_TO_ACTION[orch_name]
        phase, arch = ACTION_RELEVANCE[action]

        body = self.rewrite_body(body, orch_name, "refs")
        # Retitle the old `# wicked-testing:X` / `# X Skill` heading.
        body = re.sub(
            r"^# .*\n", f"# qe {action} — full playbook\n", body, count=1,
            flags=re.MULTILINE,
        )
        header = (
            "---\n"
            f"phase_relevance: {phase}\n"
            f"archetype_relevance: {arch}\n"
            "---\n\n"
            f"<!-- Action ref of the `{ROUTER_NAME}` router (Phase 6b port of\n"
            f"     wicked-testing's `{orch_name}` orchestrator). Loaded on demand\n"
            f"     via Read() from the router's `{action}` action — not a skill. -->\n\n"
        )
        out = header + body
        if "{WT_LIB}" in out:
            out = out.rstrip() + "\n" + WT_LIB_NOTE
        if re.search(r"from ['\"]wicked-ledger", out):
            out = out.rstrip() + "\n" + LEDGER_NOTE
        return out


def main(argv):
    src = DEFAULT_SRC
    if "--src" in argv:
        src = Path(argv[argv.index("--src") + 1])
    if not src.is_dir():
        raise SystemExit(f"source skills dir not found: {src}")

    orch, workers = discover(src)
    tiers = load_tiers(src)
    rw = Rewriter(orch, workers)

    # Clean previous generation (exactly what we generate, nothing else).
    for role in workers:
        tgt = REPO / "skills" / f"{DOMAIN}-{role}"
        if tgt.exists():
            shutil.rmtree(tgt)
    refs_dir = REPO / "skills" / DOMAIN / "refs"
    if refs_dir.exists():
        for action in ORCH_TO_ACTION.values():
            f = refs_dir / f"{action}.md"
            if f.exists():
                f.unlink()

    # Generate.
    for role, path in sorted(workers.items()):
        tgt = REPO / "skills" / f"{DOMAIN}-{role}"
        tgt.mkdir(parents=True, exist_ok=True)
        (tgt / "SKILL.md").write_text(rw.convert_worker(role, path, tiers), encoding="utf-8")
    refs_dir.mkdir(parents=True, exist_ok=True)
    for orch_name, path in sorted(orch.items()):
        action = ORCH_TO_ACTION[orch_name]
        (refs_dir / f"{action}.md").write_text(
            rw.convert_action_ref(orch_name, path), encoding="utf-8")

    # ---- Post-generation assertions -------------------------------------
    errors = []
    gen_files = [REPO / "skills" / f"{DOMAIN}-{r}" / "SKILL.md" for r in workers]
    gen_files += [refs_dir / f"{a}.md" for a in ORCH_TO_ACTION.values()]
    for f in gen_files:
        text = f.read_text(encoding="utf-8")
        rel = f.relative_to(REPO)
        if re.search(r"wicked-testing:[a-z]", text):
            errors.append(f"{rel}: un-rewritten colon ref remains")
        if f"{PREFIX}-{DOMAIN}-{PREFIX}" in text:
            errors.append(f"{rel}: double-prefix artifact")
        fm_match = FRONTMATTER_RE.match(text)
        if fm_match and re.search(r"^(tier|color)\s*:", fm_match.group(1), re.MULTILINE):
            errors.append(f"{rel}: tier/color survived in frontmatter")
        for sk in re.findall(r'Skill\(\s*skill="([^"]+)"', text):
            if sk.startswith(PREFIX) and not (
                sk == ROUTER_NAME
                or sk.startswith(f"{PREFIX}-{DOMAIN}-")
                or sk.startswith(f"{PREFIX}-")
            ):
                errors.append(f"{rel}: suspicious Skill() target {sk}")

    print(f"generated: {len(workers)} workers + {len(orch)} action refs")
    print(f"rewrites applied: {len(rw.log)}")
    leftover_twins = [k for k in TWIN_NOTES]
    if leftover_twins:
        errors.append(f"twin notes never injected for: {leftover_twins}")
    if rw.manual_review:
        print("\nMANUAL REVIEW (ambiguous tokens left as-is):")
        for line in sorted(set(rw.manual_review)):
            print("  " + line)
    # Residual 'wicked-testing' prose mentions (allowed: data paths + package refs)
    print("\nresidual 'wicked-testing' prose mentions (excluding .wicked-testing/ paths):")
    for f in gen_files:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "wicked-testing" in line and ".wicked-testing" not in line:
                print(f"  {f.relative_to(REPO)}:{i}: {line.strip()[:110]}")
    if "--log" in argv:
        for entry in rw.log:
            print("LOG " + entry)
    if errors:
        print("\nERRORS:")
        for e in errors:
            print("  " + e)
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
