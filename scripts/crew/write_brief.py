#!/usr/bin/env python3
"""scripts/crew/write_brief.py — produce a crew-brief.md handoff file.

Phase 2A of the v10 slim-skill-body shape. Absorbs the procedural prep
work that lived in `commands/crew/start.md` (slug generation, flag
parsing, existing-project conflict check, project shell creation) so
the command body can shrink to a Pattern B shape (≤30 lines).

The brief is the dynamic handoff artifact — it carries session-specific
data (parsed args, generated slug, project_dir, flags) into the
facilitator agent's task. Static rubric content (the 9-factor scoring,
phase catalog, gate policy) stays in the agent's body or refs/ — see
the static-vs-dynamic boundary rule documented in CLAUDE.md.

Brief is append-only with `---` separators. First call initializes the
project + writes the brief; subsequent calls append. Single-writer
convention prevents the file-sprawl failure mode that bit hitl-decision.json.

Usage:
  write_brief.py --command crew:start --description "..."
  write_brief.py --command crew:start --description "..." --on-conflict {switch,resume,rename,cancel}

Exit codes:
  0  brief written; JSON {slug, project_dir, ...} on stdout
  1  validation / IO error
  2  conflict — existing active project; structured info on stderr;
     parent re-invokes with --on-conflict to resolve

Design record: brainstorms/v10-session-02-slim-skill-body-shape.md
Decision memory: memory/v10-slim-skill-body-shape-decision.md
Issue: #813 (v10 series)
"""

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _PLUGIN_ROOT / "scripts"

# Theme prefix detection — first matching signal group wins. Keep keywords
# lowercased; matched against lowercased description. Ordered by specificity
# (issue patterns before fix because "issue with bug" should be issue, not fix).
_THEME_SIGNALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("issue", ("issue", "gh-", "github issue")),
    ("fix",   ("bug", "fix", "broken", "regression", "crash")),
    ("refactor", ("refactor", "cleanup", "clean up", "reorganize")),
    ("docs",  ("docs", "documentation", "readme", "changelog")),
    ("feat",  ("feature", "feat", "add", "implement", "new", "introduce")),
)

# Issue-number pattern (#1234) signals the issue theme regardless of words.
_ISSUE_NUMBER_RE = re.compile(r"#\d+")

_STOP_WORDS = frozenset({
    "the", "a", "an", "for", "to", "of", "in", "and", "with",
    "on", "at", "by", "from", "is", "are", "be", "as",
})

_SLUG_MAX = 64

# crew-brief.md format — kept minimal; absorbs only what's session-specific.
# The static procedure that the facilitator agent follows lives in the
# agent body / refs/, not duplicated here per turn.
_BRIEF_TEMPLATE = """\
# Crew Brief — {command} → {slug}

> One-file handoff. Append-only. Single writer: scripts/crew/write_brief.py.
> Static procedure lives in the facilitator agent body + refs/.

## Session

- **Command**: `/{command}`
- **Slug**: `{slug}` (theme: `{theme_prefix}`)
- **Project dir**: `{project_dir}`
- **Created**: {timestamp}

## User intent (raw $ARGUMENTS)

{description_quoted}

## Parsed flags

{flags_block}

## Conflict resolution

{conflict_block}

## Procedure pointer

The facilitator agent must:
1. Run the 9-factor rubric on the user intent above.
2. Validate the resulting plan via `scripts/crew/validate_plan.py`.
3. Persist `process-plan.md` + `process-plan.json` to the project dir.
4. Emit the task chain via TaskCreate (one per task in plan.tasks[]).
5. Verify emission via `scripts/crew/verify_chain_emission.py`.
6. Persist plan metadata via `scripts/crew/phase_manager.py update`.
7. Store the planning decision via `wicked-brain:memory`.
8. Return JSON: `{{rigor_tier, reason, phase_count, specialist_count, complexity, slug, project_dir}}`.

The full procedure rubric lives in the facilitator agent's body + refs/ —
this brief carries only what's session-specific.
"""


# ---------------------------------------------------------------------------
# Slug generation — three-stage theme-aware algorithm (see start.md history).
# ---------------------------------------------------------------------------

def _kw_pattern(kw: str) -> re.Pattern:
    """Word-boundary regex for a theme keyword.

    For multi-word phrases like "github issue" or "clean up", embed the
    space as `\\s+` so any whitespace separator matches. For single words,
    use plain `\\b...\\b` so substrings (e.g. "add" inside "address",
    "fix" inside "suffix") never match.
    """
    if " " in kw:
        # Multi-word: wrap each part in word boundaries, join by \s+.
        parts = [re.escape(p) for p in kw.split() if p]
        body = r"\s+".join(parts)
        return re.compile(rf"\b{body}\b", re.IGNORECASE)
    return re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE)


