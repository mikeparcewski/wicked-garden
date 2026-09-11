"""Drift detector for the vendored canonical portability fixture.

``tests/portability_rules.json`` is wicked-crew's ``packages/crew/tests/fixtures/portability_rules.json``
vendored BYTE-FOR-BYTE (F-079 / wicked-crew#531): the two lints agree because they read the same
data, so any local edit is drift. Two checks:

1. the fixture's own integrity claim — ``sha256_of_rules`` re-computed with the algorithm the
   fixture states (canonical JSON of exactly the ``sha256_covers`` members) must match;
2. the vendored bytes are pinned — re-vendoring from a newer crew head is the ONLY way to change
   this file, and it updates ``VENDORED_SHA256`` (and the crew head below) in the same commit.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "portability_rules.json"

# wicked-crew#532 @ 6c8870b9263759ba9bb0c1dae95d24d93d554883 — packages/crew/tests/fixtures/portability_rules.json
VENDORED_FROM = "mikeparcewski/wicked-crew@6c8870b9263759ba9bb0c1dae95d24d93d554883"
VENDORED_SHA256 = "2df674f2380d1842f7a0336ee4d3536c20bc10da160a8b525667b5b5037aba08"  # sha256 of the vendored file bytes


def _fixture_bytes() -> bytes:
    return FIXTURE.read_bytes()


def test_declared_sha256_of_rules_reproduces():
    d = json.loads(_fixture_bytes().decode("utf-8"))
    covered = {k: d[k] for k in d["sha256_covers"]}
    canonical = json.dumps(covered, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == d["sha256_of_rules"], (
        "the vendored fixture's rules no longer match its declared sha256_of_rules — it was edited "
        "locally; re-vendor from wicked-crew instead"
    )
    assert d["version"] == 2
    assert "wicked-garden vendors it VERBATIM" in d["$schema_note"]


def test_vendored_bytes_are_pinned():
    digest = hashlib.sha256(_fixture_bytes()).hexdigest()
    assert digest == VENDORED_SHA256, (
        f"tests/portability_rules.json sha256={digest} differs from the pinned vendored copy "
        f"({VENDORED_FROM}); re-vendor byte-for-byte and update VENDORED_SHA256 in this test"
    )


def test_fixture_has_no_local_only_sections():
    d = json.loads(_fixture_bytes().decode("utf-8"))
    garden_only = {"launcher", "fallbacks", "identifiers", "corpus", "tokens", "codemod"}
    assert not (garden_only & set(d)), (
        "garden-only sections belong in tests/portability_rules.garden.json, never in the vendored canonical file"
    )
