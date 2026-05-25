#!/usr/bin/env python3
"""compile.py — the wicked-garden compiler emit stage.

Phase 0 proved a single repo-agnostic detector can infer a repo's bindings
(``detect.py``) and that detect→declare-contract→record→cross-check works
end-to-end (``wire_vault.py``). But ``wire_vault`` is a *probe*: it cleans up
after itself, leaving the target repo untouched. This is the *emitter*: it
writes a **persistent, self-contained harness** into the target repo.

The thesis, made concrete:

    wicked-garden = a compiler that emits a small repo-native harness
                  = compiled bindings + compiled enforcement + a trigger
                    over a *utility* (wicked-vault) it never compiles.

What gets emitted into ``<repo>/.wicked/``:

  - ``bindings.json``  — the detected bindings (provenance; what we saw).
  - ``contract.json``  — the vault contract: the repo's real test command,
                         pinned, as a ``tests-pass`` claim → ``exit_code_eq:0``.
                         This is the **compiled binding**.
  - ``gate.py``        — a stdlib-only, dependency-free harness that resolves
                         the vault via ``npx`` (or ``WICKED_VAULT_BIN``), then
                         init → declare-contract → record --run → cross-check.
                         Exit 0 == the build's claims re-derive. This is the
                         **compiled enforcement** + the **trigger** a CI step or
                         pre-commit hook invokes. It imports NOTHING from
                         wicked-garden — the garden compiled it and left.
  - ``README.md``      — what this is and how to wire it into CI / pre-commit.

The on-switch rule holds: the vault (the *tool*) is resolved at runtime via
npx and is fully skippable by the operator; its *trigger* (gate.py in CI) is
what the compiler bakes in and what is not skippable once wired.

Stdlib-only. The emitted gate is stdlib-only too, so it runs in any repo's
CI with zero deps beyond node+npx (which the vault needs anyway).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "phase0"))
import detect as _detect  # noqa: E402  (phase0/detect.py — the proven binding detector)

# A detected test command below this confidence is emitted but flagged: the
# harness still works, but a human should confirm the command is right.
_LOW_CONFIDENCE = 0.6


# ---------------------------------------------------------------------------
# Binding → contract
# ---------------------------------------------------------------------------

# Each detected command becomes one required claim. `tests-pass` is the core
# claim and is always present (flagged unconfigured if no test command was
# found); lint/build claims are added only when actually detected — pinning a
# command the repo doesn't have would make the gate fail forever.
_CLAIM_MAP = [
    ("tests-pass", "test-run", "test_command", True),
    ("lint-clean", "lint-run", "lint_command", False),
    ("build-clean", "build-run", "build_command", False),
]


def claim_specs(bindings: dict) -> list[dict]:
    """Detected commands → claim specs {claim_id, kind, command, source, confidence}."""
    specs = []
    for claim_id, kind, key, always in _CLAIM_MAP:
        b = bindings.get(key) or {}
        cmd = b.get("value")
        if always or cmd:
            specs.append({
                "claim_id": claim_id, "kind": kind, "command": cmd,
                "source": b.get("source"), "confidence": b.get("confidence"),
            })
    return specs


def derive_contract(bindings: dict) -> dict:
    """Turn detected bindings into a multi-claim wicked-vault contract spec.

    Each detected command (test / lint / build) becomes a required claim
    pinned (G8) to an ``exit_code_eq:0`` verifier. The gate then means "this
    build is actually clean" — re-derived at gate time — not merely "tests ran".
    """
    specs = claim_specs(bindings)
    required = [
        {
            "claim_id": s["claim_id"],
            "kind": s["kind"],
            "source_pin": s["command"],
            "verifier": {"kind": "exit_code_eq", "params": {"code": 0}},
            "required": True,
        }
        for s in specs
    ]
    return {
        "required_evidence": required,
        "origin": "wicked-garden:compiler:emit",
        "_provenance": {
            "ecosystem": bindings["test_command"].get("ecosystem"),
            "claims": {s["claim_id"]: {"command": s["command"],
                                       "source": s["source"],
                                       "confidence": s["confidence"]} for s in specs},
            "test_command_ambiguity": bindings["test_command"].get("ambiguity"),
        },
    }


# ---------------------------------------------------------------------------
# The emitted harness (self-contained; imports nothing from wicked-garden)
# ---------------------------------------------------------------------------

_GATE_TEMPLATE = '''#!/usr/bin/env python3
"""gate.py — EMITTED by the wicked-garden compiler. DO NOT hand-edit bindings.