def _detect_theme(text_lower: str) -> str:
    """Return the matching theme prefix, or '' if no signal matches.

    Uses word-boundary regex so short keywords ('add', 'fix', 'new')
    don't match inside unrelated words (e.g. 'address', 'suffix',
    'newcomer'). Per PR #815 review feedback.
    """
    if _ISSUE_NUMBER_RE.search(text_lower):
        return "issue"
    for theme, keywords in _THEME_SIGNALS:
        if any(_kw_pattern(kw).search(text_lower) for kw in keywords):
            return theme
    return ""


def _strip_theme_keywords(text_lower: str, theme: str) -> str:
    """Remove the theme keywords from the description so they don't
    leak into the concept extraction step. Word-boundary respecting —
    `fix` does not strip from `suffix`, `add` does not strip from
    `address`. Per PR #815 review feedback.
    """
    if not theme:
        return text_lower
    for t, keywords in _THEME_SIGNALS:
        if t == theme:
            for kw in keywords:
                text_lower = _kw_pattern(kw).sub(" ", text_lower)
            break
    # Strip issue-number tokens too — they're noise once the theme is set.
    text_lower = _ISSUE_NUMBER_RE.sub(" ", text_lower)
    return text_lower


def _extract_concepts(text: str) -> list[str]:
    """Return up to 4 kebab-cased concept tokens drawn from the
    description after stop-word removal."""
    # Split on non-word; lowercase each fragment.
    words = re.split(r"[^a-z0-9]+", text.lower())
    concepts: list[str] = []
    for w in words:
        if not w or w in _STOP_WORDS or len(w) < 2:
            continue
        concepts.append(w)
        if len(concepts) >= 4:
            break
    return concepts


def _truncate_on_word_boundary(s: str, max_len: int) -> str:
    """Truncate `s` at <= max_len without splitting a word. Returns
    the longest prefix that ends on `-` (or end-of-string)."""
    if len(s) <= max_len:
        return s
    cut = s[:max_len]
    last = cut.rfind("-")
    return cut[:last] if last > 0 else cut


def generate_slug(description: str) -> tuple[str, str]:
    """Return ``(slug, theme_prefix)`` for a description.

    Three-stage:
      1. detect theme prefix
      2. extract concepts (theme keywords + stop words removed)
      3. assemble + truncate at word boundary

    No-match fallback: kebab-case the full description.
    """
    text_lower = description.lower().strip()
    if not text_lower:
        return "", ""

    theme = _detect_theme(text_lower)
    concept_text = _strip_theme_keywords(text_lower, theme)
    concepts = _extract_concepts(concept_text)

    if theme and concepts:
        slug = f"{theme}-" + "-".join(concepts)
    elif theme:
        slug = theme
    elif concepts:
        slug = "-".join(concepts)
    else:
        # Pure fallback: kebab-case the original.
        slug = re.sub(r"[^a-z0-9]+", "-", text_lower).strip("-")

    return _truncate_on_word_boundary(slug, _SLUG_MAX), theme


# ---------------------------------------------------------------------------
# Flag parsing
# ---------------------------------------------------------------------------

def parse_flags(description: str) -> tuple[dict[str, Any], str]:
    """Extract recognised v6 flags from the description.

    Returns ``(flags_dict, description_clean)`` where description_clean
    has the parsed flag tokens removed by INDEX (not by global string
    substitution). The index-based approach prevents over-stripping —
    e.g. ``Implement full feature --rigor full`` retains the literal
    word ``full`` in the description while stripping only the flag's
    own value token.

    Per PR #815 review feedback.
    """
    flags: dict[str, Any] = {
        "yolo": False,
        "rigor": None,
        "force": False,
        "consensus_threshold": None,
    }
    rigor_values = {"minimal", "standard", "full"}

    tokens = description.split()
    consumed: set[int] = set()

    i = 0
    while i < len(tokens):
        if i in consumed:
            i += 1
            continue
        tok = tokens[i]

        if tok in ("--yolo", "--just-finish"):
            flags["yolo"] = True
            consumed.add(i)
        elif tok == "--force":
            flags["force"] = True
            consumed.add(i)
        elif tok.startswith("--rigor="):
            value = tok.split("=", 1)[1]
            if value in rigor_values:
                flags["rigor"] = value
                consumed.add(i)
            # Unrecognised value (e.g. --rigor=turbo): leave the flag
            # token in the description so the user sees their typo.
        elif tok == "--rigor" and i + 1 < len(tokens):
            value = tokens[i + 1]
            if value in rigor_values:
                flags["rigor"] = value
                consumed.add(i)
                consumed.add(i + 1)
        elif tok.startswith("--consensus-threshold="):
            try:
                flags["consensus_threshold"] = int(tok.split("=", 1)[1])
                consumed.add(i)
            except ValueError:
                pass
        elif tok == "--consensus-threshold" and i + 1 < len(tokens):
            try:
                flags["consensus_threshold"] = int(tokens[i + 1])
                consumed.add(i)
                consumed.add(i + 1)
            except ValueError:
                pass

        i += 1

    description_clean = " ".join(t for idx, t in enumerate(tokens) if idx not in consumed)
    return flags, description_clean.strip()


