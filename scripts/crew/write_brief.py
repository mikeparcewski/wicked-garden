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
import shutil
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

# v6 flags — orthogonal axes. Anything not in this set is treated as part
# of the description (so "implement --turbo flag" doesn't get parsed as a
# `--turbo` flag).
_KNOWN_FLAGS = frozenset({
    "--yolo", "--just-finish", "--force",
    # Flags with values:
    "--rigor", "--consensus-threshold",
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

def _detect_theme(text_lower: str) -> str:
    """Return the matching theme prefix, or '' if no signal matches."""
    if _ISSUE_NUMBER_RE.search(text_lower):
        return "issue"
    for theme, keywords in _THEME_SIGNALS:
        if any(kw in text_lower for kw in keywords):
            return theme
    return ""


def _strip_theme_keywords(text_lower: str, theme: str) -> str:
    """Remove the theme keywords from the description so they don't
    leak into the concept extraction step."""
    if not theme:
        return text_lower
    for t, keywords in _THEME_SIGNALS:
        if t == theme:
            for kw in keywords:
                text_lower = text_lower.replace(kw, " ")
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
    has the parsed flag tokens removed so they don't leak into slug
    concept extraction.
    """
    flags: dict[str, Any] = {
        "yolo": False,
        "rigor": None,
        "force": False,
        "consensus_threshold": None,
    }
    tokens_to_strip: list[str] = []

    # Walk tokens; recognise --flag / --flag=value / --flag value.
    tokens = description.split()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        # --flag=value form
        if tok.startswith("--") and "=" in tok:
            name, _, value = tok.partition("=")
            if name == "--rigor" and value in {"minimal", "standard", "full"}:
                flags["rigor"] = value
                tokens_to_strip.append(tok)
            elif name == "--consensus-threshold":
                try:
                    flags["consensus_threshold"] = int(value)
                    tokens_to_strip.append(tok)
                except ValueError:
                    pass  # unparseable → leave as part of description
        elif tok in ("--yolo", "--just-finish"):
            flags["yolo"] = True
            tokens_to_strip.append(tok)
        elif tok == "--force":
            flags["force"] = True
            tokens_to_strip.append(tok)
        elif tok == "--rigor" and i + 1 < len(tokens):
            v = tokens[i + 1]
            if v in {"minimal", "standard", "full"}:
                flags["rigor"] = v
                tokens_to_strip.extend([tok, v])
                i += 1  # skip the value token next loop
        elif tok == "--consensus-threshold" and i + 1 < len(tokens):
            try:
                flags["consensus_threshold"] = int(tokens[i + 1])
                tokens_to_strip.extend([tok, tokens[i + 1]])
                i += 1
            except ValueError:
                pass
        i += 1

    description_clean = description
    for t in tokens_to_strip:
        # Remove with surrounding whitespace, idempotent.
        description_clean = re.sub(rf"\s*{re.escape(t)}\s*", " ", description_clean)
    return flags, description_clean.strip()


# ---------------------------------------------------------------------------
# Project-shell helpers (call into existing phase_manager.py)
# ---------------------------------------------------------------------------

def _python_shim() -> str:
    return str(_SCRIPTS_DIR / "_python.sh")


def _phase_manager(*args: str) -> dict:
    """Invoke phase_manager.py with --json and return its parsed output.

    Raises CalledProcessError on non-zero exit. Caller decides what to do
    with the failure (typically: print stderr, exit non-zero).
    """
    cmd = ["sh", _python_shim(), str(_SCRIPTS_DIR / "_run.py"),
           "scripts/crew/phase_manager.py", *args]
    out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    # phase_manager prints JSON to stdout when --json passed; tolerate prelude.
    last_line = out.strip().splitlines()[-1] if out.strip() else "{}"
    try:
        return json.loads(last_line)
    except json.JSONDecodeError:
        return {"raw": out}


def find_active_project() -> dict | None:
    """Return the active project record or None when no active project exists.

    `phase_manager find-active --json` prints `{}` (or `{"slug": null}`)
    when nothing is active; treat both as "none."
    """
    try:
        cmd = ["sh", _python_shim(), str(_SCRIPTS_DIR / "_run.py"),
               "scripts/crew/crew.py", "find-active", "--json"]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.PIPE)
        last_line = out.strip().splitlines()[-1] if out.strip() else "{}"
        record = json.loads(last_line)
        if not record or not record.get("slug"):
            return None
        return record
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


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
    description_quoted = "> " + description.strip().replace("\n", "\n> ")
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

    # Conflict check — fail fast with structured info if the parent didn't
    # supply --on-conflict resolution.
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

    if existing and args.on_conflict == "switch":
        try:
            pause_existing_project(conflicting_slug)
        except subprocess.CalledProcessError as exc:
            print(f"error: pause_existing_project failed: {exc}", file=sys.stderr)
            return 1
    if args.on_conflict in ("resume", "cancel"):
        # Parent should have aborted before calling us — but if we got here,
        # surface a clear no-op response.
        sys.stderr.write(json.dumps({
            "noop": True,
            "reason": f"on_conflict={args.on_conflict} — caller should not create new project",
        }) + "\n")
        return 1

    # Create the project shell (unless we're in a no-op resume/cancel path).
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
