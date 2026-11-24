"""Crew 2eab5eb's served-form answers pin the Python port, including fixed-seed fuzz inputs."""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "editor"))
VECTORS = json.loads((REPO / "tests/fixtures/editor/crew_guard_vectors.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=lambda v: "crew-" + hashlib.sha256(v["html"].encode()).hexdigest()[:12])
def test_guard_bundle_matches_crew_vector(vector):
    guard = importlib.import_module("_crew_guard")
    got = guard.guard_bundle(vector["html"].encode("utf-8"), guard.MAX_INLINE_SCRIPTS)
    assert got.too_many == vector.get("too_many")
    if "too_many" in vector:
        assert got.body == b"" and got.script_hashes == []
        return
    assert hashlib.sha256(got.body).hexdigest() == vector["body_sha256"]
    if "body" in vector:
        assert got.body.decode("utf-8") == vector["body"]
    assert got.script_hashes == vector["script_hashes"]
    # Fuzz vectors store hashes without repeating the policy. Reconstruct their exact expected header
    # from crew's empty-policy answer and crew's hashes, preserving first-occurrence order.
    sources = " ".join("'sha256-" + h + "'" for h in dict.fromkeys(vector["script_hashes"])) or "'none'"
    expected_csp = VECTORS["headers_without_scripts"]["Content-Security-Policy"].replace(
        "script-src 'none'", "script-src " + sources, 1)
    if "csp" in vector:
        assert expected_csp == vector["csp"]
    assert guard.bundle_headers(got.script_hashes)["Content-Security-Policy"] == expected_csp


def test_crew_prelude_budget_and_full_header_set():
    guard = importlib.import_module("_crew_guard")
    assert guard.WEBRTC_PRELUDE == VECTORS["prelude"]
    assert guard.MAX_INLINE_SCRIPTS == VECTORS["max_inline_scripts"]
    assert guard.bundle_headers() == VECTORS["headers_without_scripts"]


def test_crew_headers_deduplicate_hashes_in_document_order():
    guard = importlib.import_module("_crew_guard")
    csp = guard.bundle_headers(["AAA=", "BBB=", "AAA="])["Content-Security-Policy"]
    assert "script-src 'sha256-AAA=' 'sha256-BBB=';" in csp
    assert csp.count("sha256-AAA=") == 1


def test_crew_bad_utf8_is_replaced_like_buffer_to_string():
    guard = importlib.import_module("_crew_guard")
    body = b"<p>\xff\xc0\xaf\xed\xa0\x80</p><script>\xf0\x9f\x92</script>"
    got = guard.guard_bundle(body)
    expected = "<p>\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd</p><script>" + guard.WEBRTC_PRELUDE + "\ufffd</script>"
    assert got.body == expected.encode("utf-8")


@pytest.mark.parametrize("space", ["\ufeff", "\u00a0", "\u1680", *map(chr, range(0x2000, 0x200b)), "\u2028", "\u2029", "\u202f", "\u205f", "\u3000"])
def test_js_whitespace_ends_operator_name(space):
    guard = importlib.import_module("_crew_guard")
    text = '"a"\nin' + space + 'x'
    assert guard.with_prelude(text) == guard.WEBRTC_PRELUDE + text


@pytest.mark.parametrize("identifier", ["\U0001f600", "in\U0001f600", "instanceof\U0001f600"])
def test_astral_utf16_units_count_as_identifier_parts(identifier):
    guard = importlib.import_module("_crew_guard")
    assert guard.with_prelude('"a"\n' + identifier) == '"a";' + guard.WEBRTC_PRELUDE + '\n' + identifier
