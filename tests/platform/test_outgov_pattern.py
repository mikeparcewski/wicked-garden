"""Tests for guard_pipeline.check_outgov_pattern (garden#983)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Make guard_pipeline importable.
_SCRIPTS_ROOT = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_ROOT / "platform"))
sys.path.insert(0, str(_SCRIPTS_ROOT))


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
        (rules_dir / "bare.json").write_text(
            json.dumps({"rules": _pat("PAT-001", "Bare")}), encoding="utf-8"
        )
        result = _load_pattern_rules(rules_dir)
        assert len(result) == 1

    def test_empty_dir(self, tmp_path):
        from guard_pipeline import _load_pattern_rules
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        assert _load_pattern_rules(rules_dir) == []


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
        from guard_pipeline import check_outgov_pattern, SEVERITY_WARN, SEVERITY_BLOCK
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
