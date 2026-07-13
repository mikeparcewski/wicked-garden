"""The vendored schema is pinned and does not drift from brain's canonical copy.

Enforces the vendor discipline (contract §1): garden pins a byte-compatible copy
of @wicked/domain-model-schema and gates drift. When the sibling wicked-brain
repo is present on disk, this asserts byte-identity; when it is absent (a
repo-isolated checkout / CI that doesn't clone the sibling), the byte-compare
skips gracefully — we never FAIL on the sibling's absence, only on a detected
drift.
"""

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
VENDOR = REPO / "skills" / "modernize" / "vendor"
SCHEMA = VENDOR / "domain-model.schema.json"
VERSION = VENDOR / "VERSION"

# Candidate locations for the canonical brain-owned copy (sibling checkout).
_BRAIN_CANDIDATES = [
    REPO.parent / "wicked-brain" / "schemas" / "domain-model.schema.json",
]


def test_version_file_matches_schema_id():
    version = VERSION.read_text(encoding="utf-8").strip()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["$id"].endswith(f"/{version}"), (
        f"VERSION {version!r} does not match schema $id {schema['$id']!r}"
    )


def test_schema_version_const_matches_pin():
    version = VERSION.read_text(encoding="utf-8").strip()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    const = schema["properties"]["metadata"]["properties"]["schema_version"]["const"]
    assert const == version, (
        f"schema_version const {const!r} != pinned VERSION {version!r}"
    )


def test_vendored_copy_is_byte_identical_to_brain_when_present():
    canonical = next((p for p in _BRAIN_CANDIDATES if p.exists()), None)
    if canonical is None:
        pytest.skip("sibling wicked-brain/schemas not present — drift check skipped")
    assert SCHEMA.read_bytes() == canonical.read_bytes(), (
        f"vendored schema drifted from canonical {canonical} — re-vendor from the "
        "brain-owned copy at a known tag and bump VERSION if the bundle changed"
    )
