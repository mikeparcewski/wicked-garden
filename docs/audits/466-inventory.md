# #466 — CREW_GATE_ENFORCEMENT=legacy Audit Inventory

**Closed by**: PR #472 (batch α mode-3 infrastructure)
**Branch**: feat/466-mode3-crew-execution
**v6.0 posture**: strict enforcement unconditional; env-var bypass removed.

## Files changed

| File | Change | Kind |
|---|---|---|
| `hooks/scripts/pre_tool.py` | removed `CREW_GATE_ENFORCEMENT=legacy` branch in `_challenge_gate_bypassed` | code |
| `scripts/crew/phase_manager.py` | removed 3 env-var branches + comments (lines 929, 965, 974-977, 1086, 1562, 1643, 1652) | code |
| `scripts/crew/convergence.py` | removed `legacy_bypass` read + dict field | code |
| `.claude/CLAUDE.md` | removed Rollback bullet + WG_TASK_METADATA mirror note | docs |
| `.claude-plugin/gate-policy.json` | description text → "bypass not supported" | config |
| `agents/qe/semantic-reviewer.md` | replaced Bypass section | docs |
| `commands/crew/convergence.md` | replaced note line | docs |
| `skills/propose-process/refs/challenge-gate.md` | kept `WG_CHALLENGE_GATE=off` (scoped), noted global switch removed | docs |
| `scenarios/crew/gate-enforcement-adversarial.md` | removed Step 8 (legacy bypass test) | scenario |
| `tests/crew/test_approve_sessionstate.py` | removed `TestLegacyBypass` class | test |
| `tests/crew/test_convergence.py` | removed `test_legacy_bypass_forces_approve` | test |
| `tests/crew/test_gate_enforcement.py` | removed 4 setUp env-pop lines | test |
| `tests/qe/test_semantic_review.py` | removed `TestLegacyBypass` class | test |

## Retained references (intentional)

| File | Why |
|---|---|
| `CHANGELOG.md` | historical release-note entries |
| `tests/crew/test_adopt_legacy.py` | migration-tool tests that detect/transform leftover legacy references in USER projects |
| `hooks/scripts/pre_tool.py` (comments) | explicit "removed in #466" historical notes |
| `skills/propose-process/refs/challenge-gate.md` (replacement text) | one-line historical marker |

## Rollback posture

Rollback = git revert on PR #472. No runtime toggle. Strict mode is hardcoded at `scripts/crew/phase_manager.py:67` (`GATE_ENFORCEMENT_MODE="strict"`).
