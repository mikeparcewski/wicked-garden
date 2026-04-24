"""tests/daemon/test_latency_benchmark.py — Warm-path p99 latency benchmark.

Council condition — #611: replace the 10-sample smoke file with a proper
pytest-benchmark run using on-disk SQLite, seeded data, and 100+ iterations.

Requirements:
  - On-disk SQLite (tmpdir, not :memory:) per council requirement.
  - Seed >= 50 task rows + >= 20 project rows before measurement.
  - Measure warm-path p99 for GET /tasks/<id> and GET /tasks?session=X.
  - Assert p99 < 50ms for both endpoints.
  - @pytest.mark.benchmark so the suite runs only in the benchmark CI lane.

T1: deterministic — fixed seed data; no random.
T2: no sleep-based sync.
T3: isolated — each benchmark gets its own tmpdir db + ephemeral server thread.
T4: one concern per test function.
T5: descriptive names.
T6: provenance: #596 v8-PR-2, council condition #611.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# sys.path — daemon package must be importable from the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Named constants (R3: no magic values)
# ---------------------------------------------------------------------------

_SEED_TASK_COUNT: int = 50      # council requirement: >= 50 task rows
_SEED_PROJECT_COUNT: int = 20   # council requirement: >= 20 project rows
_BENCH_SESSION_ID: str = "bench-session-001"
_BENCH_TASK_ID: str = "bench-task-001"

# The p99 SLO — must be < 50ms on warm path.
_P99_LIMIT_SECONDS: float = 0.050

# Minimum iterations pytest-benchmark must run per round.
# pytest-benchmark auto-scales rounds; min_rounds ensures statistical validity.
_MIN_ROUNDS: int = 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _free_port() -> int:
    """Allocate an ephemeral localhost TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _seed_db(db_path: str) -> None:
    """Seed the on-disk DB with projects and tasks before benchmarking."""
    import daemon.db as db
    from daemon.projector import project_event

    conn = db.connect(db_path)
    db.init_schema(conn)

    ts_base = 1_700_000_000

    # Seed projects (>= 20)
    for i in range(_SEED_PROJECT_COUNT):
        project_event(conn, {
            "event_id": i + 1,
            "event_type": "wicked.project.created",
            "created_at": ts_base + i,
            "payload": {
                "project_id": f"bench-project-{i:03d}",
                "name": f"Benchmark Project {i:03d}",
                "workspace": "/bench",
                "archetype": "code-repo",
            },
        })

    # Seed tasks (>= 50): all in _BENCH_SESSION_ID so the session filter hits them
    for i in range(_SEED_TASK_COUNT):
        task_id = f"bench-task-{i:03d}"
        project_event(conn, {
            "event_id": _SEED_PROJECT_COUNT + i + 1,
            "event_type": "wicked.task.created",
            "created_at": ts_base + _SEED_PROJECT_COUNT + i,
            "payload": {
                "task_id": task_id,
                "session_id": _BENCH_SESSION_ID,
                "subject": f"Benchmark task {i:03d}",
                "status": "in_progress",
                "chain_id": "bench-project-000.build",
            },
        })

    conn.close()


def _start_daemon(db_path: str, port: int) -> threading.Thread:
    """Start the daemon HTTP server in a daemon thread; return after it is ready."""
    import daemon.server as server

    srv = server.make_server(host="127.0.0.1", port=port, db_path=db_path)

    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    # Wait up to 2s for the server to accept connections.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.01)
    else:
        raise RuntimeError(f"Daemon did not start on port {port} within 2s")

    return t


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def bench_db(tmp_path_factory):
    """Create and seed an on-disk SQLite DB; shared across all benchmark tests.

    Module-scoped so seeding happens once and the warm-path measurements are
    not contaminated by schema-init overhead.
    """
    db_dir = tmp_path_factory.mktemp("bench_db")
    db_path = str(db_dir / "bench.db")
    _seed_db(db_path)
    return db_path


@pytest.fixture(scope="module")
def bench_server(bench_db):
    """Start the daemon server with the seeded DB; return its base URL."""
    port = _free_port()
    _start_daemon(bench_db, port)
    base_url = f"http://127.0.0.1:{port}"

    # Warm-up: one call to prime the connection pool + SQLite page cache.
    # This call is NOT measured — it absorbs the cold-start spike.
    for _ in range(3):
        try:
            urllib.request.urlopen(f"{base_url}/health", timeout=1.0)
            break
        except Exception:
            time.sleep(0.05)

    return base_url


