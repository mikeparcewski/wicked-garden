"""tests/daemon/conftest.py — Shared pytest fixtures for the daemon parity test suite.

Provides:
  - mem_conn: ephemeral in-memory SQLite connection with schema initialised.
  - load_fixture: loads events.jsonl + expected_{project,phases}.json for a named fixture.
  - fake_event_stream: builds an ordered list[dict] from raw event dicts for parameterised
    replay tests.
  - free_port: allocates an OS-assigned TCP port (used by server integration tests, not
    parity tests, but kept here for the shared daemon test suite).

All fixtures are function-scoped (default) — no shared state between tests.

T1: deterministic — no wall-clock, no random, no network.
T3: isolated — each fixture call gets its own in-memory DB.
T6: provenance: #589 parity harness.
"""

from __future__ import annotations

import json
import socket
import sqlite3
import sys
from pathlib import Path
from typing import Any, Generator

import pytest

# ---------------------------------------------------------------------------
# sys.path: daemon/ package must be importable from the repo root.
# Tests import `daemon.db` and `daemon.projector` — those modules live at
# daemon/ off the repo root.  The root conftest already adds scripts/ but does
# NOT add the repo root itself, so we do it here.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mem_conn() -> Generator[sqlite3.Connection, None, None]:
    """Open an in-memory SQLite connection with the daemon schema initialised.

    Why in-memory: guarantees zero cross-test pollution without tmp-file cleanup.
    Schema is applied via daemon.db.init_schema — the same path exercised in
    production, so a schema bug surfaces here rather than only at runtime.
    """
    from daemon.db import connect, init_schema  # type: ignore[import]

    conn = connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture()
def load_fixture():
    """Return a callable that loads a named fixture directory.

    Usage::

        events, expected_project, expected_phases = load_fixture("single_phase_approve")

    Returns:
        (events: list[dict], expected_project: dict, expected_phases: list[dict])

    The fixture directory must contain:
      - events.jsonl           one JSON object per line, event_id ascending
      - expected_project.json  single project dict
      - expected_phases.json   list of phase dicts
    """

    def _load(name: str) -> tuple[list[dict], dict, list[dict]]:
        fixture_dir = _FIXTURES_DIR / name
        if not fixture_dir.is_dir():
            raise FileNotFoundError(
                f"Fixture directory not found: {fixture_dir}. "
                "Available fixtures: "
                + ", ".join(d.name for d in _FIXTURES_DIR.iterdir() if d.is_dir())
            )

        events_path = fixture_dir / "events.jsonl"
        project_path = fixture_dir / "expected_project.json"
        phases_path = fixture_dir / "expected_phases.json"

        events: list[dict] = []
        with events_path.open("r", encoding="utf-8") as fh:
            for line_num, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"events.jsonl line {line_num} in fixture '{name}' is not valid JSON: {exc}"
                    ) from exc

        # Validate strict ordering
        for i in range(1, len(events)):
            prev_id = events[i - 1].get("event_id", 0)
            curr_id = events[i].get("event_id", 0)
            if curr_id <= prev_id:
                raise ValueError(
                    f"events.jsonl in fixture '{name}': event_id must be strictly ascending. "
                    f"Line {i + 1} has event_id={curr_id} after {prev_id}."
                )

        expected_project: dict = json.loads(project_path.read_text(encoding="utf-8"))
        expected_phases: list[dict] = json.loads(phases_path.read_text(encoding="utf-8"))

        return events, expected_project, expected_phases

    return _load


@pytest.fixture()
def fake_event_stream():
    """Return a factory that builds a deterministic event list from keyword dicts.

    Usage::

        stream = fake_event_stream(
            {"event_id": 1, "event_type": "wicked.project.created", ...},
            {"event_id": 2, "event_type": "wicked.phase.transitioned", ...},
        )

    Ensures event_id is monotonically increasing and created_at is populated
    with a fixed sentinel epoch (1_700_000_000) when absent — keeps tests
    wall-clock-free.
    """

    def _build(*events: dict[str, Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        _SENTINEL_TS = 1_700_000_000
        for i, ev in enumerate(events, start=1):
            ev = dict(ev)
            ev.setdefault("event_id", i)
            ev.setdefault("created_at", _SENTINEL_TS + i)
            ev.setdefault("chain_id", None)
            result.append(ev)
        # Validate monotonic event_id
        for j in range(1, len(result)):
            assert result[j]["event_id"] > result[j - 1]["event_id"], (
                f"fake_event_stream: event_id must be strictly ascending at index {j}"
            )
        return result

    return _build


@pytest.fixture()
def free_port() -> int:
    """Allocate an ephemeral TCP port that is not in use.

    Uses SO_REUSEADDR so the OS releases it promptly.  The server must bind
    before another process can steal it — acceptable for local test isolation.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