# ---------------------------------------------------------------------------
# Project-shell helpers (call into existing phase_manager.py)
# ---------------------------------------------------------------------------

def _python_shim() -> str:
    return str(_SCRIPTS_DIR / "_python.sh")


def _parse_json_block(stdout: str) -> dict:
    """Parse pretty-printed JSON output from a CLI helper.

    `phase_manager.py --json` and `crew.py --json` both pretty-print
    multi-line JSON (indent=2), so the trailing line is just `}`. A
    naive ``json.loads(last_line)`` would always fail. We try the full
    stripped stdout first; if that fails, fall back to extracting the
    last balanced ``{...}`` block. Per PR #815 review feedback.
    """
    text = stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: find the last top-level JSON object by walking backwards
    # from end-of-string for matching braces. Tolerant to leading prelude.
    depth = 0
    end_idx = len(text)
    for i in range(len(text) - 1, -1, -1):
        c = text[i]
        if c == "}":
            if depth == 0:
                end_idx = i + 1
            depth += 1
        elif c == "{":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[i:end_idx])
                except json.JSONDecodeError:
                    return {}
    return {}


def _phase_manager(*args: str) -> dict:
    """Invoke phase_manager.py with --json and return its parsed output.

    Raises CalledProcessError on non-zero exit. Caller decides what to do
    with the failure (typically: print stderr, exit non-zero).
    """
    cmd = ["sh", _python_shim(), str(_SCRIPTS_DIR / "_run.py"),
           "scripts/crew/phase_manager.py", *args]
    out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    return _parse_json_block(out)


def find_active_project() -> dict | None:
    """Return a normalised active-project record, or None when nothing active.

    ``crew.py find-active --json`` prints ``{"project": <record>|null,
    "project_dir": <path>|null}``. We normalise into a flat dict with
    keys ``slug``, ``phase``, ``project_dir`` so callers don't have to
    know the wrapper shape. Per PR #815 review feedback.
    """
    try:
        cmd = ["sh", _python_shim(), str(_SCRIPTS_DIR / "_run.py"),
               "scripts/crew/crew.py", "find-active", "--json"]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        return None
    record = _parse_json_block(out)
    if not isinstance(record, dict):
        return None
    project = record.get("project")
    if not isinstance(project, dict):
        return None
    name = project.get("name") or project.get("slug")
    if not name:
        return None
    return {
        "slug": name,
        "phase": project.get("current_phase") or project.get("phase"),
        "project_dir": record.get("project_dir") or project.get("project_dir"),
    }


def create_project_shell(slug: str, description: str) -> dict:
    """Call phase_manager create and return its JSON response."""
    return _phase_manager(slug, "create", "--description", description, "--json")


def pause_existing_project(slug: str) -> None:
    """Set paused=true on an existing project so it stops surfacing as active."""
    _phase_manager(slug, "update", "--data", json.dumps({"paused": True}), "--json")


# ---------------------------------------------------------------------------
# Brief composition
# ---------------------------------------------------------------------------

def _format_flags_block(flags: dict[str, Any]) -> str:
    """Render the flags dict as a compact markdown table or 'none'."""
    populated = {k: v for k, v in flags.items() if v not in (False, None)}
    if not populated:
        return "_None._"
    rows = "\n".join(f"- `{k}`: `{v}`" for k, v in populated.items())
    return rows


def _format_conflict_block(resolution: str | None, conflicting_slug: str | None) -> str:
    if not conflicting_slug:
        return "_No conflict — fresh project._"
    if resolution == "switch":
        return (
            f"Existing active project `{conflicting_slug}` was paused via "
            f"`phase_manager.py update --data '{{\"paused\": true}}'`. "
            f"Resume later by setting `paused: false`."
        )
    if resolution in ("resume", "cancel", "rename"):
        return f"User chose `{resolution}` for conflict with `{conflicting_slug}`."
    return f"Unresolved conflict with `{conflicting_slug}` — see stderr."


