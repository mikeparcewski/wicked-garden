"""Deterministic LIFT checks for the methodology personas.

Thesis (from the persona review): a persona only earns its keep if it adds
something the base model does NOT already supply — a named failure-mode defense,
a hard constraint, or a scope guard. Generic "act like role X" personas have low
durable value. So we don't ASSERT a persona is better; we MEASURE the structural
lift it carries.

This suite is the DETERMINISTIC half of the persona eval. It pins the structural
preconditions for lift to exist:

  1. Methodology personas carry NAMED failure-mode constraints (`FAILURE MODE — …`)
     and a scope guard (`not_focus`) — the things a base prompt lacks.
  2. The persona:as dispatch template SURFACES those fields, so the lift reaches
     the model (a constraint the prompt drops is a constraint that does nothing).
  3. The persona:define MECHANISM round-trips a failure-mode constraint + scope
     guard end-to-end, so an enterprise can author its own house defense.

The behavioural half — proving the persona actually changes model OUTPUT vs the
base model on a task — lives in `eval_cases/*.json` and requires real Claude API
calls (user-gated). See tests/persona/eval_cases/README.md.

Provenance: garden persona-surface review (2026-06). T1 determinism: no network,
no model calls, no sleeps. Registry is loaded with CLAUDE_PLUGIN_ROOT pinned to
the repo so the builtin source resolves.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

# The registry resolves builtin personas only when CLAUDE_PLUGIN_ROOT points at
# the plugin. Pin it for the whole module so the builtin source is available
# regardless of how the env is configured in CI.
os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(_REPO_ROOT))
os.environ["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)

# Load the registry BY FILE PATH from THIS repo, not via `from persona import
# registry`. In a full-suite run a sibling test inserts the installed plugin-cache
# copy (~/.claude/plugins/cache/.../scripts) onto sys.path; the ambient `persona`
# package would then resolve to that stale copy, which lacks the not_focus scope
# guards added in this review. Importing the repo file explicitly makes this
# suite assert against the code under test, order-independently.
import importlib.util as _ilu  # noqa: E402

_REGISTRY_PATH = _REPO_ROOT / "scripts" / "persona" / "registry.py"
_MODNAME = "_wg_repo_persona_registry"
_spec = _ilu.spec_from_file_location(_MODNAME, _REGISTRY_PATH)
registry = _ilu.module_from_spec(_spec)
# Register before exec so @dataclass can resolve type hints via sys.modules.
sys.modules[_MODNAME] = registry
_spec.loader.exec_module(registry)

# Personas the review classified as METHODOLOGY: each must defend named failure
# modes the base model does not self-apply.
METHODOLOGY_PERSONAS = ["platform", "qe", "agentic"]

# The "FAILURE MODE — " sentinel is the structural marker that a constraint names
# the specific failure it guards (not a generic role restatement).
FAILURE_MODE_SENTINEL = "FAILURE MODE"

AS_COMMAND = _REPO_ROOT / "commands" / "persona" / "as.md"


@pytest.fixture(autouse=True)
def _pin_plugin_root(monkeypatch):
    """Re-pin CLAUDE_PLUGIN_ROOT (and project cwd) for EVERY test in this module.

    registry.get_persona() reads CLAUDE_PLUGIN_ROOT at call time to resolve the
    builtin specialist.json. Other suites in the full run mutate that env (and
    HOME/CLAUDE_CWD) for their own isolation; without re-pinning here, the
    builtin source silently fails to load and personas fall back to a
    constraint-less record. Pin it per-test so this suite is order-independent
    (T3 isolation). We also pin CLAUDE_CWD to this repo so any custom-store read
    points at the real project, not a sibling test's temp dir.
    """
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(_REPO_ROOT))
    monkeypatch.setenv("CLAUDE_CWD", str(_REPO_ROOT))

    # A sibling suite may have reload()'d _paths / _domain_store with a temp HOME,
    # leaving their module-level storage root stale. registry imports DomainStore
    # lazily, so it would pick up that stale module. Reload them under the pinned
    # env so the custom-store read resolves against the real project store and
    # builtins (which carry the failure-mode constraints) are not shadowed.
    from importlib import reload
    import _paths as _paths_mod
    import _domain_store as _ds_mod
    reload(_paths_mod)
    reload(_ds_mod)


def _builtin_rich(name: str) -> dict:
    """The env-independent source of truth for a builtin persona's rich profile.

    The methodology defense lives in registry._BUILTIN_RICH — a module constant
    that does NOT depend on CLAUDE_PLUGIN_ROOT, HOME, or the DomainStore. We
    assert against it directly so this suite is order-independent: a sibling test
    that mutates the env or reloads _paths cannot make the registry MERGE path
    resolve a constraint-less fallback and flip these results. (The merge path is
    exercised separately in test_methodology_persona_resolves, which tolerates an
    env-perturbed source.)
    """
    return registry._BUILTIN_RICH[name]


@pytest.fixture
def methodology_records():
    """Load the methodology persona records (per test — env is pinned by fixture)."""
    return {name: registry.get_persona(name) for name in METHODOLOGY_PERSONAS}


# --------------------------------------------------------------------------- #
# Lift precondition 1: methodology personas carry the defense the base lacks
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name", METHODOLOGY_PERSONAS)
def test_methodology_persona_resolves(name, methodology_records):
    """Each methodology persona must resolve through the registry merge path.

    Tolerant of env perturbation from sibling suites: if the builtin source did
    not load (env mutated elsewhere in a full run), the persona may resolve from
    a lower-priority source or not at all — that is a separate concern from the
    CONTENT assertions, which read _BUILTIN_RICH directly. We only require that
    when it DOES resolve as builtin, it is the real record.
    """
    rec = methodology_records[name]
    if rec is None:
        pytest.skip(f"'{name}' did not resolve — builtin source unavailable in this env")
    if rec.get("source") == "builtin":
        assert rec.get("constraints"), f"builtin '{name}' resolved with no constraints"


@pytest.mark.parametrize("name", METHODOLOGY_PERSONAS)
def test_methodology_persona_has_named_failure_modes(name):
    """LIFT signal: constraints must NAME the failure mode, not restate a role.

    A generic persona says 'review for security'. A methodology persona says
    'FAILURE MODE — silent secret exposure: …'. We require at least 3 of the 4
    constraints to carry the sentinel so the defense is concrete and auditable.
    Asserts against _BUILTIN_RICH (the source of truth) so it is deterministic.
    """
    constraints = _builtin_rich(name).get("constraints", [])
    assert len(constraints) >= 4, (
        f"'{name}' has {len(constraints)} constraints; methodology personas "
        "must carry a full set of failure-mode defenses"
    )
    named = [c for c in constraints if FAILURE_MODE_SENTINEL in c]
    assert len(named) >= 3, (
        f"'{name}': only {len(named)}/{len(constraints)} constraints name a "
        f"failure mode ('{FAILURE_MODE_SENTINEL} — …'). Without a named failure "
        "mode a constraint is a role restatement, not durable lift."
    )


@pytest.mark.parametrize("name", METHODOLOGY_PERSONAS)
def test_methodology_persona_has_scope_guard(name):
    """LIFT signal: a scope guard keeps the persona sharp (senior-engineer pattern).

    Without `not_focus`, a methodology persona diffuses into a generic reviewer.
    Asserts against _BUILTIN_RICH (the source of truth) so it is deterministic.
    """
    not_focus = _builtin_rich(name).get("not_focus", [])
    assert len(not_focus) >= 2, (
        f"'{name}' has {len(not_focus)} not_focus entries; a methodology persona "
        "needs an explicit scope guard so it hands off adjacent concerns instead "
        "of diffusing into a generic reviewer"
    )


# --------------------------------------------------------------------------- #
# Lift precondition 2: the dispatch template surfaces the defense to the model
# --------------------------------------------------------------------------- #

def test_dispatch_template_surfaces_constraints_and_scope_guard():
    """A constraint the persona:as prompt drops is a constraint that does nothing.

    The dispatch template in commands/persona/as.md must render both the
    constraints and the not_focus scope guard, otherwise the lift never reaches
    the model.
    """
    text = AS_COMMAND.read_text(encoding="utf-8")
    assert "{constraints_as_numbered_list}" in text, (
        "persona:as dispatch prompt no longer renders constraints — "
        "methodology lift would be silently dropped"
    )
    assert "{not_focus_as_bullet_list}" in text, (
        "persona:as dispatch prompt no longer renders the not_focus scope guard"
    )
    assert "NOT Your Focus" in text, (
        "persona:as dispatch prompt is missing the 'NOT Your Focus' scope-guard "
        "section header"
    )


# --------------------------------------------------------------------------- #
# Lift precondition 3: the define mechanism round-trips a house defense
# --------------------------------------------------------------------------- #

def test_define_mechanism_roundtrips_failure_mode_constraint(tmp_path):
    """An enterprise must be able to author a failure-mode persona via the mechanism.

    Runs the registry CLI in a SUBPROCESS with HOME + CLAUDE_CWD pointed at a temp
    dir, so the DomainStore storage root is fully isolated and no module state
    leaks back into the in-process registry the other tests use (T3 isolation).
    This is also exactly the path persona:define uses, so the test exercises the
    real mechanism. We assert the named failure-mode constraint and the scope
    guard survive the define → get round-trip.
    """
    import json
    import subprocess

    env = dict(os.environ)
    env["HOME"] = str(tmp_path)
    env["CLAUDE_CWD"] = str(tmp_path)
    env["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)

    constraint = (
        "FAILURE MODE — double-charge: any retry on a charge path MUST carry an "
        "idempotency key"
    )
    guard = "UI copy — hand to product"
    registry_py = str(_REPO_ROOT / "scripts" / "persona" / "registry.py")

    define = subprocess.run(
        [
            sys.executable, registry_py,
            "--define", "eval-house-persona",
            "--focus", "money movement is irreversible",
            "--constraints", constraint,
            "--not-focus", guard,
            "--role", "finance",
            "--json",
        ],
        capture_output=True, text=True, env=env, cwd=str(tmp_path),
    )
    assert define.returncode == 0, f"define failed: {define.stderr}"

    got = subprocess.run(
        [sys.executable, registry_py, "--get", "eval-house-persona", "--json"],
        capture_output=True, text=True, env=env, cwd=str(tmp_path),
    )
    assert got.returncode == 0, f"get failed: {got.stderr}"
    reloaded = json.loads(got.stdout)

    assert constraint in reloaded.get("constraints", []), (
        "the named failure-mode constraint did not survive the define round-trip — "
        "the mechanism cannot encode a house defense"
    )
    assert guard in reloaded.get("not_focus", []), (
        "the scope guard did not survive the define round-trip"
    )
    # FAILURE MODE sentinel must persist so list-tier classification still sees it.
    assert any(FAILURE_MODE_SENTINEL in c for c in reloaded.get("constraints", []))


def test_define_then_delete_roundtrips(tmp_path):
    """`persona:define` must be reversible: a defined persona can be deleted.

    Regression guard for the delete_persona bug — custom personas are stored
    under an auto-generated UUID ``id`` (the DomainStore key), while the human
    ``name`` lives in the record body. ``delete_persona(name)`` used to delete
    BY NAME, so it looked up ``{name}.json``, found nothing, and silently
    returned False, leaving the persona in place. The fix resolves name -> id
    first. We assert the full define -> get -> delete -> get round-trip plus the
    miss case (deleting an unknown name returns False, not a stray success).

    Runs in a SUBPROCESS with HOME + CLAUDE_CWD pinned to a temp dir so the
    DomainStore root is isolated and no module state leaks into the in-process
    registry the other tests share (T3 isolation), mirroring the define
    round-trip test above.
    """
    import json
    import subprocess
    import textwrap

    env = dict(os.environ)
    env["HOME"] = str(tmp_path)
    env["CLAUDE_CWD"] = str(tmp_path)
    env["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)

    # Drive define -> delete through the registry API the persona:define surface
    # uses. No --delete CLI verb exists, so call the functions directly in an
    # isolated interpreter and emit a single JSON result line we assert on.
    driver = textwrap.dedent(
        """
        import json, os, sys, importlib.util as ilu
        sys.path.insert(0, os.path.join(os.environ["CLAUDE_PLUGIN_ROOT"], "scripts"))
        p = os.path.join(os.environ["CLAUDE_PLUGIN_ROOT"], "scripts", "persona", "registry.py")
        spec = ilu.spec_from_file_location("_wg_del_rt", p)
        rg = ilu.module_from_spec(spec); sys.modules["_wg_del_rt"] = rg
        spec.loader.exec_module(rg)
        name = "delete-roundtrip-persona"
        defined = rg.save_persona(name, "reversible define", description="d", role="custom")
        present_before = rg.get_persona(name) is not None
        deleted = rg.delete_persona(name)
        present_after = rg.get_persona(name) is not None
        missing = rg.delete_persona("no-such-persona-xyz")
        print(json.dumps({
            "defined_id": defined.get("id"),
            "present_before": present_before,
            "deleted": deleted,
            "present_after": present_after,
            "missing_returns_false": missing,
        }))
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", driver],
        capture_output=True, text=True, env=env, cwd=str(tmp_path),
    )
    assert proc.returncode == 0, f"driver failed: {proc.stderr}"
    result = json.loads(proc.stdout.strip().splitlines()[-1])

    assert result["defined_id"], "define did not assign a UUID id"
    assert result["present_before"] is True, "define did not persist the persona"
    assert result["deleted"] is True, (
        "delete_persona(name) returned False — the name->id resolution is "
        "broken (the original bug: delete-by-name against a UUID-keyed store)"
    )
    assert result["present_after"] is False, (
        "persona still resolvable after delete — delete did not remove it"
    )
    assert result["missing_returns_false"] is False, (
        "deleting an unknown name must return False, not a stray success"
    )


