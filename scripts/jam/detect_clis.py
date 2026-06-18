#!/usr/bin/env python3
"""
detect_clis.py — detect & probe agentic LLM CLIs for the council.

Reads ``agentic_cli_registry.py`` and answers two questions the council needs:

  1. Which registered CLIs are INSTALLED on this machine (``shutil.which``)?
  2. With ``--probe``: which installed CLIs are actually USABLE right now —
     i.e. running their headless form (+ trust flags) on a trivial prompt
     returns a sane reply — vs INSTALLED-BUT-UNUSABLE (auth revoked, no
     provider configured, daemon down, …)?

The probe is the difference between "the binary is on PATH" and "the council
can get a real answer out of it". A CLI can be installed yet 401, or print
"no provider configured", or fail to reach a local daemon. Those seats must
NOT be counted toward quorum.

Safety / cross-platform contract (mirrors _capability_registry.py + CLAUDE.md):
  * stdlib only — no third-party imports.
  * detection via ``shutil.which``.
  * each probe runs with ``subprocess.run(..., timeout=N, stdin=DEVNULL,
    cwd=<fresh tempdir under tempfile.gettempdir()>)`` so a hanging CLI is
    bounded, nothing reads our stdin, and no CLI mutates the real project.
  * never perl/bash-isms, never a bare ``/tmp``.

Modes:
  detect_clis.py                 # PATH scan, human output
  detect_clis.py --json          # PATH scan, JSON
  detect_clis.py --probe         # PATH scan + usability probe (JSON-capable)
  detect_clis.py --list          # dump the registry (no detection)
  detect_clis.py --list --json   # registry dump as JSON

Output JSON shape (--probe):
  {
    "detected":   [ {key, display_name, binary, resolved_path, category,
                     confidence, enabled_for_council, version}, ... ],
    "usable":     [ "<key>", ... ],
    "unusable":   [ {"cli": "<key>", "reason": "<class>: <detail>"}, ... ],
    "collisions": [ {"binary": "...", "keys": [...]}, ... ]
  }
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

# Import the registry. Works both when run as a file from anywhere
# (sys.path bootstrap) and when imported as a module.
try:
    from agentic_cli_registry import (  # type: ignore
        AGENTIC_CLI_REGISTRY,
        AgenticCLI,
        detect as registry_detect,
    )
except ModuleNotFoundError:  # pragma: no cover — path bootstrap for direct runs
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from agentic_cli_registry import (  # type: ignore
        AGENTIC_CLI_REGISTRY,
        AgenticCLI,
        detect as registry_detect,
    )


# Trivial prompt: cheap, deterministic, and the reply is easy to sanity-check.
PROBE_PROMPT = "Reply with the single word: pong"

# Per-CLI probe timeout (seconds). Agentic coders spin up tools/MCP and can be
# slow on a cold start; this bounds a hang (e.g. cursor-agent `-p`) without
# starving a legitimately-slow-but-working CLI. Local runners get longer
# because first-token latency on a cold model load is high.
DEFAULT_TIMEOUT = 45
LOCAL_RUNNER_TIMEOUT = 60

# ---------------------------------------------------------------------------
# Error-signature classification.
# A CLI that is installed-but-unusable fails in a recognisable way. We match
# stdout+stderr (lower-cased) against these signatures to label WHY a seat is
# unusable, so the council can tell the user "codex: auth revoked" rather than
# a generic failure. Order matters: first match wins.
# ---------------------------------------------------------------------------

_UNUSABLE_SIGNATURES: list[tuple[str, re.Pattern[str]]] = [
    (
        "auth",
        re.compile(
            r"\b(401|403|unauthor|authentication (failed|required)|not (logged|signed) in"
            r"|please (log ?in|sign ?in|run .*login)|invalid api key|api key (not|is missing)"
            r"|expired (token|credential)|forbidden|access denied"
            r"|credentials? (not found|missing|expired)|re-?authenticate)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "no-provider",
        re.compile(
            r"\b(no (provider|model) (configured|set|selected|available)"
            r"|no api key|set (the )?\w*_?api_key|missing .*api[_ ]?key"
            r"|configure (a )?(provider|model|api key)|run .*configure"
            r"|no default model|model not (found|configured))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "daemon-down",
        re.compile(
            r"\b(could not connect|connection refused|connection error"
            r"|failed to connect|daemon (not|isn'?t) running|is the server running"
            r"|ollama (server|app) (not|isn'?t) running|dial tcp|econnrefused"
            r"|no such model|model .* not found, try pulling)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "quota",
        re.compile(
            r"\b(quota|rate ?limit|429|insufficient (credit|funds|balance)"
            r"|billing|payment required|402)\b",
            re.IGNORECASE,
        ),
    ),
]

# If a CLI exits non-zero with no recognised signature, we still mark it
# unusable but with this generic label so the seat is not silently trusted.
_GENERIC_UNUSABLE = "error"


def _classify_failure(
    returncode: int | None, combined: str, timed_out: bool
) -> tuple[str, str] | None:
    """Classify a probe run. Returns ``(reason_class, matched_line)`` for an
    unusable run, or ``None`` if the run looks usable.

    ``matched_line`` is the specific line that tripped the signature (e.g. the
    401 line), so the human-facing reason is honest rather than echoing a
    cosmetic banner line. A run is USABLE only when it did not time out, exited
    0, and produced non-trivial stdout free of a failure signature (some CLIs
    print the error to stdout yet still exit 0).
    """
    if timed_out:
        return ("timeout", "")
    lines = combined.splitlines()
    for label, pat in _UNUSABLE_SIGNATURES:
        for line in lines:
            if pat.search(line):
                return (label, line.strip())
        # Fall back to a whole-text match (signature spanning the buffer).
        if pat.search(combined):
            return (label, "")
    if returncode not in (0, None):
        return (_GENERIC_UNUSABLE, "")
    return None


def _looks_like_real_reply(stdout: str) -> bool:
    """A sane reply has some printable content beyond whitespace/banners.

    We do NOT require the literal word 'pong' — models phrase things their own
    way and some CLIs wrap output. We only require that *something* substantive
    came back, since auth/provider/daemon failures produce either empty stdout
    or an error string (already caught by signature matching)."""
    stripped = stdout.strip()
    return len(stripped) >= 2


def _probe_version(cli: AgenticCLI, timeout: int) -> str:
    """Capture the version string (disambiguates binary collisions like grok)."""
    try:
        proc = subprocess.run(
            cli.version_probe,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=min(timeout, 15),
        )
        out = (proc.stdout or proc.stderr or "").strip()
        # Keep it to the first line — version banners can be multi-line.
        return out.splitlines()[0].strip() if out else ""
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return ""


def _build_probe_argv(cli: AgenticCLI) -> list[str] | None:
    """Build the headless argv for a probe run: rendered template + trust flags.

    Returns None for CLIs that cannot be safely auto-probed with a trivial
    prompt (e.g. ollama needs a model name we don't know). Those are reported
    as detected but skipped by the probe with an explicit reason.
    """
    if cli.key == "ollama" or "{MODEL}" in cli.headless_invocation:
        # Local runners need a concrete pulled model; we won't guess one.
        return None

    rendered = cli.render(PROBE_PROMPT)
    try:
        import shlex

        argv = shlex.split(rendered, posix=(sys.platform != "win32"))
    except ValueError:
        return None
    if not argv:
        return None
    # Append trust flags AFTER the template so headless runs don't block on a
    # permission / trust / git-repo prompt.
    argv.extend(cli.trust_flags)
    return argv


def _probe_one(cli: AgenticCLI) -> dict:
    """Probe a single detected CLI. Returns {usable: bool, reason, version}."""
    timeout = LOCAL_RUNNER_TIMEOUT if cli.category == "local-runner" else DEFAULT_TIMEOUT
    version = _probe_version(cli, timeout)

    argv = _build_probe_argv(cli)
    if argv is None:
        return {
            "usable": False,
            "reason": "skipped: requires a model/daemon not auto-probeable (e.g. ollama needs a pulled model + running daemon)",
            "version": version,
        }

    tmpdir = tempfile.mkdtemp(prefix="wg-council-probe-")
    timed_out = False
    returncode: int | None = None
    stdout = ""
    stderr = ""
    try:
        proc = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tmpdir,
        )
        returncode = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = (exc.stderr or b"").decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    except (OSError, ValueError) as exc:
        return {"usable": False, "reason": f"error: could not launch ({exc})", "version": version}
    finally:
        # Best-effort cleanup of the scratch cwd (aider et al. drop cache files).
        try:
            import shutil as _sh

            _sh.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    combined = f"{stdout}\n{stderr}"
    classified = _classify_failure(returncode, combined, timed_out)
    if classified is None and _looks_like_real_reply(stdout):
        return {"usable": True, "reason": None, "version": version}

    if classified is None:
        # Exited 0 but produced nothing substantive — treat as unusable so the
        # council does not seat an empty responder.
        reason, matched = "empty-response", ""
    else:
        reason, matched = classified

    # Prefer the line that actually matched the failure signature (e.g. the
    # 401 line); fall back to the first non-empty line if nothing matched
    # (timeout / generic non-zero exit).
    detail = matched
    if not detail:
        for line in combined.splitlines():
            s = line.strip()
            if s:
                detail = s
                break
    detail = detail[:160]
    full = f"{reason}: {detail}" if detail else reason
    return {"usable": False, "reason": full, "version": version}


def run_detect(probe: bool) -> dict:
    """Detect installed CLIs and, if ``probe``, classify usable vs unusable."""
    base = registry_detect(probe=False)
    detected = base["detected"]
    collisions = base["collisions"]

    if not probe:
        return {"detected": detected, "collisions": collisions}

    usable: list[str] = []
    unusable: list[dict] = []
    for entry in detected:
        key = entry["key"]
        if key == "claude":
            # Claude is the in-process host, not an external seat. Record its
            # version for collision/audit purposes but don't probe it as a CLI.
            cli = AGENTIC_CLI_REGISTRY[key]
            entry["version"] = _probe_version(cli, DEFAULT_TIMEOUT)
            continue
        cli = AGENTIC_CLI_REGISTRY[key]
        result = _probe_one(cli)
        entry["version"] = result["version"]
        if result["usable"]:
            usable.append(key)
        else:
            unusable.append({"cli": key, "reason": result["reason"]})

    return {
        "detected": detected,
        "usable": usable,
        "unusable": unusable,
        "collisions": collisions,
    }


def list_registry() -> dict:
    """Dump the full registry as plain dicts (for --list)."""
    return {
        "clis": [asdict(cli) for cli in AGENTIC_CLI_REGISTRY.values()],
        "count": len(AGENTIC_CLI_REGISTRY),
    }


# ---------------------------------------------------------------------------
# Human-readable rendering
# ---------------------------------------------------------------------------

def _emit_human_list(reg: dict) -> None:
    sys.stdout.write(f"agentic CLI registry — {reg['count']} entries\n")
    for cli in reg["clis"]:
        flag = "" if cli["enabled_for_council"] else " [council-disabled]"
        conf = "" if cli["confidence"] == "verified" else f" ({cli['confidence']})"
        sys.stdout.write(
            f"  {cli['key']:<14} {cli['category']:<14} {cli['vendor']}{conf}{flag}\n"
        )


def _emit_human_detect(result: dict, probed: bool) -> None:
    detected = result["detected"]
    sys.stdout.write(f"detected {len(detected)} installed CLI(s):\n")
    usable = set(result.get("usable", []))
    unusable_map = {u["cli"]: u["reason"] for u in result.get("unusable", [])}
    for entry in detected:
        key = entry["key"]
        ver = entry.get("version", "")
        ver_s = f"  v={ver}" if ver else ""
        if not probed:
            status = ""
        elif key == "claude":
            status = "  [in-process host]"
        elif key in usable:
            status = "  USABLE"
        elif key in unusable_map:
            status = f"  UNUSABLE — {unusable_map[key]}"
        else:
            status = ""
        sys.stdout.write(f"  {key:<14} {entry['resolved_path']}{ver_s}{status}\n")

    if probed:
        sys.stdout.write(
            f"\nquorum: {len(usable)} usable external CLI(s)"
            + (
                " — full council"
                if len(usable) >= 2
                else " — below quorum (fallback to Task() subagent seats)"
            )
            + "\n"
        )

    if result.get("collisions"):
        sys.stdout.write("\nbinary collisions (disambiguate by version):\n")
        for c in result["collisions"]:
            sys.stdout.write(f"  {c['binary']}: {', '.join(c['keys'])}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detect & probe agentic LLM CLIs for the wicked-garden council."
    )
    parser.add_argument("--probe", action="store_true", help="run headless usability probe")
    parser.add_argument("--list", action="store_true", help="dump the registry and exit")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    args = parser.parse_args(argv)

    if args.list:
        reg = list_registry()
        if args.json:
            sys.stdout.write(json.dumps(reg, indent=2) + "\n")
        else:
            _emit_human_list(reg)
        return 0

    result = run_detect(probe=args.probe)
    if args.json:
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
    else:
        _emit_human_detect(result, probed=args.probe)
    return 0


if __name__ == "__main__":
    sys.exit(main())
