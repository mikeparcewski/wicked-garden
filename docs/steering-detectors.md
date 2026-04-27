# Steering Detectors

Bus-first design for the steering detector registry. Detectors observe what's
happening across a crew run and emit `wicked.steer.*` events when something
crosses a threshold worth flagging. Bus events ARE the audit trail — there is
no shadow ledger.

> **Status:** PR-1 of the epic. This PR ships the **event family + reference
> tail subscriber + schema validator only**. No detectors. No behavior
> subscribers. The wiring proof is what's being landed first.
>
> Decision record: `~/.wicked-brain/projects/wicked-garden/memory/steering-detector-registry-v1-design-decision.md`
> (semantic tier, importance 9).

---

## Event family

Locked by the `wicked-bus:naming` skill.

| Field         | Value                                              |
|---------------|----------------------------------------------------|
| `event_type`  | `wicked.steer.escalated` or `wicked.steer.advised` |
| `domain`      | `wicked-garden`                                    |
| `subdomain`   | `crew.detector.<detector-name>`                    |

`wicked.steer.escalated` carries a **rigor recommendation** (the detector
thinks something downstream should change — escalate review tier, regenerate
test strategy, force a council, etc.).

`wicked.steer.advised` is **informational only** — the detector observed
something noteworthy but is not asking anyone to change behavior.

---

## Payload schema

All required fields, regardless of severity:

| Field                 | Type   | Notes                                                  |
|-----------------------|--------|--------------------------------------------------------|
| `detector`            | string | Must be in the v1 allowlist (see below).              |
| `signal`              | string | Human-readable observation.                            |
| `threshold`           | object | The config that fired (free-form per detector).       |
| `recommended_action`  | string | E.g. `force-full-rigor`. Loose set; warns on unknown. |
| `evidence`            | object | At least one key. Should reference session + project. |
| `session_id`          | string | The session that produced the signal.                 |
| `project_slug`        | string | The crew project slug.                                |
| `timestamp`           | string | ISO8601 (`2026-04-27T10:00:00Z`).                     |

Validator: `scripts/crew/steering_event_schema.py::validate_payload(event_type, payload)`

### Example payload

```json
{
  "detector": "sensitive-path",
  "signal": "auth/login.py touched in this phase",
  "threshold": {
    "extensions": [".py", ".ts", ".go"],
    "globs": ["auth/**", "billing/**"]
  },
  "recommended_action": "force-full-rigor",
  "evidence": {
    "file": "auth/login.py",
    "session_id": "sess-001",
    "project_slug": "fix-auth-redirect",
    "phase": "build"
  },
  "session_id": "sess-001",
  "project_slug": "fix-auth-redirect",
  "timestamp": "2026-04-27T10:00:00Z"
}
```

---

## v1 detector allowlist

These five names are reserved at the schema layer in PR-1. The detectors
themselves ship in later PRs.

| Detector              | Planned `recommended_action`              |
|-----------------------|-------------------------------------------|
| `sensitive-path`      | `force-full-rigor`                        |
| `blast-radius`        | `force-full-rigor`                        |
| `council-split`       | `require-council-review`                  |
| `test-failure-spike`  | `regen-test-strategy`                     |
| `cross-domain-edits`  | `notify-only` (advised, not escalated)    |

Calibration notes from the design decision:

- **sensitive-path** — content-aware path matching (extension filter, not
  directory-only). Highest signal, easiest to calibrate via audit data.
- **blast-radius** — fires when `observed > 2 × estimate AND observed > 8 files`.
  The absolute floor prevents small-task noise.
- **test-failure-spike** — N=3 consecutive non-zero exits after the first green
  baseline. Confirm the pytest exit-code signal source exists before
  implementing.
- **council-split** — ship as-is, optionally soften to a 2nd HITL confirmation.
- **cross-domain-edits** — demoted to `wicked.steer.advised` (not escalated).
  Structural proxy, not a risk signal — revisit after 30 days of data.

Adding a new detector requires (a) adding the name to
`KNOWN_DETECTORS` in `scripts/crew/steering_event_schema.py`, (b) shipping the
detector implementation, and (c) updating this table.

---

## Recommended actions

Loose set — unknown values pass validation with a warning string, not an
error. Initial values:

- `force-full-rigor`
- `regen-test-strategy`
- `require-council-review`
- `notify-only`

---

## Subscribers (planned consumers)

Three known consumers. None of them ship in PR-1 — the table documents the
filter contract each will use.

### `crew:rigor-escalator` (in-plugin)

Filter: `wicked.steer.escalated@wicked-garden`

Acts on escalation recommendations. Reads `recommended_action` and applies the
corresponding rigor change (e.g. flips the active phase to `full` tier when
action is `force-full-rigor`).

### Audit log

Filter: `wicked.steer.*@wicked-garden`

Captures every steering event (both escalated and advised) into a persistent
audit record per the design decision's
`detector_fire.jsonl` schema:

```
detector_name, timestamp, session_id, signal_raw, threshold,
action_recommended, action_taken, override_rationale
```

The audit log is the **first deliverable** before any detector implementation
ships, per all three personas (Principal Engineer, Senior IC, Compliance
Auditor) ratifying the design.

### `wicked-testing:qe-engager` (cross-plugin)

Filter: `wicked.steer.*@wicked-garden` with a payload-level filter for
`subdomain == crew.detector.test-failure-spike`.

Reacts to test-failure spikes by triggering a wicked-testing strategy
regeneration.

---

## Reference tail subscriber

`scripts/crew/steering_tail.py` is the live debug stream — it does **not**
take action, just prints incoming events as one-line JSON:

```bash
# All steering events
python3 scripts/crew/steering_tail.py

# Escalations only
python3 scripts/crew/steering_tail.py --severity=escalated

# A specific detector
python3 scripts/crew/steering_tail.py --detector=sensitive-path

# Resume from a known cursor
python3 scripts/crew/steering_tail.py --from-cursor=<cursor_id>
```

Use this to verify wiring for any new emit point before writing a behavior
subscriber.

---

## Manual emit (for verification during PR-1)

```bash
npx wicked-bus emit \
  --type wicked.steer.escalated \
  --domain wicked-garden \
  --subdomain crew.detector.sensitive-path \
  --payload '{
    "detector": "sensitive-path",
    "signal": "auth/login.py touched",
    "threshold": {"extensions": [".py"]},
    "recommended_action": "force-full-rigor",
    "evidence": {"file": "auth/login.py"},
    "session_id": "test-001",
    "project_slug": "test",
    "timestamp": "2026-04-27T10:00:00Z"
  }'
```

In another shell, run the tail and watch the event arrive:

```bash
python3 scripts/crew/steering_tail.py --severity=escalated
```

---

## Design pointer

Full design decision (rationale, alternatives, persona votes, threshold
calibration):
`~/.wicked-brain/projects/wicked-garden/memory/steering-detector-registry-v1-design-decision.md`
