Tests the state-machine invariant that wicked.rework.triggered transitions a REJECTED phase back to ACTIVE.

Event sequence: project.created → phase.transitioned(clarify→build) → gate.decided(REJECT) → rework.triggered.

Expected end state: build phase has state='active', rework_iterations=1, gate_verdict='REJECT' still present from the gate event.
The clarify phase is approved (from the phase.transitioned event setting phase_from=clarify to approved).

This fixture covers the bug fixed in #590/#613 (council C1): _rework_triggered must call
upsert_phase(state=PhaseState.ACTIVE) after incrementing rework_iterations. Without the fix
the phase remains state='rejected' and can never advance.

Provenance: #590 #613 council C1 fix-up.
