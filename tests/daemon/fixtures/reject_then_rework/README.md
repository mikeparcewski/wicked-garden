Tests the REJECT → rework path. A project is created, then the `design` phase gate returns REJECT (score 0.45). The companion `wicked.gate.blocked` event fires, followed by `wicked.rework.triggered` carrying `iteration_count=1`.

The expected projection is a phase row with `state=active` (REJECTED → ACTIVE transition applied by rework.triggered), `gate_verdict=REJECT`, and `rework_iterations=1`. The project row retains `current_phase=""` because no phase transition has been approved yet.

This fixture locks the invariant that a REJECT sets phase `state=rejected` and `terminal_at`, and then `rework.triggered` flips the phase back to `state=active` while also setting `rework_iterations` via last-write-wins semantics on the payload's `iteration_count` field.

State machine: wicked.gate.decided(REJECT) → state='rejected'; wicked.rework.triggered → state='active' (council C1 fix, #590 #613).
