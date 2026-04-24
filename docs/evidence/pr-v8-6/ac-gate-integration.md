# AC Gate Integration — v8-PR-6

Worked example of `full` mode querying structured ACs at the clarify gate.

## Setup

```python
from pathlib import Path
from crew.autonomy import apply_policy, get_mode, AutonomyMode, GATE_CLARIFY, load_policy

mode = AutonomyMode.FULL  # or: get_mode(cli_arg="full")
policy = load_policy()
```

## Case 1: All ACs satisfied → auto-proceed

Given a project with `phases/clarify/ac-evidence.json`:

```json
[
  {"id": "AC-1", "statement": "Users can log in", "satisfied": true, "satisfied_by": ["tests/test_auth.py::test_login"]},
  {"id": "AC-2", "statement": "Invalid credentials rejected", "satisfied": true, "satisfied_by": ["tests/test_auth.py::test_invalid"]}
]
```

```python
decision = apply_policy(
    mode,
    GATE_CLARIFY,
    {
        "complexity": 3,
        "facilitator_confidence": 0.85,
        "open_questions": 0,
        "project_dir": "/path/to/project",
    },
    policy=policy,
)

# decision.proceed == True
# decision.reason  == "full mode: all ACs satisfied + HITL judge auto-proceed (2/2 ACs satisfied)"
```

## Case 2: Partial ACs + low confidence → pause

```json
[
  {"id": "AC-1", "statement": "Users can log in", "satisfied": true, "satisfied_by": ["tests/test_auth.py::test_login"]},
  {"id": "AC-2", "statement": "Invalid credentials rejected", "satisfied": false, "satisfied_by": []}
]
```

```python
decision = apply_policy(
    mode,
    GATE_CLARIFY,
    {
        "complexity": 2,
        "facilitator_confidence": 0.5,   # below 0.7 threshold
        "open_questions": 0,
        "project_dir": "/path/to/project",
    },
    policy=policy,
)

# decision.proceed == False
# decision.reason  contains "ACs not all satisfied" and HITL judge reason
```

## Case 3: No AC module available (graceful fallback)

When `acceptance_criteria.py` is unavailable or no `project_dir` is provided,
`full` mode falls back to HITL judge:

```python
decision = apply_policy(
    mode,
    GATE_CLARIFY,
    {
        "complexity": 2,
        "facilitator_confidence": 0.9,
        "open_questions": 0,
        # no project_dir
    },
    policy=policy,
)

# decision.proceed == True  (clean signals → HITL judge auto-proceeds)
# decision.reason contains "no AC module"
```

## Case 4: Pre-computed AC status (fast path)

Pass `ac_satisfied` directly to skip file I/O:

```python
decision = apply_policy(
    mode,
    GATE_CLARIFY,
    {
        "complexity": 2,
        "facilitator_confidence": 0.9,
        "open_questions": 0,
        "ac_satisfied": True,           # pre-computed
    },
    policy=policy,
)

# decision.proceed == True
```

## Where the integration lives

- `scripts/crew/autonomy.py::_check_ac_gate()` — queries `acceptance_criteria.load_acs()`.
- `scripts/crew/acceptance_criteria.py` — stub interface; PR-5 full implementation populates `ac-evidence.json`.
- `tests/crew/test_autonomy.py::TestApplyPolicyFull` — 4 tests covering cases 1-4.

## Interaction with PR-5

PR-5 (#617) adds the structured AC store.  The `ac-evidence.json` format that
`autonomy.py` reads matches the schema PR-5 writes.  When PR-5 ships its own
`load_acs()` implementation it replaces the stub in `acceptance_criteria.py`
without any changes to `autonomy.py`.
