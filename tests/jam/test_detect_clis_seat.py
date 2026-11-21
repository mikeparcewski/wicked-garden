"""wicked-garden#1513: governed seats must not discover or launch other CLIs."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil

import pytest


REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "jam_detect_clis_seat", REPO / "scripts" / "jam" / "detect_clis.py"
)
detect_clis = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(detect_clis)


@pytest.fixture
def fake_codex(monkeypatch, tmp_path):
    if os.name == "nt":
        pytest.skip("the fake executable uses POSIX executable permissions")
    executable = tmp_path / "codex"
    executable.write_text("", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.delenv("WICKED_RUN_ID", raising=False)
    monkeypatch.delenv("WICKED_RUN_AGENT", raising=False)
    return executable


def forbid_subprocess(*args, **kwargs):
    pytest.fail("a governed seat must not launch another CLI")


@pytest.mark.parametrize("probe", [False, True])
def test_seat_neither_discovers_nor_probes_other_clis(monkeypatch, fake_codex, probe):
    monkeypatch.setenv("WICKED_RUN_ID", "run-1513")
    monkeypatch.setenv("WICKED_RUN_AGENT", "pi")
    monkeypatch.setattr(detect_clis.subprocess, "run", forbid_subprocess)
    monkeypatch.setattr(shutil, "which", lambda *args, **kwargs: pytest.fail("seat scanned PATH"))

    result = detect_clis.run_detect(probe)

    assert {key: result[key] for key in ("detected", "usable", "unusable", "collisions")} == {
        "detected": [], "usable": [], "unusable": [], "collisions": []
    }
    assert result["seat"] == {
        "cli": "pi", "run": "run-1513", "one_cli": True,
        "reason": "This is the run's pi seat in a wicked-crew job. Each seat runs one CLI, "
        "and the job's other CLIs are their own seats: they cannot be called from here "
        "(a CLI started from inside a governed seat would run outside the job's rules). "
        "A jam here is one model's view; say so in the summary.",
    }


@pytest.mark.parametrize("run,agent", [(None, None), ("run-1513", None), (None, "pi"), ("", "pi"), ("run-1513", "")])
def test_incomplete_seat_context_keeps_normal_detection(monkeypatch, fake_codex, run, agent):
    for key, value in (("WICKED_RUN_ID", run), ("WICKED_RUN_AGENT", agent)):
        if value is not None:
            monkeypatch.setenv(key, value)
    monkeypatch.setattr(detect_clis.subprocess, "run", forbid_subprocess)

    result = detect_clis.run_detect(False)
    expected = detect_clis.registry_detect(probe=False)

    assert result == {**expected, "seat": None}
    assert [entry["key"] for entry in result["detected"]] == ["codex"]
    assert result["detected"][0]["resolved_path"] == str(fake_codex)


def test_main_emits_seat_json(monkeypatch, fake_codex, capsys):
    monkeypatch.setenv("WICKED_RUN_ID", "run-1513")
    monkeypatch.setenv("WICKED_RUN_AGENT", "codex")
    monkeypatch.setattr(detect_clis.subprocess, "run", forbid_subprocess)

    assert detect_clis.main(["--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["detected"] == []
    assert result["seat"]["cli"] == "codex"
    assert result["seat"]["one_cli"] is True


@pytest.mark.parametrize("args", [[], ["--probe"]])
def test_human_output_discloses_seat_reason(monkeypatch, fake_codex, capsys, args):
    monkeypatch.setenv("WICKED_RUN_ID", "run-1513")
    monkeypatch.setenv("WICKED_RUN_AGENT", "claude")
    monkeypatch.setattr(detect_clis.subprocess, "run", forbid_subprocess)

    assert detect_clis.main(args) == 0
    output = capsys.readouterr().out
    assert output == detect_clis.seat_context()["reason"] + "\n"
