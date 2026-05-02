"""Unit tests for scripts/crew/resolve.py (#717 classify-don't-retry path).

Covers:
    * load_rules — well-formed / malformed / missing
    * classify_finding — each rule type matches; unknown defaults to judgment
    * resolve_phase — preview vs accept; escalation refusal; no verdict mutation
    * gate-result.json untouched after resolve --accept (load-bearing assertion)
    * emit failure does not raise (fail-open)

Stdlib + unittest only.
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

# Add scripts/ to sys.path; conftest applies the same setup under pytest.
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from crew import resolve as rv  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _well_formed_rules() -> list[dict]:
    return [
        {"id": "ac-numbering",
         "matches": [r"AC-\d+ not found"],
         "classification": "mechanical"},
        {"id": "missing-evidence-ref",
         "matches": ["evidence file not found"],
         "classification": "mechanical"},
        {"id": "intent-change",
         "matches": ["intent change"],
         "classification": "judgment"},
        {"id": "security-finding",
         "matches": ["vulnerability"],
         "classification": "escalation"},
    ]


def _seed_manifest(project_dir: Path, phase: str, conditions: list[dict]) -> Path:
    phase_dir = project_dir / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = phase_dir / "conditions-manifest.json"
    manifest_path.write_text(
        json.dumps({"conditions": conditions}, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def _seed_gate_result(project_dir: Path, phase: str) -> Path:
    """Write a gate-result.json so we can assert it's untouched after resolve."""
    phase_dir = project_dir / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    path = phase_dir / "gate-result.json"
    path.write_text(
        json.dumps({"verdict": "CONDITIONAL", "score": 0.65, "min_score": 0.7}),
        encoding="utf-8",
    )
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# load_rules
# ---------------------------------------------------------------------------