A repo-native build gate. It re-derives this build's claims against frozen
acceptance criteria using wicked-vault — it never trusts a cached or
self-asserted "done". This script depends on NOTHING but the Python stdlib
and a resolvable wicked-vault CLI (via npx, or the WICKED_VAULT_BIN env).
wicked-garden is not required to run it.

Flow: init (idempotent) -> declare-contract (.wicked/contract.json)
   -> record --run each claim's command (capture fresh exit codes NOW)
   -> cross-check (re-run the pure verifiers; exit 0 == all PASS).

Usage:
  python3 .wicked/gate.py            # record a fresh run, then gate
  python3 .wicked/gate.py --check    # gate on existing evidence (no new run)
  python3 .wicked/gate.py --dry-run  # print compiled bindings, do nothing
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess  # noqa: S404 — argv lists, shell=False
import sys
import tempfile
from pathlib import Path

# ---- COMPILED BINDINGS (repo-specific; emitted, not hand-written) ----
REPO = {repo!r}
SCOPE = {scope!r}
PHASE = "build"
# Each claim: re-derived by running `command` and checking it exits 0.
CLAIMS = {claims!r}
# ----------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent  # repo root (.wicked/ is one down)
_CONTRACT = Path(__file__).resolve().parent / "contract.json"


def _vault_prefix():
    """Resolve the wicked-vault CLI argv prefix. npx is the portable default
    so this harness works on a fresh checkout with no global install."""
    env = os.environ.get("WICKED_VAULT_BIN", "").strip()
    if env:
        return ["node", env] if env.endswith((".mjs", ".js")) else [env]
    found = shutil.which("wicked-vault")
    if found:
        return [found]
    if shutil.which("npx"):
        return ["npx", "--yes", "wicked-vault"]
    return None


def _vault(prefix, args, timeout=600):
    proc = subprocess.run(  # noqa: S603 — argv list, shell=False
        prefix + args, cwd=str(_ROOT), capture_output=True, text=True, timeout=timeout,
    )
    out = proc.stdout.strip()
    try:
        parsed = json.loads(out) if out else {{}}
    except json.JSONDecodeError:
        parsed = {{"_raw": out, "_stderr": proc.stderr.strip()[:400]}}
    return proc.returncode, parsed


def main(argv) -> int:
    dry = "--dry-run" in argv
    check_only = "--check" in argv

    if dry:
        print(json.dumps({{
            "repo": REPO, "scope": SCOPE, "phase": PHASE, "claims": CLAIMS,
            "contract": json.loads(_CONTRACT.read_text()) if _CONTRACT.exists() else None,
        }}, indent=2))
        return 0

    prefix = _vault_prefix()
    if prefix is None:
        print(json.dumps({{"gate": "unavailable",
            "error": "wicked-vault not resolvable (need npx or WICKED_VAULT_BIN); "
                     "install: npm i -g wicked-vault"}}))
        return 1  # fail closed — never self-assert a PASS

    _vault(prefix, ["init"])  # idempotent
    if _CONTRACT.exists():
        _vault(prefix, ["declare-contract", "--scope", SCOPE, "--phase", PHASE,
                        "--spec", str(_CONTRACT)])

    if not check_only:
        runnable = [c for c in CLAIMS if c.get("command")]
        if not runnable:
            print(json.dumps({{"gate": "unconfigured",
                "error": "no runnable command was detected for any claim; "
                         "edit .wicked/gate.py + contract.json"}}))
            return 1
        for c in runnable:
            _vault(prefix, ["record", "--scope", SCOPE, "--phase", PHASE,
                            "--claim", c["claim"], "--kind", c["kind"],
                            "--source", c["command"],
                            "--criteria", c["claim"] + ": `" + c["command"] + "` exits 0",
                            "--verifier", "exit_code_eq:0", "--run"])

    rc, cc = _vault(prefix, ["cross-check", "--scope", SCOPE, "--phase", PHASE])
    overall = cc.get("overall") if isinstance(cc, dict) else None
    print(json.dumps({{"gate": "vault-cross-check", "overall": overall,
                       "scope": SCOPE, "phase": PHASE,
                       "claims": cc.get("claims") if isinstance(cc, dict) else None}},
                      indent=2))
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
'''


_README_TEMPLATE = '''# .wicked/ — emitted build gate (wicked-garden compiler)

