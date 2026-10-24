"""The build-guide skill text keeps its contract, and setup onboarding invokes it."""

from __future__ import annotations

import importlib.util
import re

from bg_helpers import REPO, SCRIPTS

SKILL_DIR = REPO / "skills" / "build-guide"
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
SETUP = (REPO / "skills" / "core" / "refs" / "setup.md").read_text(encoding="utf-8")

_spec = importlib.util.spec_from_file_location("build_guide_reading_skill", SCRIPTS / "_guide.py")
guide_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guide_mod)


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_skill_name_follows_the_router_convention():
    assert re.search(r"^name: wicked-garden-build-guide$", SKILL, re.MULTILINE)
    assert "role: router" in SKILL


def test_the_probe_unavailable_sentence_is_the_one_the_scripts_print():
    assert guide_mod.UNAVAILABLE in _flat(SKILL)


def test_verified_is_never_hand_written_and_attempts_are_bounded():
    flat = _flat(SKILL)
    assert "Never hand-write `verified`" in flat
    assert "3 probe attempts" in flat
    assert "wicked-core floor probe --repo <dir> --guide <file>" in flat


def test_the_no_guide_path_is_stated_plainly():
    assert "no build/test guide: the floor will run this repo's checks exit-code only" in _flat(SKILL)


def test_every_script_and_ref_the_skill_names_exists():
    for script in set(re.findall(r"scripts/build_guide/([a-z_]+\.py)", SKILL)):
        assert (SCRIPTS / script).is_file(), script
    for ref in set(re.findall(r"`(refs/[a-z-]+\.md)`", SKILL)):
        assert (SKILL_DIR / ref).is_file(), ref
    assert (SKILL_DIR / "assets" / "seeds").is_dir()


def test_discovery_reads_ci_before_manifests():
    flat = _flat(SKILL)
    assert flat.index("CI config first") < flat.index("then the manifests")


def test_proposal_never_writes_silently():
    flat = _flat(SKILL)
    assert "never as a silent write" in flat
    assert "Never** push to the default branch" in flat


def test_full_onboarding_hands_off_to_the_build_guide_skill():
    step = SETUP[SETUP.index("**Step E — Write the build/test guide**"):SETUP.index("#### 5.2 Quick Scout")]
    assert "open the `wicked-garden-build-guide` skill and run its `discover` action" in step
    assert "never writes the file silently" in _flat(step)
    assert "Build guide:     {BUILD_GUIDE" in SETUP
