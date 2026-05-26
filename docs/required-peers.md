# Required Peers

Wicked Garden does not stand alone. As of **v12**, four peer plugins are
**required infrastructure** — not optional integrations you bolt on for
extra credit. The garden's honest-evidence model is load-bearing on all
four; remove any one and "done" stops being re-derivable.

This is a deliberate shift. Earlier versions framed wicked-brain and
wicked-bus as *recommended companions* — nice to have, fine to skip.
v12 retired that framing. The four peers below are what the garden is
built on, and `/wicked-garden:setup` treats them that way.

## The four peers

| Peer | What it does | Install | How it's verified |
|------|--------------|---------|-------------------|
| **wicked-testing** | Evidence-gated acceptance testing with three-agent writer/executor/reviewer separation — the writer designs, the executor collects artifacts, the reviewer judges independently. Eliminates self-graded "it passed." | `npx wicked-testing install` (npm; pinned `^0.3.0` in `plugin.json`) | `/wicked-garden:setup` verifies at install |
| **wicked-vault** | The honest-evidence backend every archetype gate re-derives against: record → re-hash + re-run the verifier → cross-check. Never trusts a cached status. | `npx wicked-vault-install` (npm; pinned `^0.3.0`) | `/wicked-garden:setup` verifies at install; resolved at runtime via `WICKED_VAULT_BIN` → config → `PATH` → `node_modules` → `npx wicked-vault` |
| **wicked-brain** | Cross-session memory and cited search — the knowledge layer that carries decisions, gotchas, and patterns from session 1 to session 47. Runs a local server. | `/plugin install wicked-brain` (also on npm `0.14.0`) | SessionStart bootstrap probe |
| **wicked-bus** | The event audit substrate — fire-and-forget events that record what happened. | `/plugin install wicked-bus` (also on npm `2.0.0`) | SessionStart bootstrap probe |

`/wicked-garden:setup` verifies all four and **blocks** without them. The
SessionStart bootstrap hook independently probes for them and **warns**
(non-blocking) when one isn't resolvable.

## The stance: required at install, resilient at runtime

This is the part worth reading twice, because it looks like a
contradiction and isn't.

- **Required at install.** You must install all four. Setup will not let
  you skip them. The garden assumes they are present.
- **Resilient at runtime.** A transient outage — the brain server
  momentarily down, the bus briefly unavailable — **degrades gracefully**
  and does **not** crash your session. A hiccup won't brick you.

"Required" means *you must install it*. "Resilient" means *a runtime
hiccup won't take down the session*. Those answer two different
questions. The first is about setup-time guarantees; the second is about
defense-in-depth at runtime. Holding both is deliberate: we want the
strong guarantee that the infrastructure exists, and we want the system
to survive the moment that infrastructure flickers.

The vault carries a literal kill-switch for the same reason — set
`WICKED_VAULT_BIN=""` and the runtime resolution short-circuits cleanly
rather than thrashing.

## Why each is load-bearing

The four together are the garden's infrastructure, and each holds up a
different beam:

- **wicked-testing proves behavior.** Without it, "the tests pass" is a
  claim no independent party checked.
- **wicked-vault makes "done" re-derivable.** Gates re-hash the evidence
  and re-run the verifier instead of trusting a status field. A
  claimed-but-false pass is rejected; a missing vault fails closed.
- **wicked-brain carries knowledge across sessions.** Without it, every
  session starts from scratch and guesses at history it can't see.
- **wicked-bus carries the audit trail.** Without it, there's no record
  of what the archetypes actually did.

Make any one of them merely optional and the honest-evidence model
springs a leak: behavior goes unproven, "done" becomes self-asserted,
context evaporates between sessions, or the audit trail goes dark. That
is why they are required — and why the runtime stays resilient anyway.
