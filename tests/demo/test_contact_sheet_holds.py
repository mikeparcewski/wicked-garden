"""Freeze-aware review sheets catch mid-chapter holds (garden#1464)."""
from __future__ import annotations

import os
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest


DEMO = Path(__file__).resolve().parents[2] / "scripts" / "demo"
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
pytestmark = pytest.mark.skipif(
    not FFMPEG or not FFPROBE,
    reason="contact-sheet hold regression needs ffmpeg and ffprobe on PATH; no tools are installed by this test",
)


@pytest.fixture
def held_video(tmp_path):
    """12 s: moving testsrc at 0–4, its last frame held to 9, moving again to 12."""
    video = tmp_path / "mid-chapter-hold.mp4"
    graph = (
        "[0:v]split=2[head][tail];"
        "[head]trim=duration=4,setpts=PTS-STARTPTS,"
        "tpad=stop_mode=clone:stop_duration=5[held];"
        "[tail]trim=start=4,setpts=PTS-STARTPTS[moving];"
        "[held][moving]concat=n=2:v=1:a=0,format=yuv420p[out]"
    )
    result = subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
         "testsrc=size=320x180:rate=10:duration=7", "-filter_complex", graph,
         "-map", "[out]", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0", str(video)],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return video


def sheet_times(video, output, *sampling):
    result = subprocess.run(
        [sys.executable, str(DEMO / "contact_sheet.py"), str(video), *sampling,
         "--print-times", "--width", "160", "--out", str(output)],
        capture_output=True, text=True, timeout=60, env={**os.environ, "FFMPEG": FFMPEG},
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[-1] == str(output.resolve()), "the output path must follow the chosen times"
    assert lines[:-1] and all(re.fullmatch(r"\d+\.\d{2}", line) for line in lines[:-1]), result.stdout
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    return [float(line) for line in lines[:-1]]


def test_holds_sample_the_mid_chapter_freeze_that_a_sparse_survey_misses(held_video, tmp_path):
    holds = sheet_times(held_video, tmp_path / "holds.png", "--holds")
    assert any(4 <= t <= 9 for t in holds), holds
    assert any(abs(t - 6.5) <= 0.15 for t in holds), holds

    sparse = sheet_times(held_video, tmp_path / "sparse.png", "--every", "20")
    assert not any(4 <= t <= 9 for t in sparse), sparse

    regular = sheet_times(held_video, tmp_path / "regular.png", "--every", "5")
    assert not any(abs(t - 6.5) <= 0.15 for t in regular), regular


def test_missing_ffmpeg_reports_could_not_run(tmp_path):
    video = tmp_path / "video.mp4"
    video.touch()  # Tool discovery should refuse before trying to read this video.
    result = subprocess.run(
        [sys.executable, str(DEMO / "contact_sheet.py"), str(video), "--every", "20"],
        capture_output=True, text=True, timeout=20,
        env={**os.environ, "FFMPEG": str(tmp_path / "nonexistent-ffmpeg")},
    )
    assert result.returncode != 0
    assert "COULD-NOT-RUN" in result.stderr, result.stderr


@pytest.mark.parametrize("prefix", ["freeze_", "lap_freeze_"])
def test_longest_holds_include_a_freeze_that_runs_to_the_end(monkeypatch, prefix):
    spec = importlib.util.spec_from_file_location("contact_sheet_holds", DEMO / "contact_sheet.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    log = "\n".join([
        f"[freezedetect] {prefix}start: 0",
        f"[freezedetect] {prefix}end: 1",
        f"[freezedetect] {prefix}start: 2",
        f"[freezedetect] {prefix}end: 6",
        f"[freezedetect] {prefix}start: 8",
    ])
    monkeypatch.setattr(
        module.subprocess, "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="", stderr=log),
    )
    assert module.hold_moments("ffmpeg", Path("video.mp4"), 14, 0.5, 2) == [11, 4]