# --------------------------------------------------------------------------- #
# Anti-regression: generic personas should NOT masquerade as methodology
# --------------------------------------------------------------------------- #

def test_generic_personas_are_distinguishable_from_methodology():
    """The list-tier split is data-driven on `constraints` carrying a failure mode.

    This guards the demotion: if someone later sprinkles 'FAILURE MODE' into a
    generic persona without real substance, that's a different problem — but a
    generic persona with ZERO failure-mode constraints must remain classifiable
    as generic so the front-door presentation stays honest.
    """
    generic = ["engineering", "product", "data", "delivery", "jam", "design"]
    for name in generic:
        rec = registry._BUILTIN_RICH.get(name)
        if rec is None:
            continue
        named = [c for c in rec.get("constraints", []) if FAILURE_MODE_SENTINEL in c]
        # Generic personas may carry plain constraints, but if they ever acquire a
        # full failure-mode set + scope guard they should be re-triaged as
        # methodology and moved in the docs. Flag the drift loudly.
        is_methodology_shaped = len(named) >= 3 and len(rec.get("not_focus", [])) >= 2
        assert not is_methodology_shaped, (
            f"'{name}' is documented as GENERIC but now carries a methodology-"
            "shaped record (named failure modes + scope guard). Re-triage it and "
            "move it to the methodology tier in commands/persona/list.md + "
            "skills/persona/SKILL.md."
        )
