"""AC-11 CI benchmark lane — enforce 2x p95 SLO on ``_load_gate_result``.

This file is the CI counterpart to :mod:`test_gate_result_perf` (the
in-PR catastrophic-bound guard at 200x). The benchmark is **opt-in** via
the ``benchmark`` marker so local `pytest` runs are unaffected:

    # local developer loop (skips benchmark — current behavior):
    uv run pytest

    # CI benchmark lane (runs only this file):
    uv run pytest -m benchmark --benchmark-json=benchmark.json

Baseline methodology (docs/threat-models/gate-result-ingestion.md §8):
    1. Measurement is p95 of ``validate_gate_result_from_file`` across
       50 deterministic fixtures at sizes 1KB, 4KB, 16KB, 60KB (clamped
       to ``MAX_SUMMARY_BYTES``).
    2. ``_clear_cache_for_tests`` is called before each round so the
       cold-path (full validate + sanitize + cache insert) is measured —
       this is the path AC-11 pins. Cache-hit timing is not the SLO.
    3. Baseline p95 is stored in ``tests/crew/benchmark_baseline.json``.
       It is recomputed on main after any deliberate perf change and
       committed via the re-baselining procedure in the threat model.
    4. The assertion is ``p95_current <= 2.0 * p95_baseline``. A tight
       fail-early lane — 2x is the AC-11 gate, not advisory.

Determinism: fixtures use a fixed seed; file I/O hits ``tmp_path`` so
CI filesystem variance is minimized; pytest-benchmark auto-calibrates
its rounds/iterations to stabilize the reading.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import gate_result_schema  # noqa: E402

_FIXTURE_COUNT = 50
_SIZES = (1024, 4096, 16384, 60000)
_BASELINE_PATH = Path(__file__).parent / "benchmark_baseline.json"
_SLO_MULTIPLIER = 2.0


def _fixture(seed: int, target_bytes: int) -> dict:
    """Deterministic payload sized to approximately ``target_bytes``.

    Mirrors :func:`tests.crew.test_gate_result_perf._fixture` so the
    catastrophic-bound guard and the SLO benchmark share a workload.
    """
    pad = ("deterministic_" * (target_bytes // 14))[:max(0, target_bytes - 200)]
    return {
        "verdict": "APPROVE",
        "reviewer": f"security-engineer-{seed}",
        "recorded_at": "2026-04-19T10:00:00+00:00",
        "reason": "All conditions met.",
        "score": 0.9,
        "min_score": 0.7,
        "summary": pad,
        "conditions": [],
    }


@pytest.fixture(scope="module")
def fixture_files():
    """Write 50 deterministic fixtures into a module-scoped tmpdir."""
    tmp = tempfile.TemporaryDirectory()
    tmp_path = Path(tmp.name)
    files = []
    for i in range(_FIXTURE_COUNT):
        size = _SIZES[i % len(_SIZES)]
        fp = tmp_path / f"gr-{i}.json"
        fp.write_text(json.dumps(_fixture(i, size)))
        files.append(fp)
    yield files
    tmp.cleanup()


def _load_baseline_p95_ns() -> float | None:
    """Return the baseline p95 in nanoseconds, or ``None`` if absent.

    Missing baseline is a soft-skip, not a failure — the first run after
    the file is deleted records a measurement without asserting the SLO.
    """
    if not _BASELINE_PATH.exists():
        return None
    data = json.loads(_BASELINE_PATH.read_text())
    return float(data["p95_ns"])


@pytest.mark.benchmark(group="gate_result_load")
def test_load_gate_result_p95_within_2x_baseline(benchmark, fixture_files):
    """AC-11 SLO: p95 of full-validator load stays within 2x baseline.

    ``benchmark.pedantic`` is used so each round clears the cache and
    walks all 50 fixtures — every sample is a cold-path read. That
    matches AC-11's "validate + sanitize + cache insert" semantic and
    excludes the fast-path (cache-hit) reading, which is not the SLO.
    """
    def _round():
        gate_result_schema._clear_cache_for_tests()
        for fp in fixture_files:
            gate_result_schema.validate_gate_result_from_file(fp)

    benchmark.pedantic(_round, rounds=20, iterations=1, warmup_rounds=2)

    # pytest-benchmark stats are in seconds — convert to ns for parity
    # with the baseline file and the catastrophic-bound guard.
    # Divide by fixture count so the baseline is a per-file p95 reading.
    # `stats["percentiles"]` lives under the Metadata object; we pull
    # the raw samples and compute p95 ourselves (matches test_gate_result_perf).
    samples_s = list(benchmark.stats.stats.data)
    # Each sample is a _round() time covering _FIXTURE_COUNT files.
    per_file_ns = sorted(s * 1e9 / _FIXTURE_COUNT for s in samples_s)
    # Inclusive p95 over the per-round-normalized samples.
    idx = max(0, int(round(0.95 * (len(per_file_ns) - 1))))
    p95_ns = per_file_ns[idx]

    baseline_ns = _load_baseline_p95_ns()
    sys.stderr.write(
        f"[AC-11 benchmark] p95_current={p95_ns:.0f}ns "
        f"baseline={baseline_ns}ns "
        f"slo={_SLO_MULTIPLIER}x\n"
    )

    # Record on the benchmark object so pytest-benchmark JSON captures it.
    benchmark.extra_info["p95_ns"] = p95_ns
    benchmark.extra_info["baseline_ns"] = baseline_ns
    benchmark.extra_info["slo_multiplier"] = _SLO_MULTIPLIER

    if baseline_ns is None:
        pytest.skip(
            "No baseline recorded — run on main and commit "
            "tests/crew/benchmark_baseline.json to activate the SLO gate."
        )

    budget_ns = _SLO_MULTIPLIER * baseline_ns
    assert p95_ns <= budget_ns, (
        f"AC-11 perf regression: p95={p95_ns:.0f}ns exceeds "
        f"{_SLO_MULTIPLIER}x baseline budget={budget_ns:.0f}ns "
        f"(baseline={baseline_ns}ns). "
        "Re-baseline on main (see docs/threat-models/"
        "gate-result-ingestion.md §8) if the regression is intentional."
    )
