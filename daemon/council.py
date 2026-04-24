"""daemon/council.py — Council orchestrator for the wicked-garden v8 daemon.

Issue #594 (v8 PR-4).

ARCHITECTURAL NOTE — mutation carve-out from PR-1 decision #6
--------------------------------------------------------------
PR-1 established the daemon as read-only (events projected from the bus).
PR-2 introduced mutations for event ingestion.  PR-4 adds a second explicit
write path: council sessions.  Council is *synchronous* — the caller POSTs a
question and waits for the full result including synthesis.  There is no bus
event to project from; the daemon *originates* the session row and vote rows.
This is a deliberate, documented carve-out.  The read-only principle still
applies to all projection tables (projects, phases, tasks, cursor, event_log).

Public API
----------
run_council(conn, topic, question, criteria, cli_list, timeout_s) -> CouncilResult
    Fan out the question to all CLIs in parallel threads, persist per-model
    vote rows, call build_council_output for synthesis, call
    hitl_judge.should_pause_council for the HITL decision, write session
    completion, return a CouncilResult.

CouncilResult is a plain dataclass — JSON-serialisable via dataclasses.asdict.
"""

from __future__ import annotations

import logging
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants (R3: no magic values)
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT_S: int = 120
"""Default per-CLI subprocess timeout in seconds (R5: all I/O must have timeouts)."""

_MIN_QUORUM: int = 1
"""Minimum number of successful votes required to attempt synthesis."""

_VERDICT_UNAVAILABLE: str = "unavailable"
"""Recorded when the CLI binary is not found in PATH."""

_VERDICT_TIMEOUT: str = "timeout"
"""Recorded when the CLI subprocess exceeds the timeout (R5: no indefinite waits)."""

_VERDICT_ERROR: str = "error"
"""Recorded when the CLI subprocess exits non-zero or raises an unexpected exception."""

_QUESTION_SCAFFOLD: str = """\
Topic: {topic}
Criteria: {criteria}

{question}

Answer the following 4 questions:

1. RECOMMENDATION: What is your recommendation? Be specific about trade-offs.

2. TOP RISK: What is the single biggest risk with your recommendation?

3. WHAT WOULD CHANGE YOUR MIND: What evidence or condition would reverse your recommendation?

4. DISQUALIFIER: Is any option fundamentally unviable? If so, which and why? If all are viable, say "None."
"""

# LLM CLI roster — matches agents/jam/council.md roster exactly (coordination constraint).
# New CLIs must be added to agents/jam/council.md in the same change.
_DEFAULT_CLI_LIST: tuple[str, ...] = (
    "codex", "gemini", "opencode", "copilot", "claude",
    "pi", "aider", "llm", "aichat", "goose",
)

# Per-CLI invocation recipes.  Keys are CLI names; values are callable factories
# that take (scaffold_path: str) and return the argv list to pass to Popen.
# This table is the single source of truth for how each CLI is invoked —
# it mirrors the Bash snippets in agents/jam/council.md.
_CLI_ARGV: dict[str, Any] = {
    "codex": lambda p: ["codex", "exec", "You are evaluating a question for a council. Answer the 4 questions below precisely.", "--file", p],
    "gemini": lambda p: ["sh", "-c", f'cat {p} | gemini "You are evaluating a question for a council. Answer the 4 questions below precisely."'],
    "opencode": lambda p: ["sh", "-c", f'cat {p} | opencode run "You are evaluating a question for a council. Answer the 4 questions below precisely."'],
    "copilot": lambda p: ["sh", "-c", f'cat {p} | copilot -p "You are evaluating a question for a council. Answer the 4 questions below precisely." --output-format text --available-tools=""'],
    "claude": lambda p: ["sh", "-c", f'cat {p} | claude -p "You are evaluating a question for a council. Answer the 4 questions below precisely."'],
    "pi": lambda p: ["pi", "-p", "You are evaluating a question for a council. Answer the 4 questions below precisely.", f"@{p}"],
    "aider": lambda p: ["aider", "--message-file", p, "--no-git", "--yes-always", "--no-auto-commits", "--no-stream", "--no-analytics"],
    "llm": lambda p: ["sh", "-c", f'cat {p} | llm "You are evaluating a question for a council. Answer the 4 questions below precisely."'],
    "aichat": lambda p: ["sh", "-c", f'cat {p} | aichat -S "You are evaluating a question for a council. Answer the 4 questions below precisely."'],
    "goose": lambda p: ["sh", "-c", f'cat {p} | goose run -i - --system "You are evaluating a question for a council. Answer the 4 questions below precisely."'],
}

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# sys.path: scripts/ must be importable for consensus + hitl_judge
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_ROOT = _REPO_ROOT / "scripts"
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from jam.consensus import build_council_output  # noqa: E402
from crew.hitl_judge import should_pause_council  # noqa: E402
import daemon.db as db  # noqa: E402


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class VoteRecord:
    """One model's council contribution — persisted as a council_votes row."""
    model: str
    verdict: str | None
    confidence: float | None
    rationale: str
    raw_response: str
    latency_ms: int

    def to_vote_dict(self) -> dict[str, Any]:
        """Shape expected by build_council_output + should_pause_council."""
        return {
            "model": self.model,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "raw_text": self.raw_response,
        }