This directory was **emitted** by the wicked-garden compiler from this repo's
detected bindings. It is self-contained: the gate depends only on the Python
stdlib and a resolvable [wicked-vault](https://www.npmjs.com/package/wicked-vault)
CLI (`npx wicked-vault`). wicked-garden itself is **not** required to run it.

## What it does

`gate.py` re-derives this build's claims instead of trusting a self-asserted
"done": it runs each detected command (test / lint / build), captures the real
exit code, and re-runs a pure verifier through the vault. Exit 0 means every
claim re-derives.

- **Repo:** `{repo}`
- **Vault scope:** `{scope}` · phase `build`

### Claims this gate re-derives

{claims_md}
{flag_block}
## Run it

```bash
python3 .wicked/gate.py            # record a fresh run, then gate (exit 0 = PASS)
python3 .wicked/gate.py --check    # gate on existing evidence, no new run
python3 .wicked/gate.py --dry-run  # show the compiled bindings
```

## Wire it into CI

```yaml
# .github/workflows — minimal
- run: python3 .wicked/gate.py
```

Or as a pre-push hook (`.git/hooks/pre-push`): `python3 .wicked/gate.py`.

## Files

- `bindings.json` — what the detector saw (provenance).
- `contract.json` — the vault contract: one required claim per detected
  command (test / lint / build), each pinned to its command + `exit_code_eq:0`.
  Edit this to add claims/verifiers.
- `gate.py` — the harness (compiled enforcement + trigger). Re-emit rather
  than hand-editing the bindings block.

Regenerate after the repo changes shape:
`python3 <wicked-garden>/scripts/compiler/compile.py <repo-root>`.
'''


def _claims_md(specs: list[dict]) -> str:
    rows = []
    for s in specs:
        cmd = f"`{s['command']}`" if s.get("command") else "_(none detected)_"
        rows.append(f"- `{s['claim_id']}` → {cmd}  "
                    f"_({s.get('source')}, confidence {s.get('confidence')})_")
    return "\n".join(rows)


def _flag_block(bindings: dict, specs: list[dict]) -> str:
    notes = []
    for s in specs:
        if s.get("command") and (s.get("confidence") or 0) < _LOW_CONFIDENCE:
            notes.append(
                f"- ⚠️ **Low confidence** for `{s['claim_id']}` "
                f"(`{s['command']}`, {s.get('confidence')}). Inferred, not declared "
                "— confirm before relying on the gate; fix in `contract.json` + `gate.py`."
            )
        if not s.get("command") and s["claim_id"] == "tests-pass":
            notes.append(
                "- ⚠️ **No test command detected** — `tests-pass` will fail closed "
                "(MISSING) until you set a command in `contract.json` + `gate.py`."
            )
    tc = bindings["test_command"]
    if tc.get("ambiguity"):
        notes.append(f"- ⚠️ **Ambiguity:** {tc['ambiguity']} (alt: `{tc.get('alt')}`).")
    return ("\n".join(notes) + "\n") if notes else ""


# ---------------------------------------------------------------------------
# Emit
# ---------------------------------------------------------------------------

def compile_repo(repo_root: str, out_subdir: str = ".wicked") -> dict:
    """Detect bindings and emit the harness into ``<repo>/<out_subdir>/``.

    Returns a manifest: the emitted files, the derived scope, and
    ``needs_review`` (True when a binding was inferred at low confidence).
    """
    root = Path(repo_root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")

    bindings = _detect.detect(str(root))
    contract = derive_contract(bindings)
    specs = claim_specs(bindings)
    scope = root.name

    out = root / out_subdir
    out.mkdir(parents=True, exist_ok=True)

    (out / "bindings.json").write_text(json.dumps(bindings, indent=2))
    (out / "contract.json").write_text(json.dumps(contract, indent=2))

    gate_claims = [{"claim": s["claim_id"], "kind": s["kind"], "command": s["command"]}
                   for s in specs]
    (out / "gate.py").write_text(_GATE_TEMPLATE.format(
        repo=bindings["repo"], scope=scope, claims=gate_claims,
    ))

    (out / "README.md").write_text(_README_TEMPLATE.format(
        repo=bindings["repo"], scope=scope,
        claims_md=_claims_md(specs), flag_block=_flag_block(bindings, specs),
    ))

    tc = bindings["test_command"]
    needs_review = (
        not tc.get("value")  # no test command at all
        or any(s.get("command") and (s.get("confidence") or 0) < _LOW_CONFIDENCE
               for s in specs)
        or bool(tc.get("ambiguity"))
    )

    return {
        "repo": bindings["repo"],
        "root": str(root),
        "scope": scope,
        "out_dir": str(out),
        "emitted": ["bindings.json", "contract.json", "gate.py", "README.md"],
        "claims": {s["claim_id"]: s["command"] for s in specs},
        "needs_review": needs_review,
        "bindings": bindings,
    }


# ---------------------------------------------------------------------------
# Triggers — what FIRES the gate. The gate is the compiled enforcement; a
# trigger is what makes it non-skippable once wired. We compile the trigger;
# we never compile the tool (the vault is resolved at runtime via npx).
# ---------------------------------------------------------------------------

_HOOK_START = "# >>> wicked-gate (managed by wicked-garden) >>>"
_HOOK_END = "# <<< wicked-gate <<<"
_HOOK_BLOCK = f'''{_HOOK_START}
# Re-derives this build's claims via .wicked/gate.py before allowing a push.
# Delete this block (or the file) to disable; edit .wicked/gate.py to retune.
_root="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -n "$_root" ] && [ -f "$_root/.wicked/gate.py" ]; then
  python3 "$_root/.wicked/gate.py" || {{
    echo "wicked-gate: build claims do not re-derive — push blocked." >&2
    exit 1
  }}
fi
{_HOOK_END}'''

_CI_MARKER = "generated-by: wicked-garden:compiler:emit"

# The vault needs node/npx everywhere; the repo's own toolchain is added per
# detected ecosystem so `gate.py` can actually run the test command in CI.
_CI_SETUP = {
    "node": "      - uses: actions/setup-node@v4\n        with:\n          node-version: '20'\n",
    "go": ("      - uses: actions/setup-node@v4\n        with:\n          node-version: '20'\n"
           "      - uses: actions/setup-go@v5\n        with:\n          go-version: 'stable'\n"),
    "python": ("      - uses: actions/setup-node@v4\n        with:\n          node-version: '20'\n"
               "      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.x'\n"),
    "rust": ("      - uses: actions/setup-node@v4\n        with:\n          node-version: '20'\n"
             "      - uses: dtolnay/rust-toolchain@stable\n"),
}
_CI_SETUP_DEFAULT = ("      - uses: actions/setup-node@v4\n        with:\n          node-version: '20'\n"
                     "      # TODO: add your toolchain setup so .wicked/gate.py can run the tests\n")


def _ci_workflow(ecosystem: str | None) -> str:
    setup = _CI_SETUP.get(ecosystem or "", _CI_SETUP_DEFAULT)
    return (
        f"# {_CI_MARKER}  (safe to re-emit; edit .wicked/gate.py or contract.json instead)\n"
        "name: wicked-gate\n"
        "on: [push, pull_request]\n"
        "jobs:\n"
        "  gate:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        f"{setup}"
        "      - name: re-derive build claims (wicked-vault)\n"
        "        run: python3 .wicked/gate.py\n"
    )


def _install_pre_push_hook(root: Path) -> dict:
    git_dir = root / ".git"
    if not git_dir.exists():
        return {"trigger": "pre-push-hook", "status": "skipped", "reason": "not a git repo"}
    hooks = git_dir / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-push"
    existing = hook.read_text(encoding="utf-8") if hook.exists() else ""

    if _HOOK_START in existing:
        # Replace our managed region in place (idempotent re-emit).
        pre = existing.split(_HOOK_START)[0]
        post = existing.split(_HOOK_END, 1)[1] if _HOOK_END in existing else ""
        text, status = pre + _HOOK_BLOCK + post, "updated"
    elif existing.strip():
        # Foreign hook present — preserve it, append our block. Never clobber.
        text, status = existing.rstrip() + "\n\n" + _HOOK_BLOCK + "\n", "appended"
    else:
        text, status = "#!/bin/sh\n" + _HOOK_BLOCK + "\n", "created"

    hook.write_text(text, encoding="utf-8")
    hook.chmod(0o755)
    return {"trigger": "pre-push-hook", "status": status, "path": str(hook)}


def _install_ci_workflow(root: Path, ecosystem: str | None) -> dict:
    wf_dir = root / ".github" / "workflows"
    wf = wf_dir / "wicked-gate.yml"
    if wf.exists() and _CI_MARKER not in wf.read_text(encoding="utf-8"):
        # A foreign file owns this name — do not overwrite hand-authored CI.
        return {"trigger": "ci-workflow", "status": "skipped",
                "reason": "wicked-gate.yml exists but is not wicked-generated", "path": str(wf)}
    status = "updated" if wf.exists() else "created"
    wf_dir.mkdir(parents=True, exist_ok=True)
    wf.write_text(_ci_workflow(ecosystem), encoding="utf-8")
    return {"trigger": "ci-workflow", "status": status, "path": str(wf)}


def install_triggers(repo_root: str, kinds: list[str], ecosystem: str | None = None) -> list[dict]:
    """Install the requested trigger surfaces. ``kinds`` ⊆ {"hook", "ci"}.

    Idempotent and non-destructive: the pre-push hook appends to (never
    clobbers) a foreign hook and replaces only its own managed block; the CI
    workflow refuses to overwrite a same-named file it did not generate.
    """
    root = Path(repo_root).resolve()
    results = []
    if "hook" in kinds:
        results.append(_install_pre_push_hook(root))
    if "ci" in kinds:
        results.append(_install_ci_workflow(root, ecosystem))
    return results


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="wicked-garden compiler — emit a repo-native gate.")
    p.add_argument("repo_root")
    p.add_argument("--out", default=".wicked", help="harness subdir (default .wicked)")
    p.add_argument("--trigger", default="",
                   help="comma list of triggers to install: hook,ci (or 'all'). "
                        "Default: emit harness only (no triggers).")
    a = p.parse_args()

    manifest = compile_repo(a.repo_root, a.out)

    kinds_raw = [k.strip() for k in a.trigger.split(",") if k.strip()]
    kinds = ["hook", "ci"] if "all" in kinds_raw else kinds_raw
    if kinds:
        manifest["triggers"] = install_triggers(
            a.repo_root, kinds, ecosystem=manifest["bindings"]["test_command"].get("ecosystem"))

    print(json.dumps({k: v for k, v in manifest.items() if k != "bindings"}, indent=2))