class TestLoadRules(unittest.TestCase):
    def test_missing_path_returns_empty_list(self):
        self.assertEqual(rv.load_rules("/no/such/file.json"), [])

    def test_malformed_json_returns_empty_list(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            path.write_text("{ not json", encoding="utf-8")
            self.assertEqual(rv.load_rules(path), [])

    def test_well_formed_rules_parsed(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            path.write_text(json.dumps(
                {"schema_version": "1.0.0", "rules": _well_formed_rules()}
            ), encoding="utf-8")
            rules = rv.load_rules(path)
            self.assertEqual(len(rules), 4)
            self.assertEqual(rules[0]["id"], "ac-numbering")

    def test_malformed_individual_rules_dropped(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            path.write_text(json.dumps({
                "rules": [
                    {"id": "good", "matches": ["x"], "classification": "mechanical"},
                    {"id": "no-classification", "matches": ["y"]},
                    {"id": "bad-classification", "matches": ["z"], "classification": "invented"},
                    {"matches": ["w"], "classification": "mechanical"},  # no id
                    "not-a-dict",
                ]
            }), encoding="utf-8")
            rules = rv.load_rules(path)
            self.assertEqual(len(rules), 1)
            self.assertEqual(rules[0]["id"], "good")

    def test_load_rules_pre_compiles_regex(self):
        """load_rules attaches _compiled re.Pattern objects per rule."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            path.write_text(json.dumps({"rules": _well_formed_rules()}),
                            encoding="utf-8")
            rules = rv.load_rules(path)
            self.assertEqual(len(rules), 4)
            for rule in rules:
                self.assertIn("_compiled", rule)
                self.assertEqual(len(rule["_compiled"]), len(rule["matches"]))
                for pattern in rule["_compiled"]:
                    # Real re.Pattern objects expose .search.
                    self.assertTrue(hasattr(pattern, "search"))

    def test_load_rules_drops_rule_when_all_patterns_malformed(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            path.write_text(json.dumps({"rules": [
                {"id": "all-bad", "matches": ["[unclosed", "(also"],
                 "classification": "mechanical"},
                {"id": "one-good", "matches": ["[unclosed", "AC-3"],
                 "classification": "mechanical"},
            ]}), encoding="utf-8")
            rules = rv.load_rules(path)
            ids = {r["id"] for r in rules}
            self.assertNotIn("all-bad", ids,
                             "rule with no surviving patterns must be dropped")
            self.assertIn("one-good", ids,
                          "rule with at least one good pattern survives")


# ---------------------------------------------------------------------------
# classify_finding
# ---------------------------------------------------------------------------

class TestClassifyFinding(unittest.TestCase):
    def setUp(self):
        self.rules = _well_formed_rules()

    def test_ac_numbering_matches_mechanical(self):
        finding = {"id": "c1", "message": "AC-3 not found in clarify/acceptance-criteria.json"}
        result = rv.classify_finding(finding, self.rules)
        self.assertEqual(result["classification"], "mechanical")
        self.assertEqual(result["applied_rule"], "ac-numbering")

    def test_missing_evidence_matches_mechanical(self):
        finding = {"id": "c2", "description": "evidence file not found: diagram.png"}
        result = rv.classify_finding(finding, self.rules)
        self.assertEqual(result["classification"], "mechanical")
        self.assertEqual(result["applied_rule"], "missing-evidence-ref")

    def test_security_matches_escalation(self):
        finding = {"id": "c3", "message": "SQL injection vulnerability in user_input"}
        result = rv.classify_finding(finding, self.rules)
        self.assertEqual(result["classification"], "escalation")
        self.assertEqual(result["applied_rule"], "security-finding")

    def test_unknown_defaults_to_judgment(self):
        finding = {"id": "c4", "message": "the outcome statement is ambiguous"}
        result = rv.classify_finding(finding, self.rules)
        self.assertEqual(result["classification"], "judgment")
        self.assertEqual(result["applied_rule"], rv.NO_MATCH_RULE_ID)

    def test_case_insensitive_match(self):
        finding = {"message": "AC-3 NOT FOUND"}
        result = rv.classify_finding(finding, self.rules)
        self.assertEqual(result["classification"], "mechanical")

    def test_malformed_regex_in_rule_does_not_raise(self):
        bad_rules = [
            {"id": "bad-regex", "matches": ["[unclosed"], "classification": "mechanical"},
            {"id": "good", "matches": ["AC-3"], "classification": "mechanical"},
        ]
        finding = {"message": "AC-3 not found"}
        result = rv.classify_finding(finding, bad_rules)
        # bad-regex skipped, good still matches
        self.assertEqual(result["applied_rule"], "good")

    def test_non_dict_finding_handled(self):
        result = rv.classify_finding("AC-3 not found", self.rules)
        self.assertEqual(result["classification"], "mechanical")


# ---------------------------------------------------------------------------
# resolve_phase
# ---------------------------------------------------------------------------

class TestResolvePhase(unittest.TestCase):
    def test_missing_manifest_returns_empty(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            result = rv.resolve_phase(project_dir, "design")
            self.assertFalse(result["manifest_loaded"])
            self.assertEqual(result["mechanical"], [])
            self.assertEqual(result["resolved"], [])
            self.assertTrue(result["verdict_unchanged"])

    def test_preview_does_not_modify_disk(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            manifest = _seed_manifest(project_dir, "design", [
                {"id": "c1", "message": "AC-3 not found", "verified": False},
            ])
            gate = _seed_gate_result(project_dir, "design")
            manifest_sha_before = _sha256(manifest)
            gate_sha_before = _sha256(gate)

            result = rv.resolve_phase(project_dir, "design", accept=False)
            self.assertEqual(len(result["mechanical"]), 1)

            # NEITHER file should be touched in preview mode.
            self.assertEqual(_sha256(manifest), manifest_sha_before,
                             "preview MUST NOT modify conditions-manifest.json")
            self.assertEqual(_sha256(gate), gate_sha_before,
                             "preview MUST NOT modify gate-result.json")

    def test_accept_writes_sidecar_but_leaves_gate_result_untouched(self):
        """Load-bearing contract assertion: --accept never mutates gate-result.json."""
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            manifest = _seed_manifest(project_dir, "design", [
                {"id": "c1", "message": "AC-3 not found", "verified": False},
            ])
            gate = _seed_gate_result(project_dir, "design")
            gate_sha_before = _sha256(gate)
            manifest_sha_before = _sha256(manifest)

            # Patch the rules path so we use _well_formed_rules.
            with TemporaryDirectory() as rules_tmp:
                rules_path = Path(rules_tmp) / "rules.json"
                rules_path.write_text(json.dumps(
                    {"rules": _well_formed_rules()}
                ), encoding="utf-8")
                with patch.object(rv, "_DEFAULT_RULES_PATH", rules_path):
                    result = rv.resolve_phase(project_dir, "design", accept=True)

            self.assertEqual(len(result["resolved"]), 1)
            sidecar = Path(result["resolved"][0]["sidecar_path"])
            self.assertTrue(sidecar.is_file(), "sidecar must be written on --accept")

            # Gate result MUST be byte-identical.
            self.assertEqual(_sha256(gate), gate_sha_before,
                             "gate-result.json MUST be untouched by resolve --accept "
                             "— this is the load-bearing #717 contract")
            # Manifest itself MUST also be untouched (sidecar is separate).
            self.assertEqual(_sha256(manifest), manifest_sha_before,
                             "conditions-manifest.json MUST be untouched on --accept "
                             "(only the sidecar is written; verified flag stays as-is "
                             "until crew:approve runs)")

    def test_escalation_refused_with_structured_message(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            _seed_manifest(project_dir, "design", [
                {"id": "c1", "message": "SQL injection vulnerability detected", "verified": False},
            ])
            with TemporaryDirectory() as rules_tmp:
                rules_path = Path(rules_tmp) / "rules.json"
                rules_path.write_text(json.dumps(
                    {"rules": _well_formed_rules()}
                ), encoding="utf-8")
                with patch.object(rv, "_DEFAULT_RULES_PATH", rules_path):
                    result = rv.resolve_phase(project_dir, "design", accept=True)
            self.assertEqual(len(result["escalation"]), 1)
            self.assertEqual(result["resolved"], [],
                             "escalation findings must NEVER be auto-resolved")
            self.assertIn("crew:swarm", result["escalation"][0]["refused_with"])

    def test_mixed_findings_classified_separately(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            _seed_manifest(project_dir, "design", [
                {"id": "mech-1", "message": "AC-3 not found", "verified": False},
                {"id": "esc-1", "message": "SQL injection vulnerability", "verified": False},
                {"id": "judge-1", "message": "ambiguous outcome statement", "verified": False},
                {"id": "verified-1", "message": "AC-9 not found", "verified": True},  # already verified — skip
            ])
            with TemporaryDirectory() as rules_tmp:
                rules_path = Path(rules_tmp) / "rules.json"
                rules_path.write_text(json.dumps(
                    {"rules": _well_formed_rules()}
                ), encoding="utf-8")
                with patch.object(rv, "_DEFAULT_RULES_PATH", rules_path):
                    result = rv.resolve_phase(project_dir, "design", accept=False)
            self.assertEqual(len(result["mechanical"]), 1)
            self.assertEqual(len(result["judgment"]), 1)
            self.assertEqual(len(result["escalation"]), 1)
            # verified=True entry must be skipped entirely.
            mech_ids = {e["condition_id"] for e in result["mechanical"]}
            self.assertNotIn("verified-1", mech_ids)

    def test_cluster_id_restricts_to_single_condition(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            _seed_manifest(project_dir, "design", [
                {"id": "mech-1", "message": "AC-3 not found", "verified": False},
                {"id": "mech-2", "message": "AC-7 not found", "verified": False},
            ])
            with TemporaryDirectory() as rules_tmp:
                rules_path = Path(rules_tmp) / "rules.json"
                rules_path.write_text(json.dumps(
                    {"rules": _well_formed_rules()}
                ), encoding="utf-8")
                with patch.object(rv, "_DEFAULT_RULES_PATH", rules_path):
                    result = rv.resolve_phase(
                        project_dir, "design", accept=False, cluster_id="mech-2",
                    )
            self.assertEqual(len(result["mechanical"]), 1)
            self.assertEqual(result["mechanical"][0]["condition_id"], "mech-2")

    def test_resolution_key_takes_precedence_over_resolution_ref(self):
        """A specialist-proposed `resolution` in the manifest is preferred.

        Matches the conditions_manifest.py convention (mark_cleared /
        recover use ``resolution``). The fallback chain is:
        ``resolution`` → ``resolution_ref`` → synthesized placeholder.
        """
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            _seed_manifest(project_dir, "design", [
                {
                    "id": "c1",
                    "message": "AC-3 not found",
                    "verified": False,
                    "resolution": "patch:fix-ac-3.diff",
                    "resolution_ref": "should-not-be-used",
                },
            ])
            with TemporaryDirectory() as rules_tmp:
                rules_path = Path(rules_tmp) / "rules.json"
                rules_path.write_text(json.dumps(
                    {"rules": _well_formed_rules()}
                ), encoding="utf-8")
                with patch.object(rv, "_DEFAULT_RULES_PATH", rules_path):
                    result = rv.resolve_phase(project_dir, "design", accept=True)
            sidecar_path = Path(result["resolved"][0]["sidecar_path"])
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            self.assertEqual(sidecar["resolution_ref"], "patch:fix-ac-3.diff")

    def test_per_condition_chain_id_includes_condition_id(self):
        """chain_id MUST include condition_id so bus consumers don't dedupe.

        wicked-bus.is_processed keys idempotency by chain_id; a phase-level
        chain would let consumers silently skip every resolution after the
        first in the same phase.
        """
        captured: list[dict] = []

        def fake_emit(event_type, payload, chain_id=None, **kwargs):
            captured.append({
                "event_type": event_type,
                "chain_id": chain_id,
                "payload": payload,
            })

        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            _seed_manifest(project_dir, "design", [
                {"id": "mech-1", "message": "AC-3 not found", "verified": False},
                {"id": "mech-2", "message": "AC-7 not found", "verified": False},
            ])
            with TemporaryDirectory() as rules_tmp:
                rules_path = Path(rules_tmp) / "rules.json"
                rules_path.write_text(json.dumps(
                    {"rules": _well_formed_rules()}
                ), encoding="utf-8")
                # Patch the lazy _bus.emit_event import.
                import _bus  # type: ignore[import]
                with patch.object(rv, "_DEFAULT_RULES_PATH", rules_path), \
                     patch.object(_bus, "emit_event", side_effect=fake_emit):
                    rv.resolve_phase(project_dir, "design", accept=True)

        chains = [c["chain_id"] for c in captured]
        self.assertEqual(len(chains), 2)
        # Each chain MUST be unique and include the condition_id segment.
        self.assertEqual(len(set(chains)), 2,
                         f"chain_ids must be unique per condition; got {chains}")
        for chain in chains:
            self.assertTrue(chain.endswith(".mech-1") or chain.endswith(".mech-2"),
                            f"chain_id must end with condition_id; got {chain}")

    def test_emit_failure_does_not_raise(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            _seed_manifest(project_dir, "design", [
                {"id": "c1", "message": "AC-3 not found", "verified": False},
            ])
            with TemporaryDirectory() as rules_tmp:
                rules_path = Path(rules_tmp) / "rules.json"
                rules_path.write_text(json.dumps(
                    {"rules": _well_formed_rules()}
                ), encoding="utf-8")
                with patch.object(rv, "_DEFAULT_RULES_PATH", rules_path), \
                     patch.object(rv, "_emit_resolved_event",
                                  return_value="failed:RuntimeError"):
                    # Must NOT raise.
                    result = rv.resolve_phase(project_dir, "design", accept=True)
                self.assertEqual(len(result["resolved"]), 1)
                self.assertEqual(result["resolved"][0]["emit_status"],
                                 "failed:RuntimeError")


if __name__ == "__main__":
    unittest.main()