@dataclass
class CouncilResult:
    """Full council output — returned by run_council; JSON-serialisable.

    Fields
    ------
    session_id:
        DB primary key for the council_sessions row.
    raw_votes:
        One VoteRecord per CLI attempted (including unavailable/timeout/error).
    synthesized:
        Output of build_council_output — includes ``raw_votes`` + ``synthesized``
        layers per consensus.py's WG_COUNCIL_OUTPUT mode.
    hitl_decision:
        Dict form of the JudgeDecision from should_pause_council.
    agreement_ratio:
        Float from the consensus scorer; None when synthesis was skipped.
    """
    session_id: str
    raw_votes: list[VoteRecord]
    synthesized: dict[str, Any]
    hitl_decision: dict[str, Any]
    agreement_ratio: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "raw_votes": [asdict(v) for v in self.raw_votes],
            "synthesized": self.synthesized,
            "hitl_decision": self.hitl_decision,
            "agreement_ratio": self.agreement_ratio,
        }


# ---------------------------------------------------------------------------
# Internal: CLI availability probe
# ---------------------------------------------------------------------------

def _cli_available(cli_name: str) -> bool:
    """Return True if cli_name resolves in PATH (cross-platform, no shell)."""
    import shutil
    return shutil.which(cli_name) is not None


# ---------------------------------------------------------------------------
# Internal: single CLI invocation
# ---------------------------------------------------------------------------

