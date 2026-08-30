#!/usr/bin/env python3
"""qe campaign — degradation-scenario generator (TH-23, test-R19a).

The campaign's proven negative pattern, encoded as a generator archetype:
S19 (estate binary absent → the surface still answered, HONESTLY) and
S20 (daemon kill → named disconnect state + WS reconnect on restart) both
PASSED because the consumer told the truth about a broken dependency. This
module generalizes that pattern: for every DECLARED external dependency of a
campaign target, propose a break-it scenario whose pass bar is

    **honest error naming + zero crashes + recovery** —
    distinct honest answers for distinct absent states
    (e.g. 200 ``{graph: null}`` "binary missing" vs 404 "graph not built"),
    never a generic 500, never a fake success.

No qe specialist covers this layer (qe-chaos-test-engineer is
Toxiproxy/tc/infra-level per its SKILL.md); the campaign plan is where the
dependency inventory lives, so the generator is campaign glue.

Dependencies are DECLARED, never guessed: the input is an external-deps
declaration (see ``skills/qe/refs/campaign-degradation.md`` for the format).
Built-in break archetypes, one per dependency kind:

  - ``binary``    → *absent*   (S19 generalized: resolution paths empty)
  - ``daemon``    → *down*     (S20 generalized: process stopped / port closed)
  - ``state-dir`` → *readonly* (the ledger-dir negative: writes must fail loudly)
  - ``custom``    → caller supplies ``break`` and ``honest_signal`` explicitly

Generated artifacts follow the campaign stub doctrine (campaign_plan.py):
scenario-format v1.1 markdown whose placeholder step ``exit 1``s until a
human/agent authors the concrete break-verify-restore commands — a generated
degradation scenario can never silently PASS. Rungs carry
``isolation: exclusive`` (breaking a shared dependency is the schema's own
definition of exclusive) and cap claims at ``machinery-verified``.

Cross-platform: pure stdlib (json/pathlib/argparse), no shell.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_QE_SCRIPTS = Path(__file__).resolve().parent
for _p in (_REPO_ROOT / "scripts", _QE_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from campaign_plan import (  # noqa: E402
    CampaignPlanError,
    PLAN_FILENAME,
    SCENARIO_DIRNAME,
    plan_errors,
)

DEP_KINDS = ("binary", "daemon", "state-dir", "custom")

#: kind → (archetype slug, default break recipe, default honest signal,
#:          default recovery bar). The S19/S20/ledger-readonly negatives,
#: generalized. ``custom`` has no defaults on purpose — the caller declares.
ARCHETYPES = {
    "binary": (
        "absent",
        "Make the binary unresolvable on EVERY resolution path the consumer "
        "declares (PATH shadow, renamed file, or an override env var pointed "
        "at a nonexistent path) — partial breakage tests nothing.",
        "The consumer keeps answering and NAMES the missing binary — an "
        "answer DISTINCT from 'not yet built' and from every other absent "
        "state (the S19 rule: 200 {graph: null, reason names the binary} vs "
        "404 'graph not built'). Never a generic 500, never fabricated data.",
        "Restoring the binary returns the consumer to its healthy answer "
        "WITHOUT a consumer restart (or the restart requirement is named in "
        "the honest answer itself).",
    ),
    "daemon": (
        "down",
        "Stop the dependency daemon (SIGTERM) or point the consumer at a "
        "closed port — never at a DIFFERENT live daemon.",
        "The consumer reports a NAMED connection failure / disconnected "
        "state for this dependency (the S20 rule: the UI shows the "
        "disconnect state, APIs answer with an error naming the dependency) "
        "— never a fake success, never an unhandled crash.",
        "Restarting the daemon reconnects the consumer WITHOUT a consumer "
        "restart (S20's WS-reconnect bar).",
    ),
    "state-dir": (
        "readonly",
        "Revoke write permission on the state directory (chmod 555 / "
        "read-only ACL) while the consumer is running.",
        "Writes fail with an error NAMING the directory and the operation; "
        "reads still serve what exists; no partial/corrupt state is left "
        "behind; never a fake write success.",
        "Restoring write permission lets the next write succeed WITHOUT a "
        "consumer restart, and no earlier 'successful' write turns out to "
        "have been dropped.",
    ),
}

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_RUNG_CATEGORIES = ("api", "ui", "desktop")


class DegradationError(ValueError):
    """The deps declaration or the target plan violated the contract."""


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# --------------------------------------------------------------------------
# deps declaration — validation
# --------------------------------------------------------------------------

def load_deps(doc: dict) -> list[dict]:
    """Validate an external-deps declaration; return the normalized deps.

    Fail-closed: every defect raises (never a silently-skipped dependency —
    a skipped dependency is a degradation scenario that never exists).
    """
    if not isinstance(doc, dict) or not isinstance(doc.get("deps"), list):
        raise DegradationError(
            "external-deps declaration must be an object with a deps[] array "
            "(see skills/qe/refs/campaign-degradation.md)"
        )
    deps: list[dict] = []
    seen: set[str] = set()
    for i, raw in enumerate(doc["deps"]):
        where = f"deps[{i}]"
        if not isinstance(raw, dict):
            raise DegradationError(f"{where}: must be an object")
        dep = dict(raw)
        did = dep.get("id")
        if not isinstance(did, str) or not _ID_RE.match(did):
            raise DegradationError(
                f"{where}: id must be kebab-case ([a-z0-9-]) — got {did!r}"
            )
        if did in seen:
            raise DegradationError(f"{where}: duplicate dep id {did!r}")
        seen.add(did)
        kind = dep.get("kind")
        if kind not in DEP_KINDS:
            raise DegradationError(
                f"{where} ({did}): kind must be one of {'|'.join(DEP_KINDS)} "
                f"— got {kind!r}"
            )
        if not isinstance(dep.get("name"), str) or not dep["name"]:
            raise DegradationError(
                f"{where} ({did}): name (the human name of the dependency) "
                "is required"
            )
        if kind == "custom":
            for field in ("break", "honest_signal"):
                if not isinstance(dep.get(field), str) or not dep[field]:
                    raise DegradationError(
                        f"{where} ({did}): kind 'custom' requires an explicit "
                        f"{field!r} — the generator has no default archetype "
                        "for it"
                    )
        category = dep.get("category", "api")
        if category not in _RUNG_CATEGORIES:
            raise DegradationError(
                f"{where} ({did}): category must be one of "
                f"{'|'.join(_RUNG_CATEGORIES)} — got {category!r}"
            )
        dep["category"] = category
        deps.append(dep)
    if not deps:
        raise DegradationError("external-deps declaration has zero deps")
    return deps


# --------------------------------------------------------------------------
# generation — capability entries + rungs + scenario markdown
# --------------------------------------------------------------------------

def _resolved(dep: dict) -> tuple[str, str, str, str]:
    """(archetype, break recipe, honest signal, recovery bar) for one dep —
    caller-declared fields override the archetype defaults."""
    if dep["kind"] == "custom":
        arch = dep.get("archetype", "custom-break")
        return (
            _slug(arch) or "custom-break",
            dep["break"],
            dep["honest_signal"],
            dep.get(
                "recovery",
                "Restoring the dependency returns the consumer to its "
                "healthy signal without a consumer restart.",
            ),
        )
    arch, brk, honest, recovery = ARCHETYPES[dep["kind"]]
    return (
        arch,
        dep.get("break", brk),
        dep.get("honest_signal", honest),
        dep.get("recovery", recovery),
    )


def degradation_capability(dep: dict) -> dict:
    """The capability-inventory entry for one declared dependency.

    source 'human' — the dependency was DECLARED by the operator (that is
    what makes it verified rather than proposed): the entry documents what
    honest degradation looks like when this dependency is absent.
    """
    arch, brk, honest, recovery = _resolved(dep)
    cap = {
        "id": f"degradation-{dep['id']}",
        "surface": dep.get(
            "consumer_surface",
            f"honest degradation of the target when external dependency "
            f"'{dep['name']}' ({dep['kind']}) is {arch}",
        ),
        "apis": dep.get(
            "healthy_signal",
            f"healthy signal undeclared — author it before executing "
            f"(the recovery assertion needs a healthy baseline for "
            f"'{dep['name']}')",
        ),
        "test_shape": (
            f"PASS = honest error naming, zero crashes, recovery. "
            f"Broken state ({arch}): {honest} Recovery: {recovery}"
        ),
        "needs": f"break recipe: {brk} Run EXCLUSIVE — breaking a shared "
        "dependency must never overlap another rung (TH-22).",
        "source": "human",
        "status": "verified",
    }
    if dep.get("citations"):
        cap["citations"] = list(dep["citations"])
    return cap


def degradation_rung(dep: dict, scenario_path: str | None = None) -> dict:
    """The plan rung for one declared dependency (schema format v2)."""
    arch, brk, honest, recovery = _resolved(dep)
    rung = {
        "id": f"degradation-{dep['id']}-{arch}",
        "title": f"Degradation — {dep['name']} {arch}: honest error naming, "
        "no crash, no fake success",
        "category": dep["category"],
        "capability_ids": [f"degradation-{dep['id']}"],
        "deps": [],
        "pass_criteria": {
            "terminal_state": (
                f"consumer still up and answering while '{dep['name']}' is "
                f"{arch} — zero crashes, zero restart loops"
            ),
            "artifact": (
                f"captured broken-state answer that NAMES '{dep['name']}' "
                "and is DISTINCT from every other absent state's answer "
                f"(never a generic 500, never a fake success): {honest}"
            ),
            "consumer_state": f"recovery proven by re-probe: {recovery}",
        },
        "claim_ceiling": "machinery-verified",
        # Breaking a shared dependency is the schema's own definition of
        # 'exclusive' (daemon kill/restart, migration, recovery rungs).
        "isolation": "exclusive",
        "status": "confirmed",
        "notes": f"break recipe ({dep['kind']}/{arch}): {brk}",
    }
    if scenario_path:
        rung["scenario_path"] = scenario_path
    return rung


def degradation_scenario_markdown(dep: dict, plan_name: str = "campaign") -> str:
    """Scenario-format v1.1 markdown for one dependency's break-it scenario.

    Stub doctrine (campaign_plan.scenario_stub_markdown): the placeholder
    step ``exit 1``s until the concrete break/verify/restore commands are
    authored — a generated degradation scenario can never silently PASS.
    """
    arch, brk, honest, recovery = _resolved(dep)
    name = _slug(f"{plan_name}-degradation-{dep['id']}-{arch}")

    def _block(text: str, indent: str) -> list[str]:
        """Wrap one logical sentence into consistently indented YAML |-lines."""
        words = text.split()
        lines_, cur = [], ""
        for w in words:
            if cur and len(indent) + len(cur) + 1 + len(w) > 78:
                lines_.append(f"{indent}{cur}")
                cur = w
            else:
                cur = f"{cur} {w}".strip()
        if cur:
            lines_.append(f"{indent}{cur}")
        return lines_

    category = (
        "browser" if dep["category"] == "ui"
        else "desktop" if dep["category"] == "desktop"
        else "api"
    )
    lines = [
        "---",
        f"name: {name}",
        "description: |",
        *_block(
            f"Degradation: external dependency '{dep['name']}' "
            f"({dep['kind']}) made {arch}. Pass bar: honest error naming + "
            "zero crashes + recovery — distinct honest answers for distinct "
            "absent states; never a generic 500, never a fake success "
            "(TH-23 / test-R19a, generalizing campaign S19/S20).",
            "  ",
        ),
        'version: "1.1"',
        f"category: {category}",
        "tags: [qe-campaign, degradation]",
        # breaking a shared dependency needs sole access to the target env
        "isolation: exclusive",
        "status: authored",
        "source: campaign-degradation-generator",
        "assertions:",
        "  - id: A1",
        "    description: |",
        *_block(
            f"honest error naming — while '{dep['name']}' is {arch}, the "
            "consumer's answer NAMES the dependency and is distinct from "
            f"every other absent state's answer. {honest}",
            "      ",
        ),
        "  - id: A2",
        "    description: |",
        *_block(
            "zero crashes — the consumer process stays up for the whole "
            "broken window: no unhandled exit, no crash/restart loop, no "
            "hung surface.",
            "      ",
        ),
        "  - id: A3",
        "    description: |",
        *_block(f"recovery — {recovery}", "      "),
        "---",
        "",
        "## Break recipe",
        "",
        f"{brk}",
        "",
        "## Steps",
        "",
        "1. Capture the HEALTHY baseline signal first (A3 needs it):",
        f"   {dep.get('healthy_signal', 'TODO(author): declare the healthy signal probe')}",
        "2. TODO(author): apply the break recipe above with concrete,",
        "   deterministic commands for THIS target (isolated instance only —",
        "   79xx port / scratch state dirs; NEVER a real daemon or real",
        "   state).",
        "3. TODO(author): probe the broken state and capture the answer —",
        "   assert A1 (named, distinct, honest) and A2 (consumer still up).",
        "4. TODO(author): restore the dependency, re-probe, assert A3",
        "   (healthy signal returns; no dropped writes pretending success).",
        "5. `exit 1` — the generated scenario fails until authored (never a",
        "   silent PASS).",
        "",
        "## Evidence expected",
        "",
        "- healthy baseline capture (before the break)",
        f"- broken-state capture naming '{dep['name']}' (A1) + consumer "
        "liveness proof (A2)",
        "- recovery capture matching the healthy baseline (A3)",
        "",
    ]
    return "\n".join(lines)


def generate(deps: list[dict], plan_name: str = "campaign") -> dict:
    """capabilities + rungs + scenario file texts for a deps declaration."""
    capabilities = []
    rungs = []
    scenario_texts: dict[str, str] = {}
    for dep in deps:
        arch, _, _, _ = _resolved(dep)
        fname = _slug(f"{plan_name}-degradation-{dep['id']}-{arch}")
        rel = f"{SCENARIO_DIRNAME}/{fname}.md"
        capabilities.append(degradation_capability(dep))
        rungs.append(degradation_rung(dep, scenario_path=rel))
        scenario_texts[rel] = degradation_scenario_markdown(dep, plan_name)
    return {
        "capabilities": capabilities,
        "scenarios": rungs,
        "scenario_texts": scenario_texts,
    }


# --------------------------------------------------------------------------
# plan augmentation — fail-closed, spec-version-honest
# --------------------------------------------------------------------------

def augment_plan(
    plan: dict,
    deps: list[dict],
    *,
    after: str | None = None,
    allow_spec_bump: bool = False,
) -> dict:
    """Append degradation capabilities + rungs to an existing plan.

    Fail-closed rules:
      - a spec:1 plan is REFUSED unless ``allow_spec_bump`` — degradation
        rungs carry ``isolation: exclusive``, a spec-2 field; bumping a
        plan's format version silently is a versioning lie.
      - id collisions (capability or rung) are refused, never renamed.
      - ``after`` must name an existing rung; the degradation rungs then
        depend on it (they append at the END, so ladder order holds).
      - the augmented plan must pass campaign_plan.plan_errors in full.

    Returns {plan, scenario_texts}.
    """
    if plan.get("spec") == 1:
        if not allow_spec_bump:
            raise DegradationError(
                "plan is campaign-recon spec 1 — degradation rungs carry "
                "'isolation: exclusive' which requires spec 2. Re-emit the "
                "plan at spec 2 or pass --allow-spec-bump to bump it "
                "explicitly (never silently)."
            )
        plan = dict(plan)
        plan["spec"] = 2

    gen = generate(deps, plan_name=plan.get("name") or "campaign")

    existing_caps = {c.get("id") for c in plan.get("capabilities", [])}
    existing_rungs = {r.get("id") for r in plan.get("scenarios", [])}
    for cap in gen["capabilities"]:
        if cap["id"] in existing_caps:
            raise DegradationError(
                f"capability id {cap['id']!r} already exists in the plan — "
                "degradation entries are never silently renamed or merged"
            )
    for rung in gen["scenarios"]:
        if rung["id"] in existing_rungs:
            raise DegradationError(
                f"rung id {rung['id']!r} already exists in the plan — "
                "degradation entries are never silently renamed or merged"
            )

    if after is not None:
        if after not in existing_rungs:
            raise DegradationError(
                f"--after rung {after!r} does not name a rung in the plan"
            )
        for rung in gen["scenarios"]:
            rung["deps"] = [after]

    plan = dict(plan)
    plan["capabilities"] = list(plan.get("capabilities", [])) + gen["capabilities"]
    plan["scenarios"] = list(plan.get("scenarios", [])) + gen["scenarios"]

    errors = plan_errors(plan)
    if errors:
        raise DegradationError(
            "augmented plan does not conform to the campaign-recon format "
            "(nothing was written):\n" + "\n".join(errors)
        )
    return {"plan": plan, "scenario_texts": gen["scenario_texts"]}


def persist_augmented(result: dict, out_dir: Path) -> dict:
    """Write the augmented plan + generated scenario files under out_dir."""
    out_dir = Path(out_dir)
    written = {"plan": [], "scenarios": []}
    (out_dir / SCENARIO_DIRNAME).mkdir(parents=True, exist_ok=True)
    for rel, text in result["scenario_texts"].items():
        path = out_dir / rel
        path.write_text(text, encoding="utf-8")
        written["scenarios"].append(str(path))
    plan_path = out_dir / PLAN_FILENAME
    plan_path.write_text(
        json.dumps(result["plan"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    written["plan"].append(str(plan_path))
    return written


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="campaign_degradation",
        description="qe campaign degradation glue: break-it scenarios per "
        "declared external dependency (TH-23 / test-R19a)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_gen = sub.add_parser(
        "generate",
        help="emit degradation capabilities + rungs + scenario markdown for "
        "an external-deps declaration (JSON to stdout)",
    )
    p_gen.add_argument("--deps", type=Path, required=True)
    p_gen.add_argument("--plan-name", default="campaign")

    p_aug = sub.add_parser(
        "augment",
        help="append degradation rungs to an existing campaign-recon.json "
        "and write the generated scenario files (fail-closed)",
    )
    p_aug.add_argument("--deps", type=Path, required=True)
    p_aug.add_argument("--plan", type=Path, required=True)
    p_aug.add_argument(
        "--out",
        type=Path,
        required=True,
        help="campaign dir to write campaign-recon.json + scenarios/ into",
    )
    p_aug.add_argument("--after", default=None, help="existing rung id the degradation rungs depend on")
    p_aug.add_argument("--allow-spec-bump", action="store_true")

    args = parser.parse_args(argv)

    try:
        deps = load_deps(json.loads(args.deps.read_text(encoding="utf-8")))
        if args.cmd == "generate":
            gen = generate(deps, plan_name=args.plan_name)
            print(json.dumps(gen, indent=2, ensure_ascii=False))
            return 0
        # augment
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        result = augment_plan(
            plan,
            deps,
            after=args.after,
            allow_spec_bump=args.allow_spec_bump,
        )
        written = persist_augmented(result, args.out)
        print(json.dumps(written, indent=2))
        return 0
    except (DegradationError, CampaignPlanError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
