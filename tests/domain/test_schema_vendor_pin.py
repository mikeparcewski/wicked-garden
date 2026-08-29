"""The vendored schema is pinned and does not drift from the owner's canonical copy.

Enforces the vendor discipline (contract §1): garden pins a byte-compatible copy
of the domain-model governance schema and gates drift. The LIVE OWNER is
wicked-core's governance crate (`crates/wicked-governance/schemas/` — re-homed
there from the retired wicked-brain repo, AW-2 / arch-R10); the frozen brain
archive is history, not the contract, so it is deliberately NOT a compare target.

When the owner is reachable — as a sibling `../wicked-core` checkout, or via the
`WICKED_SCHEMA_OWNER_DIR` env var (CI can point it at a wicked-core checkout to
make the check unconditional) — this asserts byte-identity of the schema AND
equality of the bundle `VERSION`. When it is not reachable (a repo-isolated
checkout), the compare skips gracefully: we never FAIL on the owner's absence,
only on a detected drift.
"""

import json
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
VENDOR = REPO / "skills" / "domain" / "vendor"
SCHEMA = VENDOR / "domain-model.schema.json"
VERSION = VENDOR / "VERSION"

# Candidate locations for the canonical owner copy, in precedence order:
# an explicit CI-provided dir, then the sibling wicked-core checkout.
_OWNER_CANDIDATES = [
    Path(p) for p in [os.environ.get("WICKED_SCHEMA_OWNER_DIR")] if p
] + [
    REPO.parent / "wicked-core" / "crates" / "wicked-governance" / "schemas",
]


def _owner_dir():
    return next((p for p in _OWNER_CANDIDATES if p.is_dir()), None)


def test_schema_version_const_matches_schema_id():
    """Self-consistency of the vendored bytes: the contract version a DOCUMENT
    carries (metadata.schema_version const) matches the $id version segment.
    (The bundle VERSION file is a different, independent version — it tracks the
    owner's whole 4-schema bundle and is checked against the owner below.)"""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    const = schema["properties"]["metadata"]["properties"]["schema_version"]["const"]
    assert schema["$id"].endswith(f"/{const}"), (
        f"schema_version const {const!r} does not match schema $id {schema['$id']!r}"
    )


def test_vendored_copy_is_byte_identical_to_owner_when_present():
    owner = _owner_dir()
    if owner is None:
        pytest.skip(
            "owner wicked-core/crates/wicked-governance/schemas not reachable "
            "(no sibling checkout, WICKED_SCHEMA_OWNER_DIR unset) — drift check skipped"
        )
    canonical = owner / "domain-model.schema.json"
    assert canonical.is_file(), f"owner dir {owner} has no domain-model.schema.json"
    assert SCHEMA.read_bytes() == canonical.read_bytes(), (
        f"vendored schema drifted from canonical {canonical} — re-vendor from the "
        "owner copy at a known commit and sync VERSION to the owner's"
    )


def test_vendored_bundle_version_matches_owner_when_present():
    owner = _owner_dir()
    if owner is None:
        pytest.skip(
            "owner wicked-core/crates/wicked-governance/schemas not reachable "
            "(no sibling checkout, WICKED_SCHEMA_OWNER_DIR unset) — VERSION check skipped"
        )
    ours = VERSION.read_text(encoding="utf-8").strip()
    theirs = (owner / "VERSION").read_text(encoding="utf-8").strip()
    assert ours == theirs, (
        f"vendored bundle VERSION {ours!r} drifted from owner {theirs!r} — "
        "re-vendor and sync (this is exactly the 1.0.0-vs-1.1.0 drift AW-2 fixed)"
    )
