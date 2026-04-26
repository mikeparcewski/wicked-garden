# Smoke Flow — Solo-Mode HITL Inline Gate Review

## Scenario: Solo developer starts a project and reviews a code-quality gate inline

### Step 1: Create project with --hitl=inline (or --solo-mode alias)

```
$ phase_manager.py my-solo-project create --hitl=inline --description "Small refactor"
Created project: my-solo-project
Phase: clarify (in_progress)
Dir: ~/.something-wicked/wicked-crew/projects/my-solo-project

[state.extras["solo_mode"] = True persisted]
```

### Step 2: Session restart — bootstrap emits banner

```
[SOLO MODE ACTIVE] Council gates replaced with inline human review for this
project. Gate artifacts are preserved. Merge-gate council pattern is unchanged.
```

### Step 3: Build phase gate fires (code-quality, mode: human-inline)

The gate policy entry has `"mode": "human-inline"`. `_dispatch_gate_reviewer`
routes to `_dispatch_human_inline`, which calls `solo_mode.dispatch_human_inline`.

```
╔══════════════════════════════════════════════╗
║ INLINE GATE REVIEW — phase: build            ║
╚══════════════════════════════════════════════╝

Evidence summary:
  • Gate 'code-quality' at phase 'build'
  • Minimum passing score: 0.7
  • Evidence required: code-review-complete
  • Normal reviewers (replaced by inline): gate-adjudicator, senior-engineer
  • Rigor tier: standard

Verdict? [APPROVE / CONDITIONAL: <conditions> / REJECT: <reason>]
> CONDITIONAL: Linting errors in src/utils.py lines 45-48 must be fixed
```

### Step 4: CONDITIONAL verdict — conditions-manifest written

Artifacts written:
- `phases/build/gate-result.json`
  ```json
  {
    "verdict": "CONDITIONAL",
    "reviewer": "human-inline",
    "score": 0.7,
    "mode": "human-inline",
    "dispatch_mode": "human-inline",
    "context_ref": "phases/build/inline-review-context.md",
    ...
  }
  ```
- `phases/build/inline-review-context.md`
- `phases/build/conditions-manifest.json`
  ```json
  {
    "conditions": [{
      "id": "C-inline-1",
      "description": "Linting errors in src/utils.py lines 45-48 must be fixed",
      "status": "pending",
      "source": "human-inline-review"
    }]
  }
  ```

### Step 5: AC-4.4 auto-resolution in next phase surfaces C-inline-1

Next-phase gate or reviewer reads conditions-manifest.json and attempts
resolution. The condition is structured inline; `id: C-inline-1` is the
stable handle.

### Step 6: Headless CI run

Same project checked out in CI (no TTY). `WG_HEADLESS=true` or stdin is not a
TTY. `_is_interactive()` returns False.

`solo_mode.dispatch_human_inline` returns stub with
`mode_fallback_reason: "no-interactive-session"`.

`_dispatch_human_inline` in `phase_manager.py` detects the fallback and
routes to `_dispatch_council` with the original reviewer list. The council
result carries `mode_fallback_reason` and `original_mode: "human-inline"` in
the merged dict so audit trails record why council ran instead.

### Step 7: Full-rigor guard

```
$ phase_manager.py my-full-project create --hitl=inline
Error: Solo-mode is not available at full rigor. Use `/wicked-garden:crew:gate`
to dispatch council review.
```
