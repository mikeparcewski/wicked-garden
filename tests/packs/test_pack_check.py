"""The shipped pack conformance gate (extension-contract gap 3).

The valid fixture must PASS clean; the deliberately-broken fixture must
FAIL with the specific rule codes its defects were built to trip — and
with messages useful enough to fix from.
"""

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts"))

from pack.check import check_pack  # noqa: E402

FIXTURES = _REPO / "tests" / "fixtures" / "packs"
VALID = FIXTURES / "acme-seo"
BROKEN = FIXTURES / "acme-broken"


def _codes(findings, level=None):
    return {f.code for f in findings if level is None or f.level == level}


def test_valid_pack_passes_clean():
    findings = check_pack(VALID, garden_root=_REPO)
    assert _codes(findings, "error") == set(), [f.render() for f in findings]


def test_broken_pack_fails_with_expected_codes():
    findings = check_pack(BROKEN, garden_root=_REPO)
    errors = _codes(findings, "error")
    assert {"PK013",   # wicked-garden-* namespace squat
            "PK014",   # missing router for declared domain
            "PK016",   # worker without context: fork
            "PK030",   # non-reciprocal NOT-THIS-WHEN
            "PK040",   # unknown archetype in produces contract
            "PK041",   # non-kebab produces id
            "PK050",   # malformed peer floor
            } <= errors
    assert "PK042" in _codes(findings, "warn")  # unknown enhances phase


def test_broken_pack_messages_name_the_fix():
    findings = check_pack(BROKEN, garden_root=_REPO)
    rendered = "\n".join(f.render() for f in findings)
    # messages must be actionable, not just codes
    assert "must declare context: fork" in rendered
    assert "one router per domain" in rendered
    assert "must be reciprocal" in rendered
    assert '">=X.Y.Z"' in rendered


def test_missing_manifest_is_pk001(tmp_path):
    findings = check_pack(tmp_path)
    assert _codes(findings, "error") == {"PK001"}


def test_oversize_router_trips_pk020(tmp_path):
    root = tmp_path / "acme-big"
    (root / "skills" / "acme-big").mkdir(parents=True)
    (root / "wicked-pack.json").write_text(json.dumps({
        "spec": 1, "name": "acme-big", "vendor": "acme", "version": "1.0.0",
        "domains": [{"name": "big"}],
    }), encoding="utf-8")
    body = "---\nname: acme-big\ndescription: router\n---\n" + ("filler\n" * 250)
    (root / "skills" / "acme-big" / "SKILL.md").write_text(body, encoding="utf-8")
    findings = check_pack(root)
    assert "PK020" in _codes(findings, "error")


def test_fork_worker_exempt_from_line_cap(tmp_path):
    root = tmp_path / "acme-work"
    for d in ("acme-work", "acme-work-deep-thinker"):
        (root / "skills" / d).mkdir(parents=True)
    (root / "wicked-pack.json").write_text(json.dumps({
        "spec": 1, "name": "acme-work", "vendor": "acme", "version": "1.0.0",
        "domains": [{"name": "work"}],
    }), encoding="utf-8")
    (root / "skills" / "acme-work" / "SKILL.md").write_text(
        "---\nname: acme-work\ndescription: router\n---\n# r\n", encoding="utf-8")
    (root / "skills" / "acme-work-deep-thinker" / "SKILL.md").write_text(
        "---\nname: acme-work-deep-thinker\ncontext: fork\ndescription: w\n---\n"
        + ("long system prompt line\n" * 400), encoding="utf-8")
    findings = check_pack(root)
    assert "PK020" not in _codes(findings)


def test_unterminated_frontmatter_is_pk011(tmp_path):
    """A SKILL.md whose frontmatter never closes must be malformed (PK011),
    not half-parsed as valid (Copilot review, PR #1057)."""
    root = tmp_path / "acme-open"
    (root / "skills" / "acme-open").mkdir(parents=True)
    (root / "wicked-pack.json").write_text(json.dumps({
        "spec": 1, "name": "acme-open", "vendor": "acme", "version": "1.0.0",
        "domains": [{"name": "open"}],
    }), encoding="utf-8")
    (root / "skills" / "acme-open" / "SKILL.md").write_text(
        "---\nname: acme-open\ndescription: no closing fence\n# body\n",
        encoding="utf-8")
    findings = check_pack(root)
    assert "PK011" in _codes(findings, "error")


def test_absolute_skills_dir_rejected(tmp_path):
    """skills_dir must not escape the pack root — absolute paths (POSIX or
    Windows drive-letter) fail structural validation (Copilot review, PR #1057)."""
    for bad in ("/etc", "C:\\evil", "..\\up"):
        root = tmp_path / f"acme-esc-{abs(hash(bad)) % 1000}"
        root.mkdir()
        (root / "wicked-pack.json").write_text(json.dumps({
            "spec": 1, "name": "acme-esc", "vendor": "acme", "version": "1.0.0",
            "skills_dir": bad, "domains": [{"name": "esc"}],
        }), encoding="utf-8")
        findings = check_pack(root)
        rendered = "\n".join(f.render() for f in findings)
        assert "relative path inside the pack" in rendered, f"{bad!r} was not rejected"


def test_dir_name_mismatch_trips_pk017(tmp_path):
    root = tmp_path / "acme-mix"
    (root / "skills" / "acme-mix").mkdir(parents=True)
    (root / "wicked-pack.json").write_text(json.dumps({
        "spec": 1, "name": "acme-mix", "vendor": "acme", "version": "1.0.0",
        "domains": [{"name": "mix"}],
    }), encoding="utf-8")
    (root / "skills" / "acme-mix" / "SKILL.md").write_text(
        "---\nname: acme-mix-other\ncontext: fork\ndescription: x\n---\n# x\n",
        encoding="utf-8")
    findings = check_pack(root)
    assert "PK017" in _codes(findings, "error")


# ---------------------------------------------------------------------------
# The command pack authors actually run: `npx wicked-garden pack check <dir>`
# (node install.mjs pack check — same file the npm bin points at).
# ---------------------------------------------------------------------------

def _node():
    import shutil
    return shutil.which("node")


def test_cli_pack_check_valid_exits_zero():
    node = _node()
    if node is None:
        import pytest
        pytest.skip("node not available")
    proc = subprocess.run(
        [node, str(_REPO / "install.mjs"), "pack", "check", str(VALID)],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout


def test_cli_pack_check_broken_exits_nonzero_with_useful_errors():
    node = _node()
    if node is None:
        import pytest
        pytest.skip("node not available")
    proc = subprocess.run(
        [node, str(_REPO / "install.mjs"), "pack", "check", str(BROKEN)],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "PK016" in proc.stdout and "context: fork" in proc.stdout
