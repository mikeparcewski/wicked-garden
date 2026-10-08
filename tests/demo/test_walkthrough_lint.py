"""Walkthrough storyline lint (DES-walkthrough-proof §4.5; wicked-garden#1231).

`walkthrough.mjs lint --root <author dir>` is the walkthrough_plan step's pinned validator
(wicked-core WALKTHROUGH_LINT_SCRIPT). It exits 0 only when <author dir>/storyline.mjs passes
every rule, else 1 with a findings JSON naming each failing rule and the path it read.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WALKTHROUGH = ROOT / "scripts" / "demo" / "walkthrough.mjs"
LAUNCHER = ROOT / "scripts" / "wicked-garden"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or shutil.which("jq") is None,
    reason="needs node and jq (the vault's jq_pred verifier)",
)

VALID = """export default {
  title: "Orders",
  baseUrl: "fixture",
  fixture: {
    start: ["node", "app.mjs"],
    ready: "/ready",
    env: { LOG_LEVEL: "info" },
    probes: { run: ["node", "probe.mjs"] },
  },
  segments: [
    { key: "00-intro", title: "Intro", intro: true, async run(ctx) {} },
    {
      key: "01-run",
      title: "Run it",
      proves: ["build"],
      checks: [
        { id: "status", kind: "locator", selector: "#status",
          negative: [{ inner_text: null }] },
        { id: "saved", kind: "probe", name: "run",
          verify: { kind: "jq_pred", params: { expr: ".parsed.exists == true" } },
          negative: [{ parsed: { exists: false } }] },
        { id: "both", kind: "join", sources: ["status", "saved"],
          negative: [{ joined: { status: "Done", saved: null } }] },
        { id: "clean", kind: "guard",
          negative: [{ foreign_writes: ["POST http://elsewhere/"], console_errors: [] }] },
      ],
      async run(ctx) { await ctx.check("status"); },
    },
  ],
};
"""


def _author(tmp_path: Path, text: str = VALID) -> Path:
    d = tmp_path / "author" / "walkthrough_plan"
    d.mkdir(parents=True)
    (d / "storyline.mjs").write_text(text)
    return d


def _lint(*argv: str, env: dict | None = None) -> tuple[int, dict, str]:
    out = subprocess.run(["node", str(WALKTHROUGH), "lint", *argv], capture_output=True,
                         text=True, timeout=60, env=env or os.environ.copy(), cwd=ROOT)
    report = json.loads(out.stdout) if out.stdout.strip() else {}
    return out.returncode, report, out.stderr


def _rules(report: dict) -> set[str]:
    return {f["rule"] for f in report.get("findings", [])}


def test_a_storyline_meeting_every_rule_passes(tmp_path):
    code, report, err = _lint("--root", str(_author(tmp_path)))
    assert code == 0, err
    assert report["ok"] is True and report["findings"] == []
    assert report["chapters"] == 1 and report["checks"] == 4


def test_the_pinned_command_passes_through_the_launcher(tmp_path):
    """The exact shape wicked-core pins: "${WICKED_GARDEN_ROOT}/scripts/wicked-garden" run ... lint --root "${WICKED_EVIDENCE_ROOT}"."""
    author = _author(tmp_path)
    env = {**os.environ, "WICKED_GARDEN_ROOT": str(ROOT), "WICKED_EVIDENCE_ROOT": str(author)}
    out = subprocess.run([str(LAUNCHER), "run", "scripts/demo/walkthrough.mjs", "lint", "--root", str(author)],
                         capture_output=True, text=True, timeout=60, env=env, cwd=tmp_path)
    assert out.returncode == 0, out.stdout + out.stderr
    assert json.loads(out.stdout)["ok"] is True


def test_a_missing_storyline_is_a_finding_naming_the_path_read(tmp_path):
    empty = tmp_path / "author" / "walkthrough_plan"
    empty.mkdir(parents=True)
    code, report, _ = _lint("--root", str(empty))
    assert code == 1
    assert _rules(report) == {"storyline_missing"}
    assert report["storyline"] == str(empty / "storyline.mjs")


def test_root_defaults_to_the_evidence_root_env(tmp_path):
    author = _author(tmp_path)
    code, report, err = _lint(env={**os.environ, "WICKED_EVIDENCE_ROOT": str(author)})
    assert code == 0, err
    assert report["storyline"] == str(author / "storyline.mjs")


def test_no_root_is_a_usage_error(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "WICKED_EVIDENCE_ROOT"}
    code, _, err = _lint(env=env)
    assert code == 2 and "usage" in err


def test_an_unloadable_storyline_is_refused(tmp_path):
    code, report, _ = _lint("--root", str(_author(tmp_path, "export default { oops")))
    assert code == 1 and _rules(report) == {"storyline_unloadable"}


def test_an_empty_plan_is_refused(tmp_path):
    text = 'export default { baseUrl: "fixture", fixture: { start: ["node", "app.mjs"] }, segments: [] };'
    code, report, _ = _lint("--root", str(_author(tmp_path, text)))
    assert code == 1 and "segments" in _rules(report)


def test_a_check_without_a_negative_sample_is_refused(tmp_path):
    text = VALID.replace('negative: [{ inner_text: null }] },', '},')
    code, report, _ = _lint("--root", str(_author(tmp_path, text)))
    assert code == 1 and _rules(report) == {"negative_missing"}


def test_a_tautology_verifier_is_refused(tmp_path):
    text = VALID.replace('".parsed.exists == true"', '"(.parsed | length) >= 0"')
    code, report, _ = _lint("--root", str(_author(tmp_path, text)))
    assert code == 1 and _rules(report) == {"negative_passes"}


def test_a_verifier_jq_rejects_is_refused(tmp_path):
    text = VALID.replace('".parsed.exists == true"', '".parsed.exists ==="')
    code, report, _ = _lint("--root", str(_author(tmp_path, text)))
    assert code == 1 and "check_verify" in _rules(report)


def test_base_url_must_be_fixture(tmp_path):
    text = VALID.replace('baseUrl: "fixture"', 'baseUrl: "http://localhost:3000"')
    code, report, _ = _lint("--root", str(_author(tmp_path, text)))
    assert code == 1 and _rules(report) == {"base_url"}


def test_inline_code_in_fixture_start_is_refused(tmp_path):
    text = VALID.replace('start: ["node", "app.mjs"]', 'start: ["node", "-e", "require(\'http\')"]')
    code, report, _ = _lint("--root", str(_author(tmp_path, text)))
    assert code == 1 and _rules(report) == {"fixture_start"}


def test_a_fixture_start_outside_the_tree_is_refused(tmp_path):
    text = VALID.replace('start: ["node", "app.mjs"]', 'start: ["node", "../elsewhere/app.mjs"]')
    code, report, _ = _lint("--root", str(_author(tmp_path, text)))
    assert code == 1 and _rules(report) == {"fixture_start"}


def test_with_tree_the_start_script_must_exist_in_it(tmp_path):
    tree = tmp_path / "tree"
    tree.mkdir()
    author = _author(tmp_path)
    code, report, _ = _lint("--root", str(author), "--tree", str(tree))
    assert code == 1 and _rules(report) == {"fixture_start"}
    (tree / "app.mjs").write_text("// fixture\n")
    code, report, err = _lint("--root", str(author), "--tree", str(tree))
    assert code == 0, err


def test_a_secret_env_name_is_refused(tmp_path):
    text = VALID.replace('env: { LOG_LEVEL: "info" }', 'env: { LOG_LEVEL: "info", STRIPE_API_KEY: "x" }')
    code, report, _ = _lint("--root", str(_author(tmp_path, text)))
    assert code == 1 and _rules(report) == {"secret_env"}


def test_a_chapter_needs_on_screen_state_and_a_cross_check(tmp_path):
    no_join = VALID.replace(
        """        { id: "both", kind: "join", sources: ["status", "saved"],
          negative: [{ joined: { status: "Done", saved: null } }] },
