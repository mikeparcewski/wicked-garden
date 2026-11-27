"""J6 v3's one model client (DES-j6-build §2, D1/D2): every call is prompt in, text out, through the daemon's own
seat (``wicked-core model-call --family claude|codex``, the Tool step's channel). Claude Code writes, Codex checks.

The call log keeps the J6 v3 proof's shape (``proof-v3/scripts/calls.py``): each call's prompt and text under
``<calls>/<step>/<id>.*``, one ``ledger.jsonl`` row per call, a re-run reuses a completed call whose prompt is
byte-identical, and a different prompt under an existing step and id is refused. The transport changed: the proof
ran the CLIs on its own host; here the engine runs the signed-in seat (under the container floor, in the seat
container through the gateway). What the proof set per call is carried through it: the writer's output cap
(``CLAUDE_CODE_MAX_OUTPUT_TOKENS=64000`` on extract, M-repair and repair; :data:`WRITER_MAX_OUTPUT`) is
``model-call --max-output-tokens``. The proof's ``tools``, ``cwd`` and ``env`` arguments are not: the engine's
tool-free posture and the seat's own home replace them. Stdlib only.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import time

WRITER, CHECKER = "claude", "codex"
WRITER_MAX_OUTPUT = 64000  # the proof's CLAUDE_CODE_MAX_OUTPUT_TOKENS on extract, M-repair and repair (38.7K seen)
FAMILY = {"claude": "anthropic", "codex": "openai"}
CORE_ENV = "WICKED_CORE_BIN"
ENGINE_CORE_ENV = "WICKED_CORE_EXE"
_state = {"calls": None, "carry": None}
CARRIED = "cache hit: carried from an earlier attempt"


class CallFailed(RuntimeError):
    """A call whose answer the run cannot go on without (the writer's extract) did not answer: the run stops before it
    stores anything, so a signed-out or timed-out seat never stands for an empty model."""


def answered(text, rc):
    """A call answered: exit 0 with some text (an empty answer is no answer)."""
    return rc == 0 and bool((text or "").strip())


def configure(calls_dir):
    """Where this run keeps its calls (``<run out>/calls``)."""
    os.makedirs(calls_dir, exist_ok=True)
    _state["calls"] = calls_dir


def carry_to(carry_dir):
    """garden#1614: where this run keeps the answers a later attempt of the same scope may reuse
    (``<runs>/.carry/<scope hash>``), or None. Each attempt has its own calls directory, so without this a retry after
    a failed check pays for every writer call again."""
    if carry_dir:
        os.makedirs(carry_dir, exist_ok=True)
    _state["carry"] = carry_dir


def drop_carry():
    """A run that stored its model keeps no carry: only a failed attempt leaves its answers behind."""
    d, _state["carry"] = _state["carry"], None
    if d and os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)


def _carry_path(family, step, prompt):
    d = _state["carry"]
    if not d:
        return None
    return os.path.join(d, hashlib.sha256(f"{family}\0{step}\0{prompt}".encode()).hexdigest() + ".out.txt")


def core_bin():
    """The wicked-core this step's calls go through: ``WICKED_CORE_BIN`` (an operator override), else the engine's own
    binary, which the daemon hands an armed step as ``WICKED_CORE_EXE`` (core C1), else PATH."""
    # a blank value is unset; a value with text is taken verbatim (a path may end in a space)
    given = [os.environ.get(k) or "" for k in (CORE_ENV, ENGINE_CORE_ENV)]
    b = next((v for v in given if v.strip()), None) or shutil.which("wicked-core")
    if not b:
        raise RuntimeError("wicked-core is not resolvable (WICKED_CORE_BIN, WICKED_CORE_EXE or PATH): "
                           "no model call can run")
    return b


def check_distinct(validator_cli=CHECKER):
    """The writer and the checker must be different model families (DES-j6-build D2)."""
    fams = {"extractor": FAMILY[WRITER], "validator": FAMILY.get(validator_cli, validator_cli)}
    if len(set(fams.values())) != 2:
        raise SystemExit(f"refusing to start: providers not distinct {fams}")
    return fams


def _calls():
    if not _state["calls"]:
        raise RuntimeError("model_calls.configure(<run out>/calls) was not called")
    return _state["calls"]


def _log(step, cid, role, provider, wall, ok, note=""):
    row = dict(ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), step=step, id=cid, role=role,
               provider=provider, wall_s=round(wall, 1), ok=ok, note=note)
    with open(os.path.join(_calls(), "ledger.jsonl"), "a") as f:
        f.write(json.dumps(row) + "\n")


def _paths(step, cid):
    d = os.path.join(_calls(), step)
    os.makedirs(d, exist_ok=True)
    return d, os.path.join(d, cid)


def _read(path):
    with open(path) as fh:
        return fh.read()


def _write(path, text):
    with open(path, "w") as fh:
        fh.write(text)


def _no_overwrite(base, prompt):
    """A different prompt under an existing step/id would overwrite earlier evidence. Refuse; use a new step."""
    if os.path.exists(base + ".prompt.txt") and _read(base + ".prompt.txt") != prompt:
        raise RuntimeError(f"{base}: a different prompt already ran under this step/id; use a new step name")


def _cached(base, prompt):
    """Same call id + byte-identical prompt + a completed output -> reuse it (a re-run, not a new call)."""
    try:
        if _read(base + ".prompt.txt") == prompt and os.path.getsize(base + ".out.txt") > 0:
            return _read(base + ".out.txt")
    except OSError:
        return None
    return None


def call(family, step, cid, prompt, timeout=1500, role=None, max_output_tokens=None):
    """One call to the ``family`` seat. Returns ``(text, rc)``: rc 0 answered, else the client's exit code.
    ``max_output_tokens`` caps the seat's answer (``model-call --max-output-tokens``)."""
    role = role or ("extractor" if family == WRITER else "validator")
    d, base = _paths(step, cid)
    _no_overwrite(base, prompt)
    c = _cached(base, prompt)
    if c is not None:
        _log(step, cid, role, family, 0, True, "cache hit: reused the completed call")
        return c, 0
    _write(base + ".prompt.txt", prompt)
    carried = _carry_path(family, step, prompt)
    try:
        c = _read(carried) if carried else None
    except OSError:
        c = None
    if c and c.strip():
        # the same step and byte-identical prompt answered in an earlier, failed attempt of this scope
        _write(base + ".out.txt", c)
        _log(step, cid, role, family, 0, True, CARRIED)
        return c, 0
    out = base + ".out.tmp"
    t0 = time.time()
    try:
        cmd = [core_bin(), "model-call", "--family", family, "--in", base + ".prompt.txt", "--out", out,
               "--timeout-s", str(int(timeout))]
        if max_output_tokens:
            cmd += ["--max-output-tokens", str(int(max_output_tokens))]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 180)
        rc, err = r.returncode, r.stderr
    except subprocess.TimeoutExpired:
        rc, err = 124, "TIMEOUT"
    wall = time.time() - t0
    text = _read(out) if rc == 0 and os.path.exists(out) else ""
    if os.path.exists(out):
        os.replace(out, base + ".out.txt") if text else os.remove(out)
    if text and carried:
        tmp = f"{carried}.{os.getpid()}.tmp"
        try:
            _write(tmp, text)
            os.replace(tmp, carried)
        except OSError:
            pass  # a carry is a saving, never a reason to fail the call
    if err:
        _write(base + ".stderr.txt", err[-5000:])
    _log(step, cid, role, family, wall, rc == 0 and bool(text), "" if rc == 0 else err[-300:])
    return text, rc


