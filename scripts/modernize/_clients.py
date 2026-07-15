"""CLI-backed clients for the modernize extraction slice (garden#989 — the un-mock).

PHASE-1 ran the modernize workers against ``_mocks.EstateClient`` / ``_mocks.BrainClient``
(canned fixtures). This module wires the REAL flow: the workers shell the actual
``wicked-estate`` + ``wicked-core`` CLIs.

Two seams, mirroring ``scripts/_loom.py``'s resolve precedence (env override ->
config -> PATH -> node_modules -> None). We SHELL the binaries (argv lists, no
shell string) and never import other-product code — so the disjoint-build
"imports NO other-product code" doctrine holds at the letter.

- ``estate_client(db)`` -> a CLI-backed :class:`CliEstateClient` when
  ``wicked-estate`` resolves AND a store path is given, else the fixture-backed
  ``_mocks.EstateClient``. Same six method names the workers already call, so no
  SKILL.md changes.
- ``core_client()`` -> a CLI-backed :class:`CliCoreClient` when ``wicked-core``
  resolves, else ``None``. There is NO mock CoreClient: the mock lane is a
  genuinely different flow (``_mocks.BrainClient`` + ``emit_domain_model``
  assemble a doc in Python), whereas the real ``wicked-core domain-graph`` READS
  THE STORE and builds ``requirements_graph.json`` itself — the doc-in/summary-out
  shape does not exist on the real path.

Cross-platform: argv lists via :mod:`subprocess` (never ``shell=True``);
``shutil.which`` for resolution; stdlib only (no third-party deps).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional


# --- binary resolution (mirrors scripts/_loom.py precedence) -----------------

_CONFIG_PATH = Path.home() / ".something-wicked" / "wicked-garden" / "config.json"


def _config_preference(key: str) -> Optional[str]:
    """Read ``tool_preferences.{key}`` from garden's config.json; None on any
    error (mirrors ``_loom._read_config_preference``)."""
    try:
        if not _CONFIG_PATH.exists():
            return None
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):  # valid JSON but not an object -> no prefs
            return None
        prefs = data.get("tool_preferences")
        if isinstance(prefs, dict):
            value = prefs.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    except (json.JSONDecodeError, OSError, ValueError):  # ValueError = non-UTF-8 decode
        return None
    return None


def _resolve_bin(
    env_var: str,
    package: str,
    project_dir: Optional[Path] = None,
) -> Optional[list[str]]:
    """Resolve the argv prefix that invokes ``package``, or ``None``.

    Ladder (first hit wins), matching ``_loom.resolve_loom`` (minus the
    npx tail — these are compiled Rust binaries, not npm packages):
      1. ``env_var`` env. Set-but-empty is the KILL-SWITCH -> None.
      2. ``tool_preferences.<package>`` in config.json.
      3. ``package`` on PATH (``shutil.which``).
      4. project-local ``node_modules/.bin/<package>``.
      else None (-> the caller falls back to the mock / hermetic lane).
    """
    if env_var in os.environ:
        val = os.environ[env_var].strip()
        # An explicit path wins; an empty string is the kill-switch.
        return [val] if val else None

    pref = _config_preference(package)
    if pref:
        return [pref]

    found = shutil.which(package)
    if found:
        return [found]

    base = Path(project_dir) if project_dir else Path.cwd()
    local = base / "node_modules" / ".bin" / package
    if local.exists():
        return [str(local)]

    return None


# Bound every CLI call so a hung peer can't wedge extraction forever (matches
# _loom's _DEFAULT_TIMEOUT). An unrunnable/hung binary fails LOUD + bounded,
# never an indefinite hang or a raw OS traceback.
_DEFAULT_TIMEOUT = 120


def _invoke(argv: list[str]) -> subprocess.CompletedProcess:
    """Run ``argv`` (argv list, never a shell string), bounded + fail-loud."""
    try:
        return subprocess.run(
            argv, capture_output=True, text=True, timeout=_DEFAULT_TIMEOUT
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"{argv[0]} not found or not executable: {e}") from e
    except OSError as e:
        raise RuntimeError(f"{argv[0]} could not be executed: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"{argv[0]} exceeded {_DEFAULT_TIMEOUT}s: {argv[1:]!r}") from e


def _run_json(argv: list[str]) -> Any:
    """Run ``argv`` and parse its stdout as JSON. Fails LOUD on non-zero exit or
    unparseable output — a silent empty would fail governance OPEN."""
    proc = _invoke(argv)
    if proc.returncode != 0:
        raise RuntimeError(
            f"{argv[0]} exited {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    out = proc.stdout.strip()
    if not out:
        raise RuntimeError(f"{argv[0]} produced no output for {argv[1:]!r}")
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{argv[0]} output is not JSON: {e}: {out[:200]!r}") from e


def _run(argv: list[str]) -> str:
    """Run ``argv`` for its side effect (a write). Fails LOUD on non-zero exit."""
    proc = _invoke(argv)
    if proc.returncode != 0:
        raise RuntimeError(
            f"{argv[0]} exited {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def _looks_like_symbol_id(value: str) -> bool:
    """A SymbolId reference, never a bare name (the silent-multiply scar)."""
    return isinstance(value, str) and value.startswith("sym::") and "::" in value[5:]


# --- estate (the frozen read/write surface, CLI-backed) ----------------------

class CliEstateClient:
    """Shells ``wicked-estate`` for the six-method estate surface. Same interface
    as ``_mocks.EstateClient`` so the workers are unchanged.

    Reconciles four mock/CLI mismatches the recon flagged:
      * ``resolve`` returns an object array -> extract each ``.symbol_id`` (mock
        returned a bare ``list[str]``); ``--file`` is EXACT path equality.
      * ``annotate`` ALWAYS passes ``--symbol`` (a bare name fans out to every
        search hit) and ALWAYS ``--replace`` (the CLI defaults to APPEND, which
        would stack duplicate rows across re-index runs).
      * ``set_requirement`` routes to the ``semantics`` subcommand (node_semantics),
        NOT ``annotate``.
      * every op threads ``--db`` so writes + the later ``wicked-core`` read hit
        the SAME store.
    """

    def __init__(self, bin_argv: list[str], db: str):
        self._bin = list(bin_argv)
        self._db = db

    def _argv(self, *parts: str) -> list[str]:
        return [*self._bin, *parts, "--db", self._db]

    def read_clusters(self, params: dict | None = None) -> list[dict[str, Any]]:
        # `--summary` is REQUIRED for the {id,size,members,...} object shape;
        # bare `--json` emits array-of-arrays the mock consumers can't read.
        # An optional `min` cluster-size filter maps to the `[min]` positional.
        argv = self._bin + ["clusters"]
        if params and params.get("min") is not None:
            argv.append(str(int(params["min"])))
        argv += ["--json", "--summary", "--db", self._db]
        data = _run_json(argv)
        return data if isinstance(data, list) else data.get("clusters", [])

    def resolve(self, name: str, file: str | None = None,
                kind: str | None = None) -> list[str]:
        argv = self._argv("resolve", name, "--json")
        if file is not None:
            argv += ["--file", file]  # EXACT location.file equality (not basename)
        if kind is not None:
            argv += ["--kind", kind]
        hits = _run_json(argv)
        # Object array -> pull each SymbolId.
        return [h["symbol_id"] for h in hits if isinstance(h, dict) and h.get("symbol_id")]

    def annotate(self, symbol_id: str, type: str, key: str, value: str,
                 confidence: float | None = None, provenance: str | None = None,
                 replace: bool = True) -> None:
        if not _looks_like_symbol_id(symbol_id):
            raise ValueError(
                f"refusing annotate on non-SymbolId {symbol_id!r} — a bare name fans "
                "out to EVERY search hit (the duplicate-Charge scar); resolve() first"
            )
        argv = self._argv("annotate", "--symbol", symbol_id, "--type", type,
                          "--key", key, "--value", value)
        if confidence is not None:
            argv += ["--confidence", repr(float(confidence))]
        if provenance is not None:
            argv += ["--provenance", provenance]
        if replace:
            argv.append("--replace")  # else the CLI APPENDs (stacks duplicates)
        _run(argv)

    def set_requirement(self, symbol_id: str, requirement: str,
                        validated: bool) -> None:
        if not _looks_like_symbol_id(symbol_id):
            raise ValueError(
                f"refusing set_requirement on non-SymbolId {symbol_id!r} — a bare "
                "name is a silent no-op in estate; resolve() first"
            )
        # node_semantics (requirement/validated), a SEPARATE subcommand from annotate.
        _run(self._argv("semantics", symbol_id, "--requirement", requirement,
                        "--validated", "true" if validated else "false"))

    def read_annotations(self, symbol_id: str) -> list[dict[str, Any]]:
        if not _looks_like_symbol_id(symbol_id):
            raise ValueError(
                f"refusing read_annotations on non-SymbolId {symbol_id!r} — the "
                "positional form name-SEARCHES and would silently miss a SymbolId; "
                "resolve() first"
            )
        # MUST use `--symbol` (not the positional `<name>` form, which name-searches
        # and returns an ARRAY of per-symbol objects — a SymbolId there matches
        # nothing and yields [] silently). `--symbol` returns the single-symbol shape
        # `{ "symbol": ..., "annotations": [...] }`.
        data = _run_json(self._argv("annotations", "--symbol", symbol_id, "--json"))
        if isinstance(data, dict):
            return data.get("annotations", [])
        # Defensive: an unexpected array shape is a contract break, not a silent [].
        raise RuntimeError(
            f"wicked-estate annotations --symbol returned {type(data).__name__}, "
            "expected the single-symbol object {symbol, annotations[]}"
        )

    def find_by_annotation(self, key: str, value: str | None = None) -> list[str]:
        # The real extraction flow does not use a reverse annotation lookup (the
        # extractor resolves forward: name -> SymbolId -> annotate). There is no
        # `wicked-estate find-by-annotation` verb, so this is unsupported on the
        # CLI-backed path — fail loud rather than silently return [].
        raise NotImplementedError(
            "find_by_annotation is not available on the CLI-backed estate client "
            "(no reverse-annotation verb); the real extractor resolves forward "
            "name -> SymbolId -> annotate. Use the mock lane if a test needs it."
        )


# --- core (owns doc assembly on the real path) -------------------------------

class CliCoreClient:
    """Shells ``wicked-core`` for the coverage + domain-graph verbs. NOT a mock of
    ``BrainClient`` — the real flow inverts who assembles the doc: ``wicked-core
    domain-graph`` READS the store and builds ``requirements_graph.json`` itself.
    """

    def __init__(self, bin_argv: list[str]):
        self._bin = list(bin_argv)

    def coverage(self, db: str, out: str) -> dict[str, Any]:
        """Emit the store's front-half coverage report to ``out`` and return it.
        Optional — ``domain_graph`` recomputes coverage internally."""
        _run([*self._bin, "coverage", "--db", db, "--out", out])
        return json.loads(Path(out).read_text())

    def domain_graph(self, db: str, out: str,
                     coverage: str | None = None) -> dict[str, Any]:
        """Build ``requirements_graph.json`` from the annotated store and return
        the parsed doc. FAILS LOUD (raises) if the store's front-half coverage
        < 1.0 (``wicked-core domain-graph`` gates fail-closed and writes nothing).
        A supplied ``coverage`` file is an OPTIONAL cross-check that must agree."""
        argv = [*self._bin, "domain-graph", "--db", db, "--out", out]
        if coverage is not None:
            argv += ["--coverage", coverage]
        _run(argv)
        return json.loads(Path(out).read_text())


# --- factories ---------------------------------------------------------------

ESTATE_ENV = "WICKED_ESTATE_BIN"
CORE_ENV = "WICKED_CORE_BIN"


def estate_client(db: Optional[str] = None,
                  project_dir: Optional[Path] = None):
    """A CLI-backed :class:`CliEstateClient` when ``wicked-estate`` resolves and a
    store ``db`` is given, else the fixture-backed ``_mocks.EstateClient``."""
    bin_argv = _resolve_bin(ESTATE_ENV, "wicked-estate", project_dir)
    if bin_argv and db:
        return CliEstateClient(bin_argv, db)
    from modernize._mocks import EstateClient  # local: the mock is the hermetic lane
    return EstateClient()


def core_client(project_dir: Optional[Path] = None) -> Optional[CliCoreClient]:
    """A CLI-backed :class:`CliCoreClient` when ``wicked-core`` resolves, else
    ``None`` (the caller falls back to the hermetic ``_mocks.BrainClient`` +
    ``emit_domain_model`` doc-assembly lane)."""
    bin_argv = _resolve_bin(CORE_ENV, "wicked-core", project_dir)
    return CliCoreClient(bin_argv) if bin_argv else None
