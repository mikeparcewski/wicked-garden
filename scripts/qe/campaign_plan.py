#!/usr/bin/env python3
"""qe campaign — recon + generation glue (TH-7, ADR 0006).

Deterministic helpers behind the `campaign` action of the `wicked-garden-qe`
router (`skills/qe/refs/campaign.md`). The agent performs the three-lens
recon (estate graph, docs recall, live probe); THIS module is the honest
assembler: it merges the lenses into a campaign plan that CONFORMS to
`schemas/campaign-recon.schema.json` (format v2; spec:1 plans still
validate — never a parallel format) and persists it plus scenario-format
v1.1 stubs.

Honesty rules enforced here, fail-closed (never by prose alone):

- **unindexed degradation** — a plan with no estate-lens entries carries
  `sources.estate: "unindexed"`; a plan claiming an estate-sourced capability
  while marked unindexed is rejected.
- **doc-derived claims are PROPOSED** — capabilities from the docs lens are
  forced to `status: "proposed"` (pending human review, the
  incident-to-scenario pending-review pattern), and a rung cannot be
  `confirmed` while any capability it certifies is still proposed.
- **the ladder is dependency-ordered** — deps reference only EARLIER rungs
  (the invariant JSON Schema cannot express).
- **rung↔capability binding resolves** — every `capability_ids` entry names a
  real inventory entry.
- **`isolation` is versioned** — the per-rung isolation annotation
  (shares-state | exclusive | stateless, TH-22) requires spec 2; a spec:1
  plan carrying it is rejected rather than silently reinterpreted.

Cross-platform: pure stdlib (json/pathlib/argparse), no shell.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from domain.validate_domain_model import _validate  # noqa: E402

SCHEMA_PATH = _REPO_ROOT / "schemas" / "campaign-recon.schema.json"

#: campaign-plan rung category → scenario-format category. As of
#: scenario-format v1.1 (TH-16 + TH-22, one shared bump) `desktop` maps too —
#: desktop stubs execute per the tier ladder in refs/scenario-format.md
#: (T0 crew-governed PTY now; T2 computer-use is exploratory and ALWAYS
#: reviewer-graded; T3 deferred in writing).
CATEGORY_MAP = {"api": "api", "ui": "browser", "desktop": "desktop"}

#: campaign-recon format version this assembler emits. spec:1 plans (no rung
#: `isolation`) remain valid inputs; `isolation` requires spec 2.
CURRENT_SPEC = 2

#: rung/scenario isolation classes (TH-22) and the documented default: a
#: missing annotation NEVER grants parallelism.
ISOLATION_VALUES = ("shares-state", "exclusive", "stateless")
DEFAULT_ISOLATION = "shares-state"

PLAN_FILENAME = "campaign-recon.json"
SCENARIO_DIRNAME = "scenarios"


class CampaignPlanError(ValueError):
    """A campaign plan violated the schema or an honesty invariant."""


# --------------------------------------------------------------------------
# validation — schema layer + the extra invariants
# --------------------------------------------------------------------------

def load_campaign_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def schema_errors(doc: Any) -> list[str]:
    """Draft-07-subset validation against schemas/campaign-recon.schema.json."""
    schema = load_campaign_schema()
    errors: list[str] = []
    _validate(doc, schema, "", schema, errors)
    return sorted(errors)


def ladder_errors(doc: dict) -> list[str]:
    """Topological-order + uniqueness invariants over scenarios[]."""
    errors: list[str] = []
    seen: set[str] = set()
    for i, rung in enumerate(doc.get("scenarios", []) or []):
        rid = rung.get("id")
        if rid in seen:
            errors.append(f"scenarios[{i}]: duplicate rung id {rid!r}")
        for dep in rung.get("deps", []) or []:
            if dep not in seen:
                errors.append(
                    f"scenarios[{i}] ({rid}): dep {dep!r} does not name an "
                    "earlier rung"
                )
        if isinstance(rid, str):
            seen.add(rid)
    return errors


def version_errors(doc: dict) -> list[str]:
    """Format-version invariants (TH-16 + TH-22 shared bump).

    `isolation` is a spec-2 field: a spec:1 plan carrying it is a versioning
    error, not something to reinterpret silently. (The enum itself is the
    schema layer's job.)
    """
    errors: list[str] = []
    if doc.get("spec") == 1:
        for i, rung in enumerate(doc.get("scenarios", []) or []):
            if isinstance(rung, dict) and "isolation" in rung:
                errors.append(
                    f"scenarios[{i}] ({rung.get('id')}): 'isolation' requires "
                    "campaign-recon spec 2 — bump the plan's spec (v1 plans "
                    "without isolation remain valid)"
                )
    return errors


def honesty_errors(doc: dict) -> list[str]:
    """The TH-7 provenance invariants (fail-closed, never prose-only)."""
    errors: list[str] = []
    caps = doc.get("capabilities", []) or []
    sources = doc.get("sources", {}) or {}

    cap_status: dict[str, str] = {}
    for i, cap in enumerate(caps):
        cid = cap.get("id")
        if isinstance(cid, str):
            cap_status[cid] = cap.get("status", "verified")
        src = cap.get("source")
        if src == "docs" and cap.get("status") != "proposed":
            errors.append(
                f"capabilities[{i}] ({cid}): doc-derived claims enter as "
                "status 'proposed' pending human review — got "
                f"{cap.get('status')!r}"
            )
        if src == "estate" and sources.get("estate") != "indexed":
            errors.append(
                f"capabilities[{i}] ({cid}): claims source 'estate' but "
                "sources.estate is not 'indexed' — an unindexed recon must "
                "not carry estate-lens entries"
            )
        if src == "docs" and sources.get("docs_recall") is not True:
            errors.append(
                f"capabilities[{i}] ({cid}): doc-derived entry present but "
                "sources.docs_recall is not true"
            )
        if src == "probe" and sources.get("live_probe") is not True:
            errors.append(
                f"capabilities[{i}] ({cid}): probe-derived entry present but "
                "sources.live_probe is not true"
            )

    for i, rung in enumerate(doc.get("scenarios", []) or []):
        rid = rung.get("id")
        for cid in rung.get("capability_ids", []) or []:
            if cid not in cap_status:
                errors.append(
                    f"scenarios[{i}] ({rid}): capability_ids entry {cid!r} "
                    "does not name a capability inventory entry"
                )
            elif (
                rung.get("status", "confirmed") == "confirmed"
                and cap_status[cid] == "proposed"
            ):
                errors.append(
                    f"scenarios[{i}] ({rid}): cannot be 'confirmed' while "
                    f"capability {cid!r} is still 'proposed' (pending review)"
                )
    return errors


def plan_errors(doc: Any) -> list[str]:
    """Every defect in the plan: schema + ladder order + honesty invariants."""
    errors = schema_errors(doc)
    if isinstance(doc, dict):
        errors += ladder_errors(doc)
        errors += honesty_errors(doc)
        errors += version_errors(doc)
    return errors


# --------------------------------------------------------------------------
# assembly — merge the three lenses into one conforming plan
# --------------------------------------------------------------------------

def _tag_lens(entries: Iterable[dict], source: str) -> list[dict]:
    tagged = []
    for entry in entries:
        cap = dict(entry)
        cap["source"] = source
        if source == "docs":
            # doc-derived claims are PROPOSED pending review — always.
            cap["status"] = "proposed"
        else:
            cap.setdefault("status", "verified")
        tagged.append(cap)
    return tagged


def assemble_plan(
    target: dict,
    *,
    estate_capabilities: Iterable[dict] = (),
    docs_capabilities: Iterable[dict] = (),
    probe_capabilities: Iterable[dict] = (),
    human_capabilities: Iterable[dict] = (),
    scenarios: Iterable[dict] = (),
    environment_manifest: dict | None = None,
    name: str | None = None,
    generated_at: str | None = None,
) -> dict:
    """Merge lens-tagged inventory entries + a rung ladder into a v1 plan.

    The `sources` block is DERIVED, never caller-asserted: `estate` is
    "indexed" iff the estate lens contributed entries — an empty estate lens
    degrades honestly to "unindexed" (docs+probe-only), never silently.
    """
    estate = _tag_lens(estate_capabilities, "estate")
    docs = _tag_lens(docs_capabilities, "docs")
    probe = _tag_lens(probe_capabilities, "probe")
    human = _tag_lens(human_capabilities, "human")

    capabilities = estate + probe + docs + human
    cap_status = {c.get("id"): c.get("status") for c in capabilities}

    rungs: list[dict] = []
    for rung in scenarios:
        rung = dict(rung)
        rung.setdefault("deps", [])
        if "status" not in rung:
            bound = rung.get("capability_ids", []) or []
            proposed = any(cap_status.get(cid) == "proposed" for cid in bound)
            rung["status"] = "proposed" if proposed else "confirmed"
        rungs.append(rung)

    plan: dict[str, Any] = {"spec": CURRENT_SPEC}
    if name:
        plan["name"] = name
    plan["generated_at"] = generated_at or (
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    plan["target"] = dict(target)
    plan["sources"] = {
        "estate": "indexed" if estate else "unindexed",
        "docs_recall": bool(docs),
        "live_probe": bool(probe),
    }
    plan["capabilities"] = capabilities
    plan["environment_manifest"] = dict(environment_manifest or {})
    plan["scenarios"] = rungs
    return plan


# --------------------------------------------------------------------------
# live-probe lens: crew's committed endpoint manifest
# --------------------------------------------------------------------------

def capabilities_from_endpoint_manifest(
    manifest: dict,
    manifest_path: str = "packages/crew/endpoint-manifest.json",
) -> list[dict]:
    """Probe-lens capability entries from a crew endpoint manifest.

    wicked-crew commits `packages/crew/endpoint-manifest.json`
    (`{version, apiTypesVersion, endpoints: [{method, path, ...}]}`) as a
    build artifact — a machine-readable source for the live-probe lens.
    Endpoints are grouped into one capability per REST resource.
    """
    endpoints = manifest.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        raise CampaignPlanError(
            f"{manifest_path}: not an endpoint manifest (no endpoints[])"
        )
    api_types = manifest.get("apiTypesVersion", "unknown")

    groups: dict[str, list[str]] = {}
    for ep in endpoints:
        method, path = ep.get("method"), ep.get("path")
        if not (isinstance(method, str) and isinstance(path, str)):
            raise CampaignPlanError(
                f"{manifest_path}: endpoint entry missing method/path: {ep!r}"
            )
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 3 and parts[0] == "api":
            resource = parts[2]  # /api/v1/<resource>/...
        else:
            # non-API surface (e.g. /ws, /ws/terminals/:id): first literal
            # segment, never a :param placeholder.
            literals = [p for p in parts if not p.startswith(":")]
            resource = literals[0] if literals else "root"
        groups.setdefault(resource, []).append(f"{method} {path}")

    caps = []
    for resource in sorted(groups):
        slug = re.sub(r"[^a-z0-9]+", "-", resource.lower()).strip("-")
        caps.append(
            {
                "id": f"api-{slug}",
                "surface": f"REST surface — {resource} endpoints "
                f"(from the committed endpoint manifest)",
                "apis": "; ".join(sorted(groups[resource]))
                + f" ({manifest_path}, apiTypesVersion {api_types})",
                "test_shape": "PASS = expected status WITH a content-bearing "
                "assertion on the response body (the runner lint rejects "
                "status-only assertions); negatives per manifest diffs",
                "needs": "isolated daemon on a 79xx port with scratch --db "
                "(never 7701/7810 or real state dirs)",
                "citations": [f"{manifest_path}:endpoints"],
            }
        )
    return caps


# --------------------------------------------------------------------------
# generation — scenario-format v1.1 stubs (never a parallel format)
# --------------------------------------------------------------------------

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def scenario_stub_markdown(rung: dict, plan: dict) -> str:
    """A scenario-format v1.1 markdown stub for one rung.

    The stub carries the rung's pass criteria as assertions and the
    provenance frontmatter of the pending-review pattern. The authoring
    agent fills `## Steps` with concrete commands; a stub left unedited
    fails its own placeholder step, so it can never silently PASS.
    """
    category = CATEGORY_MAP.get(rung.get("category", ""))
    if category is None:
        raise CampaignPlanError(
            f"rung {rung.get('id')!r}: category {rung.get('category')!r} has "
            "no scenario-format category mapping — bind a hand-authored "
            "scenario_path instead"
        )
    isolation = rung.get("isolation", DEFAULT_ISOLATION)
    if isolation not in ISOLATION_VALUES:
        raise CampaignPlanError(
            f"rung {rung.get('id')!r}: isolation {isolation!r} is not one of "
            f"{'|'.join(ISOLATION_VALUES)}"
        )
    plan_name = plan.get("name") or "campaign"
    name = _slug(f"{plan_name}-{rung['id']}")
    status = (
        "pending-review" if rung.get("status") == "proposed" else "authored"
    )
    pc = rung["pass_criteria"]
    caps = ", ".join(rung.get("capability_ids", []) or []) or "(unbound)"
    title = rung.get("title", rung["id"])
    lines = [
        "---",
        f"name: {name}",
        "description: |",
        f"  {title}",
        f"  Certifies capabilities: {caps}. Claim ceiling: "
        f"{rung['claim_ceiling']}.",
        'version: "1.1"',
        f"category: {category}",
        "tags: [qe-campaign]",
        # TH-22: explicit isolation in every stub — the rung's declared class,
        # else the conservative default (a missing annotation never grants
        # parallelism).
        f"isolation: {isolation}",
        f"status: {status}",
        "source: campaign-plan",
        f"authored_at: {plan.get('generated_at', '')}",
        "assertions:",
        "  - id: A1",
        f"    description: \"terminal_state: {pc['terminal_state']}\"",
        "  - id: A2",
        f"    description: \"artifact: {pc['artifact']}\"",
        "  - id: A3",
        f"    description: \"consumer_state: {pc['consumer_state']}\"",
        "---",
        "",
        "## Steps",
        "",
        "1. TODO(campaign author): replace this placeholder with concrete,",
        "   deterministic steps that prove A1-A3. Browser rungs: author a",
        "   runner spec (scripts/qe/runner) and invoke it here; API rungs:",
        "   curl/hurl with content-bearing assertions; desktop rungs: T0",
        "   crew-governed PTY only today (pass FILE PATHS, never scenario",
        "   bodies — the 1022B PTY line limit silently discards longer",
        "   prompts); T2 computer-use is exploratory and ALWAYS graded by",
        "   the independent reviewer (see refs/scenario-format.md tiers).",
        "2. `exit 1` — the stub fails until authored (never a silent PASS).",
        "",
        "## Evidence expected",
        "",
        f"- terminal_state — {pc['terminal_state']}",
        f"- artifact — {pc['artifact']}",
        f"- consumer_state — {pc['consumer_state']}",
        "",
    ]
    return "\n".join(lines)


def persist_plan(plan: dict, out_dir: Path, write_stubs: bool = True) -> dict:
    """Fail-closed persistence: validate, write stubs, bind, re-validate.

    Writes `<out_dir>/campaign-recon.json` plus scenario-format v1.1 stubs
    under `<out_dir>/scenarios/` for every stub-eligible rung that has no
    `scenario_path` yet. Raises CampaignPlanError (writing nothing) when the
    plan does not conform.
    """
    errors = plan_errors(plan)
    if errors:
        raise CampaignPlanError(
            "plan does not conform to the campaign-recon format:\n"
            + "\n".join(errors)
        )
    out_dir = Path(out_dir)
    scenario_dir = out_dir / SCENARIO_DIRNAME
    written: dict[str, list[str]] = {"plan": [], "scenarios": []}

    stub_texts: dict[str, str] = {}
    for rung in plan["scenarios"]:
        if rung.get("scenario_path"):
            continue
        if rung.get("category") not in CATEGORY_MAP:
            if rung.get("status") == "proposed":
                continue  # not executable yet; nothing to stub
            raise CampaignPlanError(
                f"rung {rung.get('id')!r}: no scenario_path and no "
                "stub-eligible category — bind a hand-authored scenario or "
                "mark the rung 'proposed'"
            )
        if write_stubs:
            text = scenario_stub_markdown(rung, plan)
            fname = _slug(f"{plan.get('name') or 'campaign'}-{rung['id']}")
            rel = f"{SCENARIO_DIRNAME}/{fname}.md"
            stub_texts[rel] = text
            rung["scenario_path"] = rel

    errors = plan_errors(plan)  # re-check after binding mutations
    if errors:
        raise CampaignPlanError(
            "plan invalid after scenario binding:\n" + "\n".join(errors)
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    if stub_texts:
        scenario_dir.mkdir(parents=True, exist_ok=True)
    for rel, text in stub_texts.items():
        (out_dir / rel).write_text(text, encoding="utf-8")
        written["scenarios"].append(str(out_dir / rel))
    plan_path = out_dir / PLAN_FILENAME
    plan_path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    written["plan"].append(str(plan_path))
    return written


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="campaign_plan",
        description="qe campaign plan glue: validate / probe-lens / scaffold",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser(
        "validate",
        help="validate a plan against the campaign-recon format (spec 1 or 2)",
    )
    p_val.add_argument("plan", type=Path)

    p_probe = sub.add_parser(
        "from-endpoint-manifest",
        help="emit probe-lens capability entries from a crew endpoint manifest",
    )
    p_probe.add_argument("manifest", type=Path)
    p_probe.add_argument(
        "--manifest-path",
        default="packages/crew/endpoint-manifest.json",
        help="citation path recorded on the entries",
    )

    p_scaffold = sub.add_parser(
        "scaffold",
        help="persist a validated plan + scenario stubs under --out",
    )
    p_scaffold.add_argument("plan", type=Path)
    p_scaffold.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)

    if args.cmd == "validate":
        errors = plan_errors(json.loads(args.plan.read_text(encoding="utf-8")))
        for err in errors:
            print(err, file=sys.stderr)
        print("OK" if not errors else f"{len(errors)} defect(s)")
        return 0 if not errors else 1

    if args.cmd == "from-endpoint-manifest":
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        caps = capabilities_from_endpoint_manifest(
            manifest, manifest_path=args.manifest_path
        )
        print(json.dumps(caps, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "scaffold":
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        try:
            written = persist_plan(plan, args.out)
        except CampaignPlanError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(written, indent=2))
        return 0

    return 2  # unreachable


if __name__ == "__main__":
    sys.exit(main())