def write_crew_brief(
    project_dir: Path,
    *,
    command: str,
    slug: str,
    theme_prefix: str,
    description: str,
    flags: dict[str, Any],
    resolution: str | None,
    conflicting_slug: str | None,
) -> Path:
    """Write (or append to) {project_dir}/crew-brief.md and return its path.

    Append-only convention with `---` separators. First call initializes;
    subsequent calls append a new dated section.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    brief_path = project_dir / "crew-brief.md"
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Curly braces in user-controlled text would otherwise be interpreted
    # by str.format() as placeholders and raise KeyError. Escape by
    # doubling. Per PR #815 review feedback.
    description_quoted = (
        "> " + description.strip().replace("\n", "\n> ")
    ).replace("{", "{{").replace("}", "}}")
    body = _BRIEF_TEMPLATE.format(
        command=command,
        slug=slug,
        theme_prefix=theme_prefix or "(none)",
        project_dir=str(project_dir),
        timestamp=timestamp,
        description_quoted=description_quoted,
        flags_block=_format_flags_block(flags),
        conflict_block=_format_conflict_block(resolution, conflicting_slug),
    )

    if brief_path.exists() and brief_path.stat().st_size > 0:
        with brief_path.open("a", encoding="utf-8") as fh:
            fh.write("\n\n---\n\n")
            fh.write(body)
    else:
        brief_path.write_text(body, encoding="utf-8")

    return brief_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--command", required=True, help="The slash-command this brief is for, e.g. crew:start")
    p.add_argument("--description", required=True, help="Raw $ARGUMENTS (project description + flags)")
    p.add_argument(
        "--on-conflict",
        choices=("switch", "resume", "rename", "cancel"),
        default=None,
        help="Resolution for an existing active project. Required when "
             "find-active returns a project unless caller wants exit 2.",
    )
    args = p.parse_args()

    flags, description_clean = parse_flags(args.description)
    if not description_clean.strip():
        print("error: empty description after flag parsing", file=sys.stderr)
        return 1

    slug, theme = generate_slug(description_clean)
    if not slug:
        print("error: could not derive slug from description", file=sys.stderr)
        return 1

    # Conflict check. Outcome contract — every successful exit emits a
    # JSON object on stdout with an explicit ``action`` key:
    #   action=create   → new project shell created + brief written
    #   action=resume   → user chose Resume; nothing created/written
    #   action=cancel   → user chose Cancel; nothing created/written
    # Conflict detected without --on-conflict supplied → exit 2 so the
    # caller can prompt the user. Rename is implemented client-side: the
    # user re-invokes with a new description, so we treat --on-conflict=rename
    # as a structured "abort, re-invoke" signal (exit 1 with action=rename).
    existing = find_active_project()
    conflicting_slug = existing.get("slug") if existing else None

    if existing and args.on_conflict is None:
        sys.stderr.write(json.dumps({
            "conflict": True,
            "existing_slug": conflicting_slug,
            "existing_phase": existing.get("phase"),
            "hint": "re-invoke with --on-conflict={switch|resume|rename|cancel}",
        }) + "\n")
        return 2

    if existing and args.on_conflict == "resume":
        # Resume: surface the existing project info so the parent can
        # carry on with that project. No new shell, no brief, no mutation.
        print(json.dumps({
            "action": "resume",
            "slug": conflicting_slug,
            "phase": existing.get("phase"),
            "project_dir": existing.get("project_dir"),
        }, indent=2))
        return 0

    if args.on_conflict == "cancel":
        # Cancel: explicit no-op success. Caller exits cleanly.
        print(json.dumps({"action": "cancel"}, indent=2))
        return 0

    if args.on_conflict == "rename":
        # Rename is "user picks a new description and re-invokes". We
        # cannot synthesize a new description; surface a structured
        # signal so the caller can prompt for one.
        sys.stderr.write(json.dumps({
            "action": "rename",
            "hint": "user must supply a new --description and re-invoke",
        }) + "\n")
        return 1

    if existing and args.on_conflict == "switch":
        try:
            pause_existing_project(conflicting_slug)
        except subprocess.CalledProcessError as exc:
            print(f"error: pause_existing_project failed: {exc}", file=sys.stderr)
            return 1

    # Default path: create the project shell.
    try:
        shell = create_project_shell(slug, description_clean)
    except subprocess.CalledProcessError as exc:
        print(f"error: create_project_shell failed: {exc.output}", file=sys.stderr)
        return 1

    project_dir_str = shell.get("project_dir")
    if not project_dir_str:
        print(f"error: phase_manager create returned no project_dir: {shell}", file=sys.stderr)
        return 1
    project_dir = Path(project_dir_str)

    brief_path = write_crew_brief(
        project_dir,
        command=args.command,
        slug=slug,
        theme_prefix=theme,
        description=description_clean,
        flags=flags,
        resolution=args.on_conflict,
        conflicting_slug=conflicting_slug,
    )

    out = {
        "action": "create",
        "slug": slug,
        "theme_prefix": theme,
        "project_dir": str(project_dir),
        "brief_path": str(brief_path),
        "flags": flags,
        "conflict_resolved": args.on_conflict,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
