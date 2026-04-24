# Banned State Proof — v8-PR-3 (#590)

Any attempt to transition from `completed` raises `InvalidTransition`:

```python
from scripts.crew.phase_state import transition, InvalidTransition
try:
    transition("completed", "approve")
except InvalidTransition as e:
    print(e)  # Phase state 'completed' is banned. Migration required ...
```

Verified by `TestBannedStateRaises` in `tests/crew/test_phase_state.py` (4 cases).
Also enforced at the DB write boundary in `daemon/db.py::upsert_phase`.