# ---------------------------------------------------------------------------
# Benchmark callables
# ---------------------------------------------------------------------------

def _get_task_by_id(base_url: str) -> None:
    """Single timed call to GET /tasks/<id>.  Returns on 200 only."""
    url = f"{base_url}/tasks/{_BENCH_TASK_ID}"
    with urllib.request.urlopen(url, timeout=0.5) as resp:
        body = resp.read()
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    data = json.loads(body)
    assert data.get("id") == _BENCH_TASK_ID


def _get_tasks_by_session(base_url: str) -> None:
    """Single timed call to GET /tasks?session=X returning 50 rows."""
    url = f"{base_url}/tasks?session={_BENCH_SESSION_ID}&limit={_SEED_TASK_COUNT}"
    with urllib.request.urlopen(url, timeout=0.5) as resp:
        body = resp.read()
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    rows = json.loads(body)
    assert len(rows) == _SEED_TASK_COUNT, (
        f"Expected {_SEED_TASK_COUNT} rows; got {len(rows)}"
    )


# ---------------------------------------------------------------------------
# Benchmark tests
# ---------------------------------------------------------------------------

def _p99_from_benchmark(benchmark_fixture) -> float:
    """Compute p99 from the raw timing data collected by pytest-benchmark.

    pytest-benchmark does not expose a native p99 attribute; we compute it
    from the sorted ``data`` list (seconds per round) that the Stats object
    populates.  Fallback to max when fewer than 100 samples exist.

    benchmark_fixture.stats is a Metadata object; the actual Stats object
    (which holds the data list) lives at benchmark_fixture.stats.stats.
    """
    # Metadata.stats holds the Stats instance with the raw timing list.
    stats_obj = benchmark_fixture.stats.stats
    data: list = stats_obj.data if hasattr(stats_obj, "data") else []
    if not data:
        # Last resort fallback: use the max from the Metadata dict.
        return benchmark_fixture.stats["max"]
    sorted_data = sorted(data)
    if len(sorted_data) < 100:
        # Too few samples for a meaningful p99 — use max as conservative bound.
        return sorted_data[-1]
    # 99th-percentile: index = floor(0.99 * n), clamped to last element.
    idx = min(int(0.99 * len(sorted_data)), len(sorted_data) - 1)
    return sorted_data[idx]


@pytest.mark.benchmark(group="daemon-latency", min_rounds=_MIN_ROUNDS)
def test_benchmark_get_task_by_id(benchmark, bench_server):
    """Warm-path p99 for GET /tasks/<id> must be < 50ms.

    pytest-benchmark collects timing statistics across >= 100 rounds.
    The p99 assertion fires if the 99th-percentile round exceeds the SLO.

    Provenance: #596 v8-PR-2, council condition #611.
    """
    benchmark(lambda: _get_task_by_id(bench_server))  # noqa: E731

    p99 = _p99_from_benchmark(benchmark)
    assert p99 < _P99_LIMIT_SECONDS, (
        f"GET /tasks/<id> p99 = {p99 * 1000:.1f}ms exceeds the {_P99_LIMIT_SECONDS * 1000:.0f}ms SLO. "
        "This is a REAL FAILURE — do not merge until resolved."
    )


@pytest.mark.benchmark(group="daemon-latency", min_rounds=_MIN_ROUNDS)
def test_benchmark_get_tasks_by_session(benchmark, bench_server):
    """Warm-path p99 for GET /tasks?session=X (50-row result set) must be < 50ms.

    The session query is the hot subagent_lifecycle path; it must stay within
    the 50ms hook budget defined in #596.

    Provenance: #596 v8-PR-2, council condition #611.
    """
    benchmark(lambda: _get_tasks_by_session(bench_server))  # noqa: E731

    p99 = _p99_from_benchmark(benchmark)
    assert p99 < _P99_LIMIT_SECONDS, (
        f"GET /tasks?session=X p99 = {p99 * 1000:.1f}ms exceeds the {_P99_LIMIT_SECONDS * 1000:.0f}ms SLO. "
        "This is a REAL FAILURE — do not merge until resolved."
    )