""", "")
    code, report, _ = _lint("--root", str(_author(tmp_path, no_join)))
    assert code == 1 and _rules(report) == {"chapter_cross_check"}


def test_the_walkthrough_needs_a_must_not_happen_check(tmp_path):
    no_guard = VALID.replace(
        """        { id: "clean", kind: "guard",
          negative: [{ foreign_writes: ["POST http://elsewhere/"], console_errors: [] }] },
""", "")
    code, report, _ = _lint("--root", str(_author(tmp_path, no_guard)))
    assert code == 1 and _rules(report) == {"must_not_happen"}


def test_a_probe_must_be_declared_by_the_fixture(tmp_path):
    text = VALID.replace('name: "run"', 'name: "orders"')
    code, report, _ = _lint("--root", str(_author(tmp_path, text)))
    assert code == 1 and _rules(report) == {"check_probe"}


def test_an_unknown_check_kind_is_refused(tmp_path):
    text = VALID.replace('kind: "guard"', 'kind: "saved_state"')
    code, report, _ = _lint("--root", str(_author(tmp_path, text)))
    assert code == 1 and "check_kind" in _rules(report)


def test_with_steps_every_proves_id_is_a_plan_step(tmp_path):
    author = _author(tmp_path)
    code, _, err = _lint("--root", str(author), "--steps", "build,test")
    assert code == 0, err
    code, report, _ = _lint("--root", str(author), "--steps", "test")
    assert code == 1 and _rules(report) == {"proves"}


def test_a_chapter_without_proves_is_refused(tmp_path):
    text = VALID.replace('proves: ["build"],', '')
    code, report, _ = _lint("--root", str(_author(tmp_path, text)))
    assert code == 1 and _rules(report) == {"proves"}


def test_the_skills_documented_example_passes(tmp_path):
    """skills/demo/refs/walkthrough-author.md's example is what an author copies: it must lint clean."""
    import re
    ref = (ROOT / "skills" / "demo" / "refs" / "walkthrough-author.md").read_text()
    example = re.search(r"```js\n(.*?)```", ref, re.S).group(1)
    code, report, err = _lint("--root", str(_author(tmp_path, example)))
    assert code == 0, err
    assert report["chapters"] == 1 and report["checks"] == 4


@pytest.mark.parametrize("kind", ["toString", "constructor", "__proto__"])
def test_an_inherited_property_name_is_an_unknown_kind_not_a_crash(tmp_path, kind):
    text = VALID.replace('kind: "guard"', f'kind: "{kind}"')
    code, report, _ = _lint("--root", str(_author(tmp_path, text)))
    assert code == 1 and "check_kind" in _rules(report)


def test_a_storyline_that_throws_while_read_is_a_finding(tmp_path):
    text = 'export default { baseUrl: "fixture", get segments() { throw new Error("boom"); } };'
    code, report, _ = _lint("--root", str(_author(tmp_path, text)))
    assert code == 1 and _rules(report) == {"storyline_unreadable"}
    assert report["findings"][0]["detail"] == "boom"


def test_an_unprintable_throw_is_still_a_finding(tmp_path):
    text = ('export default { baseUrl: "fixture", get segments() { throw { get message() { throw 1; }, '
            'toString() { throw 2; } }; } };')
    code, report, _ = _lint("--root", str(_author(tmp_path, text)))
    assert code == 1 and _rules(report) == {"storyline_unreadable"}
