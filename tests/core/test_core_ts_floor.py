"""garden#1600: garden declares the oldest core-ts it pairs with, so the installer can refuse an older crew.

Cores before core-ts 0.9.0 ship built-in workflows that name skills garden 12.69.0 retired
(domain-extractor, domain-coverage; core#871 retired those built-ins in core-ts 0.9.0). On such a core the
first skills publish blocks and every seat launch is refused. `wicked.coreTsFloor` in package.json is read by
wicked-installer before it installs or upgrades garden; raise it in the same PR that retires a skill an older
core still references.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _floor() -> str:
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    return (pkg.get("wicked") or {}).get("coreTsFloor", "")


def test_package_declares_a_core_ts_floor():
    assert SEMVER.match(_floor()), "package.json needs wicked.coreTsFloor as X.Y.Z (garden#1600)"


def test_floor_covers_the_retired_domain_skills():
    # The domain-* skills are gone from this tree, so the floor must be at least core-ts 0.9.0.
    retired = ["domain-extractor", "domain-coverage", "domain-modeler"]
    assert not any((ROOT / "skills" / name).exists() for name in retired)
    major, minor, _ = (int(x) for x in _floor().split("."))
    assert (major, minor) >= (0, 9), "core-ts before 0.9.0 references the retired domain-* skills"
