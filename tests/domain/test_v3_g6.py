"""G6 (DES-j6-build C1 seam): the scope core hands ``domain-run`` is checked before anything runs, and the model calls
resolve ``wicked-core`` to the engine's own binary when the daemon hands it (``WICKED_CORE_EXE``)."""
import contextlib
import io
import json

import pytest

from domain import model_calls, run


def write(tmp_path, body):
    p = tmp_path / "scope.json"
    p.write_bytes(body if isinstance(body, bytes) else json.dumps(body).encode())
    return str(p)


def test_a_well_formed_scope_is_read_whole(tmp_path):
    sc = {"intent": "map launch posture", "phrases": ["launch posture"], "scope_hash": "ab12", "description": "d"}
    assert run.read_scope(write(tmp_path, sc)) == sc
    assert run.read_scope(write(tmp_path, {"intent": "PAYCALC1"})) == {"intent": "PAYCALC1"}


@pytest.mark.parametrize("body,why", [
    (b"not json", "not JSON"),
    (b"\xff\xfe", "not JSON"),
    ([1, 2], "not a JSON object"),
    ("map it", "not a JSON object"),
    (17, "not a JSON object"),
    ({}, "no intent"),
    ({"intent": 17}, "no intent"),
    ({"intent": "  "}, "no intent"),
    ({"intent": "x", "phrases": "launch posture"}, "phrases are not a list"),
    ({"intent": "x", "phrases": ["ok", ""]}, "phrases are not a list"),
    ({"intent": "x", "phrases": [3]}, "phrases are not a list"),
    ({"intent": "x", "scope_hash": 5}, "scope_hash is not a string"),
    ({"intent": "x", "description": ["d"]}, "description is not a string"),
    ({"intent": "x", "repo": "/elsewhere"}, "unknown keys: repo"),
])
def test_a_malformed_scope_is_refused_by_name(tmp_path, body, why):
    with pytest.raises(run.Refused, match=why):
        run.read_scope(write(tmp_path, body))


def test_an_oversized_or_missing_scope_is_refused(tmp_path):
    with pytest.raises(run.Refused, match="over 65536 bytes"):
        run.read_scope(write(tmp_path, {"intent": "x" * (64 * 1024)}))
    with pytest.raises(run.Refused, match="could not be read"):
        run.read_scope(str(tmp_path / "absent.json"))


def test_a_malformed_scope_exits_3_before_any_call(tmp_path):
    path = write(tmp_path, {"intent": 17})
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rc = run.main(["--db", str(tmp_path / "none.db"), "--repo-root", str(tmp_path), "--scope", path,
                       "--out", str(tmp_path / "out")])
    assert rc == 3
    assert "refused: the scope has no intent" in err.getvalue()
    assert not (tmp_path / "out" / "calls").exists()


def test_the_engines_binary_is_used_when_the_daemon_hands_it(monkeypatch, tmp_path):
    monkeypatch.delenv(model_calls.CORE_ENV, raising=False)
    monkeypatch.setenv(model_calls.ENGINE_CORE_ENV, "/engine/wicked-core")
    monkeypatch.setenv("PATH", str(tmp_path))
    assert model_calls.core_bin() == "/engine/wicked-core"
    # an operator override still wins
    monkeypatch.setenv(model_calls.CORE_ENV, "/override/wicked-core")
    assert model_calls.core_bin() == "/override/wicked-core"
    # neither, and none on PATH: refused by name
    monkeypatch.delenv(model_calls.CORE_ENV)
    monkeypatch.setenv(model_calls.ENGINE_CORE_ENV, " ")
    with pytest.raises(RuntimeError, match="WICKED_CORE_EXE"):
        model_calls.core_bin()
