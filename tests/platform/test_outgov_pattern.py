"""Tests for guard_pipeline.check_outgov_pattern (garden#983)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# conftest.py puts scripts/ at sys.path[0]; we only need to append scripts/platform
# for guard_pipeline. Using append avoids shadowing the conftest-established order.
sys.path.append(str(Path(__file__).resolve().parents[2] / "scripts" / "platform"))


def _make_bundle(rules: list, path: Path) -> None:
    path.write_text(json.dumps({"rules": rules}), encoding="utf-8")


def _pat(rid: str, statement: str, severity: str = "warn") -> dict:
    return {
        "id": rid,
        "rule_type": "Pattern",
        "statement": statement,
        "severity": severity,
        "confidence": 0.9,
        "provenance": {"source": "test", "ref": "test", "source_kinds": ["manual"]},
    }


def _pol(rid: str, statement: str, severity: str = "warn") -> dict:
    return {
        "id": rid,
        "rule_type": "Policy",
        "statement": statement,
        "severity": severity,
        "confidence": 0.9,
        "provenance": {"source": "test", "ref": "test", "source_kinds": ["manual"]},
    }


# ---------------------------------------------------------------------------
# _load_pattern_rules
# ---------------------------------------------------------------------------

class TestLoadPatternRules:
    def test_reads_pattern_rules_from_bundle(self, tmp_path):
        from guard_pipeline import _load_pattern_rules
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        _make_bundle([_pat("PAT-001", "Use dependency injection"), _pol("POL-001", "No secrets")], rules_dir / "a.json")
        result = _load_pattern_rules(rules_dir)
        assert len(result) == 1
        assert result[0]["id"] == "PAT-001"

    def test_deduplicates_by_id(self, tmp_path):
        from guard_pipeline import _load_pattern_rules
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        _make_bundle([_pat("PAT-001", "First"), _pat("PAT-001", "Duplicate")], rules_dir / "a.json")
        result = _load_pattern_rules(rules_dir)
        assert len(result) == 1

    def test_skips_malformed_json(self, tmp_path):
        from guard_pipeline import _load_pattern_rules
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "bad.json").write_text("not-json", encoding="utf-8")
        _make_bundle([_pat("PAT-001", "Good rule")], rules_dir / "good.json")
        result = _load_pattern_rules(rules_dir)
        assert len(result) == 1

    def test_bare_single_rule_object(self, tmp_path):
        from guard_pipeline import _load_pattern_rules
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        # Rule dict at root with no "rules" key — should be treated as a single rule.
        (rules_dir / "bare.json").write_text(
            json.dumps(_pat("PAT-001", "Bare")), encoding="utf-8"
        )
        result = _load_pattern_rules(rules_dir)
        assert len(result) == 1

    def test_top_level_list(self, tmp_path):
        from guard_pipeline import _load_pattern_rules
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "list.json").write_text(
            json.dumps([_pat("PAT-001", "First"), _pat("PAT-002", "Second")]),
            encoding="utf-8",
        )
        result = _load_pattern_rules(rules_dir)
        assert len(result) == 2

    def test_empty_dir(self, tmp_path):
        from guard_pipeline import _load_pattern_rules
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        assert _load_pattern_rules(rules_dir) == []

    def test_respects_expired_deadline(self, tmp_path):
        """An already-expired deadline stops loading before reading any file."""
        import time
        from guard_pipeline import _load_pattern_rules
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        _make_bundle([_pat("PAT-001", "Would be loaded")], rules_dir / "a.json")
        _make_bundle([_pat("PAT-002", "Should be skipped")], rules_dir / "b.json")
        # deadline already in the past — the per-file check fires immediately before
        # any bundle is read, so the result is empty regardless of how many files exist.
        expired = time.monotonic() - 1.0
        result = _load_pattern_rules(rules_dir, deadline=expired)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# check_outgov_pattern
# ---------------------------------------------------------------------------

class TestCheckOutgovPattern:
    def test_skip_when_wg_outgov_off(self, tmp_path, monkeypatch):
        from guard_pipeline import check_outgov_pattern
        monkeypatch.setenv("WG_OUTGOV", "off")
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.status == "skip"
        assert "WG_OUTGOV=off" in (result.note or "")

    def test_skip_when_rules_dir_env_not_set(self, tmp_path, monkeypatch):
        from guard_pipeline import check_outgov_pattern
        monkeypatch.setenv("WG_OUTGOV", "warn")
        monkeypatch.delenv("WICKED_OUTGOV_RULES_DIR", raising=False)
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.status == "skip"

    def test_skip_when_rules_subdir_missing(self, tmp_path, monkeypatch):
        from guard_pipeline import check_outgov_pattern
        monkeypatch.setenv("WG_OUTGOV", "warn")
        monkeypatch.setenv("WICKED_OUTGOV_RULES_DIR", str(tmp_path))
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.status == "skip"
        assert "rules dir not found" in (result.note or "")

    def test_emits_findings_for_pattern_rules(self, tmp_path, monkeypatch):
        from guard_pipeline import check_outgov_pattern, SEVERITY_BLOCK
        monkeypatch.setenv("WG_OUTGOV", "warn")
        monkeypatch.setenv("WICKED_OUTGOV_RULES_DIR", str(tmp_path))
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        _make_bundle([
            _pat("PAT-001", "Use DI", "warn"),
            _pat("PAT-002", "No globals", "critical"),
            _pol("POL-001", "Skipped policy"),
        ], rules_dir / "a.json")
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.status == "ok"
        assert len(result.findings) == 2
        ids = {f.rule_id for f in result.findings}
        assert "PAT-001" in ids
        assert "PAT-002" in ids
        critical_f = next(f for f in result.findings if f.rule_id == "PAT-002")
        assert critical_f.severity == SEVERITY_BLOCK

    def test_ok_when_no_pattern_rules(self, tmp_path, monkeypatch):
        from guard_pipeline import check_outgov_pattern
        monkeypatch.setenv("WG_OUTGOV", "warn")
        monkeypatch.setenv("WICKED_OUTGOV_RULES_DIR", str(tmp_path))
        (tmp_path / "rules").mkdir()
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.status == "ok"
        assert not result.findings

    def test_budget_exhausted_does_not_crash(self, tmp_path, monkeypatch):
        """check_outgov_pattern is fail-open even with an exhausted budget."""
        from guard_pipeline import check_outgov_pattern
        monkeypatch.setenv("WG_OUTGOV", "warn")
        monkeypatch.setenv("WICKED_OUTGOV_RULES_DIR", str(tmp_path))
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        _make_bundle([_pat("PAT-001", "Use DI"), _pat("PAT-002", "No globals")], rules_dir / "a.json")
        # budget_seconds=0 forces the deadline to fire; result must be ok (fail-open).
        result = check_outgov_pattern([], budget_seconds=0.0)
        assert result.status == "ok"
        # Either "budget exhausted; N of M rules surfaced" (deadline fired during emission)
        # or "no pattern rules found" (deadline fired during load) — both are correct.
        # Either way the note must NOT claim "partial rule set surfaced" without a count.
        note = result.note or ""
        assert not note.startswith("budget exhausted; partial"), (
            "note must include surfaced/total counts, not just 'partial'"
        )
        assert result.duration_ms >= 0


# ---------------------------------------------------------------------------
# AW-16: content-hash provenance — the rules dir is a graph-derived view
# ---------------------------------------------------------------------------

class TestContentHashProvenance:
    def _dir_with_rules(self, tmp_path, monkeypatch, rules=None):
        monkeypatch.setenv("WG_OUTGOV", "warn")
        monkeypatch.setenv("WICKED_OUTGOV_RULES_DIR", str(tmp_path))
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        _make_bundle(rules or [_pat("PAT-001", "Use DI")], rules_dir / "a.json")
        return rules_dir

    def test_hash_is_deterministic_and_order_independent(self, tmp_path):
        from guard_pipeline import compute_rules_content_hash
        d1 = tmp_path / "one" / "rules"
        d2 = tmp_path / "two" / "rules"
        d1.mkdir(parents=True)
        d2.mkdir(parents=True)
        # Same files, written in opposite order → same hash (sorted by name).
        _make_bundle([_pat("PAT-001", "A")], d1 / "a.json")
        _make_bundle([_pat("PAT-002", "B")], d1 / "b.json")
        _make_bundle([_pat("PAT-002", "B")], d2 / "b.json")
        _make_bundle([_pat("PAT-001", "A")], d2 / "a.json")
        h1 = compute_rules_content_hash(d1)
        h2 = compute_rules_content_hash(d2)
        assert h1 == h2
        assert h1.startswith("sha256:")

    def test_hash_changes_when_content_changes(self, tmp_path):
        from guard_pipeline import compute_rules_content_hash
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        _make_bundle([_pat("PAT-001", "A")], rules_dir / "a.json")
        before = compute_rules_content_hash(rules_dir)
        _make_bundle([_pat("PAT-001", "A but edited")], rules_dir / "a.json")
        assert compute_rules_content_hash(rules_dir) != before

    def test_hash_changes_when_filename_changes(self, tmp_path):
        from guard_pipeline import compute_rules_content_hash
        d1 = tmp_path / "one" / "rules"
        d2 = tmp_path / "two" / "rules"
        d1.mkdir(parents=True)
        d2.mkdir(parents=True)
        _make_bundle([_pat("PAT-001", "A")], d1 / "a.json")
        _make_bundle([_pat("PAT-001", "A")], d2 / "renamed.json")
        assert compute_rules_content_hash(d1) != compute_rules_content_hash(d2)

    def test_hash_always_recorded_in_meta(self, tmp_path, monkeypatch):
        from guard_pipeline import check_outgov_pattern
        self._dir_with_rules(tmp_path, monkeypatch)
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.meta is not None
        assert str(result.meta.get("rules_content_hash", "")).startswith("sha256:")

    def test_missing_provenance_is_recorded_not_penalized(self, tmp_path, monkeypatch):
        """A dir without provenance.json still serves rules — fail-open."""
        from guard_pipeline import check_outgov_pattern
        self._dir_with_rules(tmp_path, monkeypatch)
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.status == "ok"
        assert result.meta["provenance"] == "missing"
        assert len(result.findings) == 1  # only the rule itself, no penalty finding
        assert result.findings[0].rule_id == "PAT-001"

    def test_verified_provenance(self, tmp_path, monkeypatch):
        from guard_pipeline import check_outgov_pattern, write_rules_provenance
        self._dir_with_rules(tmp_path, monkeypatch)
        write_rules_provenance(tmp_path, source="estate-graph:test")
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.meta["provenance"] == "verified"
        assert result.meta["provenance_source"] == "estate-graph:test"
        assert not [f for f in result.findings if f.rule_id == "outgov-provenance-stale"]

    def test_stale_provenance_warns_and_still_serves_rules(self, tmp_path, monkeypatch):
        """Hand-editing the graph-derived dir is detected — but stays advisory."""
        from guard_pipeline import (
            check_outgov_pattern, write_rules_provenance, SEVERITY_WARN, SEVERITY_BLOCK,
        )
        rules_dir = self._dir_with_rules(tmp_path, monkeypatch)
        write_rules_provenance(tmp_path, source="estate-graph:test")
        # Simulate a hand edit AFTER generation.
        _make_bundle([_pat("PAT-001", "Use DI"), _pat("PAT-999", "sneaky insert")],
                     rules_dir / "a.json")
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.status == "ok"
        assert result.meta["provenance"] == "stale"
        assert str(result.meta.get("recorded_content_hash", "")).startswith("sha256:")
        stale = [f for f in result.findings if f.rule_id == "outgov-provenance-stale"]
        assert len(stale) == 1
        assert stale[0].severity == SEVERITY_WARN  # advisory — NOT a block
        assert stale[0].severity != SEVERITY_BLOCK
        # Rules are still surfaced (fail-open): both PAT rules present.
        ids = {f.rule_id for f in result.findings}
        assert {"PAT-001", "PAT-999"} <= ids

    def test_malformed_provenance_is_unverifiable(self, tmp_path, monkeypatch):
        from guard_pipeline import check_outgov_pattern
        self._dir_with_rules(tmp_path, monkeypatch)
        (tmp_path / "provenance.json").write_text('{"content_hash": 42}', encoding="utf-8")
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.status == "ok"
        assert result.meta["provenance"] == "unverifiable"
        assert len(result.findings) == 1  # rule surfaced, no stale finding

    def test_unparseable_provenance_treated_as_missing(self, tmp_path, monkeypatch):
        from guard_pipeline import check_outgov_pattern
        self._dir_with_rules(tmp_path, monkeypatch)
        (tmp_path / "provenance.json").write_text("not-json", encoding="utf-8")
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.status == "ok"
        assert result.meta["provenance"] == "missing"

    def test_meta_flows_through_to_dict(self, tmp_path, monkeypatch):
        """The recorded hash reaches the persisted report (briefing/bus payload)."""
        from guard_pipeline import check_outgov_pattern
        self._dir_with_rules(tmp_path, monkeypatch)
        d = check_outgov_pattern([], budget_seconds=5.0).to_dict()
        assert d["meta"]["rules_content_hash"].startswith("sha256:")

    def test_stamp_helper_matches_consumer_recipe(self, tmp_path):
        from guard_pipeline import compute_rules_content_hash, write_rules_provenance
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        _make_bundle([_pat("PAT-001", "A")], rules_dir / "a.json")
        doc = write_rules_provenance(tmp_path, source="s")
        assert doc["content_hash"] == compute_rules_content_hash(rules_dir)
        on_disk = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
        assert on_disk == doc


# ---------------------------------------------------------------------------
# AW-16: WG_OUTGOV defaults to warn (default-on advisory) + fail-open AC
# ---------------------------------------------------------------------------

class TestDefaultWarn:
    def test_default_is_warn_rules_surfaced_without_env(self, tmp_path, monkeypatch):
        """WG_OUTGOV unset → warn: the advisory runs (default-on, AW-16)."""
        from guard_pipeline import check_outgov_pattern
        monkeypatch.delenv("WG_OUTGOV", raising=False)
        monkeypatch.setenv("WICKED_OUTGOV_RULES_DIR", str(tmp_path))
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        _make_bundle([_pat("PAT-001", "Use DI")], rules_dir / "a.json")
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.status == "ok"
        assert len(result.findings) == 1

    def test_explicit_off_still_opts_out(self, tmp_path, monkeypatch):
        """Per-repo opt-out (P-5): WG_OUTGOV=off wins over the warn default."""
        from guard_pipeline import check_outgov_pattern
        monkeypatch.setenv("WG_OUTGOV", "off")
        monkeypatch.setenv("WICKED_OUTGOV_RULES_DIR", str(tmp_path))
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.status == "skip"
        assert not result.findings

    def test_unrecognized_mode_treated_as_off(self, tmp_path, monkeypatch):
        from guard_pipeline import check_outgov_pattern
        monkeypatch.setenv("WG_OUTGOV", "banana")
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.status == "skip"
        assert "banana" in (result.note or "")

    def test_fail_open_missing_rules_dir_no_block(self, tmp_path, monkeypatch):
        """AC: missing rules dir = no block — a skip note only, zero findings."""
        from guard_pipeline import check_outgov_pattern, SEVERITY_BLOCK
        monkeypatch.delenv("WG_OUTGOV", raising=False)  # default-on warn
        monkeypatch.setenv("WICKED_OUTGOV_RULES_DIR", str(tmp_path / "nowhere"))
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.status == "skip"
        assert result.findings == []  # zero findings ⇒ zero SEVERITY_BLOCK findings
        assert "rules dir not found" in (result.note or "")
        assert not [f for f in result.findings if f.severity == SEVERITY_BLOCK]

    def test_fail_open_env_unset_entirely(self, tmp_path, monkeypatch):
        """AC: no estate, no rules dir, default-on — still nothing blocks."""
        from guard_pipeline import check_outgov_pattern
        monkeypatch.delenv("WG_OUTGOV", raising=False)
        monkeypatch.delenv("WICKED_OUTGOV_RULES_DIR", raising=False)
        result = check_outgov_pattern([], budget_seconds=5.0)
        assert result.status == "skip"
        assert result.findings == []

    def test_default_on_pipeline_never_blocks_without_rules(self, tmp_path, monkeypatch):
        """Whole-pipeline fail-open: default-on outgov with no rules dir adds
        zero block-severity findings to a standard run (hermetic: empty repo)."""
        from guard_pipeline import run_pipeline, SEVERITY_BLOCK
        monkeypatch.delenv("WG_OUTGOV", raising=False)
        monkeypatch.delenv("WICKED_OUTGOV_RULES_DIR", raising=False)
        report = run_pipeline(profile_name="standard", cwd=tmp_path, files=[])
        outgov = next(c for c in report.checks if c.name == "outgov_pattern")
        assert outgov.status == "skip"
        assert outgov.findings == []
        assert report.findings_by_severity.get(SEVERITY_BLOCK, 0) == 0