def claude(step, cid, prompt, timeout=1500, role="extractor", max_output_tokens=None):
    """The writer."""
    return call(WRITER, step, cid, prompt, timeout=timeout, role=role, max_output_tokens=max_output_tokens)


def codex(step, cid, prompt, timeout=1500, role="validator"):
    """The checker."""
    return call(CHECKER, step, cid, prompt, timeout=timeout, role=role)


# The answer fields that hold lists of objects: a model's `null` is an empty list and a non-object element is
# dropped, so no reader of an answer meets a shape the prompts never asked for.
OBJECT_LISTS = frozenset(("targets", "results", "repairs", "claims", "statements", "verdicts", "groups", "findings",
                          "not_rules", "details"))


def _shape(v):
    if isinstance(v, dict):
        return {k: ([_shape(x) for x in (v[k] or []) if isinstance(x, dict)]
                    if k in OBJECT_LISTS and (v[k] is None or isinstance(v[k], list)) else _shape(v[k])) for k in v}
    if isinstance(v, list):
        return [_shape(x) for x in v]
    return v


def parse_json(text):
    """The first top-level JSON object in a model's text (strips code fences), shaped (:data:`OBJECT_LISTS`)."""
    j = _parse(text)
    return _shape(j) if isinstance(j, dict) else None


def _parse(text):
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```\s*$", "", t)
    try:
        return json.loads(t)
    except Exception:
        pass
    i = t.find("{")
    while i >= 0:
        depth, instr, esc = 0, False, False
        for j in range(i, len(t)):
            ch = t[j]
            if instr:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    instr = False
                continue
            if ch == '"':
                instr = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[i:j + 1])
                    except Exception:
                        break
        i = t.find("{", i + 1)
    return None