def _invoke_cli(
    cli_name: str,
    scaffold_path: str,
    timeout_s: int,
) -> VoteRecord:
    """Run one CLI against the scaffold file and return a VoteRecord.

    Never raises (R2: no bare panics in production paths).  Unavailable, timeout,
    and subprocess errors all produce explicit VoteRecord statuses so they appear
    in the vote matrix and are not silently dropped.

    The raw stdout is stored verbatim; verdict is extracted by looking for the
    first occurrence of APPROVE/REJECT/CONDITIONAL (case-insensitive) on a line
    beginning with "RECOMMENDATION:" — falling back to the first such keyword
    anywhere, then None.
    """
    start = time.monotonic()

    # Probe availability before attempting invocation — avoids a slow Popen
    # failure path on Windows where missing binaries behave differently.
    if not _cli_available(cli_name):
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.debug("council: %s not found in PATH — recording as unavailable", cli_name)
        return VoteRecord(
            model=cli_name,
            verdict=_VERDICT_UNAVAILABLE,
            confidence=None,
            rationale=f"{cli_name} not found in PATH",
            raw_response="",
            latency_ms=latency_ms,
        )

    argv_factory = _CLI_ARGV.get(cli_name)
    if argv_factory is None:
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.warning("council: no argv recipe for CLI %r", cli_name)
        return VoteRecord(
            model=cli_name,
            verdict=_VERDICT_ERROR,
            confidence=None,
            rationale=f"no argv recipe configured for {cli_name}",
            raw_response="",
            latency_ms=latency_ms,
        )

    argv = argv_factory(scaffold_path)
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,  # R5: timeout enforced on every subprocess call
        )
    except subprocess.TimeoutExpired:
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.warning("council: %s exceeded timeout %ds", cli_name, timeout_s)
        return VoteRecord(
            model=cli_name,
            verdict=_VERDICT_TIMEOUT,
            confidence=None,
            rationale=f"{cli_name} exceeded timeout of {timeout_s}s",
            raw_response="",
            latency_ms=latency_ms,
        )
    except Exception as exc:  # noqa: BLE001 — intentional; subprocess errors must not crash the fan-out
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.error("council: unexpected error invoking %s: %s", cli_name, exc, exc_info=True)
        return VoteRecord(
            model=cli_name,
            verdict=_VERDICT_ERROR,
            confidence=None,
            rationale=f"unexpected error: {exc}",
            raw_response="",
            latency_ms=latency_ms,
        )

    latency_ms = int((time.monotonic() - start) * 1000)
    raw_response = result.stdout or ""

    if result.returncode != 0:
        logger.warning(
            "council: %s exited %d — recording as error vote (stderr: %s)",
            cli_name, result.returncode, (result.stderr or "")[:200],
        )
        return VoteRecord(
            model=cli_name,
            verdict=_VERDICT_ERROR,
            confidence=None,
            rationale=f"exited {result.returncode}: {(result.stderr or '')[:200]}",
            raw_response=raw_response,
            latency_ms=latency_ms,
        )

    # Extract a simple verdict from the raw text.
    verdict = _extract_verdict(raw_response)
    from jam.consensus import _extract_rationale  # local import — avoid circular at module level
    rationale = _extract_rationale(raw_response)

    return VoteRecord(
        model=cli_name,
        verdict=verdict,
        confidence=None,  # per agents/jam/council.md rule #1: no confidence scores
        rationale=rationale,
        raw_response=raw_response,
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# Internal: verdict extraction
# ---------------------------------------------------------------------------

import re as _re  # noqa: E402  — stdlib re; imported here to keep the module header clean

_VERDICT_PATTERN = _re.compile(
    r"\b(APPROVE|REJECT|CONDITIONAL|RECOMMEND|ENDORSE|REFUSE|DECLINE)\b",
    _re.IGNORECASE,
)


def _extract_verdict(text: str) -> str | None:
    """Extract the most prominent verdict keyword from raw model output.

    Looks on lines starting with 'RECOMMENDATION:' first, then scans the
    whole text.  Returns None when no keyword matches.
    """
    for line in text.splitlines():
        if line.strip().upper().startswith("RECOMMENDATION:"):
            match = _VERDICT_PATTERN.search(line)
            if match:
                return match.group(0).upper()
    # Fallback: first keyword anywhere in the text
    match = _VERDICT_PATTERN.search(text)
    return match.group(0).upper() if match else None


# ---------------------------------------------------------------------------
# Internal: scaffold file writer
# ---------------------------------------------------------------------------

def _write_scaffold(topic: str, question: str, criteria: str) -> str:
    """Write the question scaffold to a temp file; return the file path.

    Uses tempfile.gettempdir() — works on macOS, Linux, and Windows.
    The caller is responsible for deleting the file.
    """
    content = _QUESTION_SCAFFOLD.format(
        topic=topic,
        criteria=criteria or "general quality, correctness, risk",
        question=question,
    )
    tmp_dir = tempfile.gettempdir()
    tmp_path = Path(tmp_dir) / f"council-scaffold-{uuid.uuid4().hex}.md"
    tmp_path.write_text(content, encoding="utf-8")
    return str(tmp_path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_council(
    conn: sqlite3.Connection,
    topic: str,
    question: str,
    criteria: str = "",
    cli_list: list[str] | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> CouncilResult:
    """Fan out question to N CLIs in parallel, persist votes, synthesise, return result.

    Parameters
    ----------
    conn:
        Open daemon DB connection.  run_council writes council_sessions +
        council_votes rows (explicit mutation carve-out from PR-1 decision #6).
    topic:
        Short label for the decision (used in DB and synthesis output).
    question:
        Full question text passed to each CLI.
    criteria:
        Evaluation dimensions (optional; auto-filled when empty).
    cli_list:
        Which CLIs to probe.  Defaults to the full roster (_DEFAULT_CLI_LIST).
        Pass a subset for testing or when the caller has already detected
        available CLIs.
    timeout_s:
        Per-CLI timeout in seconds (R5: enforced on every subprocess call).

    Returns
    -------
    CouncilResult
        Full result including raw_votes, synthesized output, and hitl_decision.
        The session_id in the result is also the DB primary key for the
        council_sessions row.
    """
    resolved_cli_list: list[str] = list(cli_list) if cli_list else list(_DEFAULT_CLI_LIST)
    session_id = str(uuid.uuid4())

    # --- 1. Insert session row (started) ---
    db.insert_council_session(conn, session_id, topic, question)

    # --- 2. Write scaffold to temp file ---
    scaffold_path = _write_scaffold(topic, question, criteria)
    try:
        # --- 3. Fan out — one thread per CLI (R5: bounded by len(cli_list)) ---
        votes: list[VoteRecord] = []
        # ThreadPoolExecutor with explicit max_workers so we never spawn more
        # threads than CLIs.  If cli_list is empty we produce zero votes and
        # synthesis handles the no-quorum case.
        max_workers = max(1, len(resolved_cli_list))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_cli = {
                pool.submit(_invoke_cli, cli_name, scaffold_path, timeout_s): cli_name
                for cli_name in resolved_cli_list
            }
            for future in as_completed(future_to_cli):
                cli_name = future_to_cli[future]
                try:
                    vote = future.result()
                except Exception as exc:  # noqa: BLE001 — safety net; _invoke_cli should never raise
                    logger.error(
                        "council: future for %r raised unexpectedly: %s", cli_name, exc,
                        exc_info=True,
                    )
                    vote = VoteRecord(
                        model=cli_name,
                        verdict=_VERDICT_ERROR,
                        confidence=None,
                        rationale=f"future raised: {exc}",
                        raw_response="",
                        latency_ms=0,
                    )
                votes.append(vote)

                # --- 4. Persist vote immediately (atomic per model) ---
                db.upsert_council_vote(
                    conn,
                    session_id=session_id,
                    model=vote.model,
                    verdict=vote.verdict,
                    confidence=vote.confidence,
                    rationale=vote.rationale,
                    raw_response=vote.raw_response,
                    latency_ms=vote.latency_ms,
                )
    finally:
        # Always clean up the scaffold temp file.
        try:
            Path(scaffold_path).unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("council: could not remove scaffold temp file: %s", exc)

    # --- 5. Synthesise via consensus.build_council_output ---
    vote_dicts = [v.to_vote_dict() for v in votes]
    # Build a minimal synthesized dict from the vote matrix for the envelope.
    synthesized = _build_synthesis_dict(votes, topic)
    output_envelope = build_council_output(vote_dicts, synthesized)

    # --- 6. HITL judge integration (non-bypassable per spec) ---
    hitl_decision = should_pause_council(votes=vote_dicts)

    # --- 7. Compute agreement ratio from the tally ---
    agreement_ratio = _compute_agreement_ratio(votes)

    # --- 8. Mark session complete in DB ---
    db.complete_council_session(
        conn,
        session_id=session_id,
        synthesized_verdict=synthesized.get("verdict"),
        agreement_ratio=agreement_ratio,
        hitl_paused=hitl_decision.pause,
        hitl_rule_id=hitl_decision.rule_id,
    )

    return CouncilResult(
        session_id=session_id,
        raw_votes=votes,
        synthesized=output_envelope,
        hitl_decision=hitl_decision.to_dict(),
        agreement_ratio=agreement_ratio,
    )


# ---------------------------------------------------------------------------
# Internal: synthesis helpers
# ---------------------------------------------------------------------------

def _build_synthesis_dict(votes: list[VoteRecord], topic: str) -> dict[str, Any]:
    """Build a summary synthesis dict from the collected vote records.

    This is a lightweight pass over the vote records that produces the
    ``synthesized`` layer for build_council_output.  It is NOT the full
    consensus.synthesize() path (which requires Proposal objects from a
    structured jam session) — council.py operates on raw CLI text where
    structured proposals are not available.

    Returns a dict with ``verdict``, ``tally``, ``participant_count``,
    ``topic``, and ``notes``.
    """
    tally: dict[str, int] = {}
    successful_votes: list[VoteRecord] = []
    for v in votes:
        if v.verdict not in (_VERDICT_UNAVAILABLE, _VERDICT_TIMEOUT, _VERDICT_ERROR, None):
            tally[v.verdict] = tally.get(v.verdict, 0) + 1
            successful_votes.append(v)

    dominant_verdict: str | None = None
    if tally:
        dominant_verdict = max(tally, key=lambda k: tally[k])

    notes: list[str] = []
    if any(v.verdict == _VERDICT_UNAVAILABLE for v in votes):
        unavail = [v.model for v in votes if v.verdict == _VERDICT_UNAVAILABLE]
        notes.append(f"unavailable: {', '.join(unavail)}")
    if any(v.verdict == _VERDICT_TIMEOUT for v in votes):
        timed_out = [v.model for v in votes if v.verdict == _VERDICT_TIMEOUT]
        notes.append(f"timeout: {', '.join(timed_out)}")

    return {
        "verdict": dominant_verdict,
        "tally": tally,
        "participant_count": len(successful_votes),
        "topic": topic,
        "notes": notes,
    }


def _compute_agreement_ratio(votes: list[VoteRecord]) -> float | None:
    """Compute agreement ratio as the fraction of successful votes that share the dominant verdict.

    Returns None when there are no successful votes (division by zero avoided).
    """
    tally: dict[str, int] = {}
    for v in votes:
        if v.verdict not in (_VERDICT_UNAVAILABLE, _VERDICT_TIMEOUT, _VERDICT_ERROR, None):
            tally[v.verdict] = tally.get(v.verdict, 0) + 1

    total = sum(tally.values())
    if total == 0:
        return None

    dominant_count = max(tally.values())
    return round(dominant_count / total, 3)
