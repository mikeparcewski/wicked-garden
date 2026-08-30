#!/usr/bin/env bash
# AW-25 golden path — the wiki pipeline's own evidence-gated proof (arch-R21).
#
# Chain (every hop captured as a numbered evidence file):
#   1. seed doc (ruleset/aw25-golden.md, deterministic canary trigger)
#   2. `wicked-core rules ingest` + `rules fanout` into ISOLATED stores
#   3. `rules.recall` over the INSTALLED wicked-estate-mcp returns the rule with citation
#   4. an ISOLATED crew daemon runs a governed run whose intent trips the trigger
#   5. the gate denial cites the rule id + wiki URI
#   6. GET /runs/:id/acceptance carries the ConformanceClaim (deny-dominates)
#
# ISOLATION CONTRACT (never touch real state):
#   - crew daemon on $AW25_PORT (default 7907) with --db/--bus-db under $AW25_WORK
#   - WICKED_CREW_PROJECT_GRAPH_ROOT / WICKED_ESTATE_REPO_GRAPH_ROOT pinned to $AW25_WORK
#   - WICKED_ESTATE_DB pinned to a scratch events store for the rules CLIs (wiki lifecycle
#     events land there, never in the operator's home outbox)
#   - the daemon is killed on exit (trap), pass/fail alike
#
# Binaries (override via env):
#   WICKED_CORE_BIN   wicked-core with the `rules` subcommands (main >= PR#310; the npm/installer
#                     binary predates them — build from wicked-core main if `rules` is missing)
#   CREW_CLI          the crew daemon entry: either an installed `wicked-crew` >= 0.7.2 or
#                     `node <wicked-crew>/packages/crew/dist/cli/index.js` (main >= PR#359 —
#                     the acceptance conformance section; 0.7.1 on npm predates it)
#   ESTATE_MCP_BIN    installed wicked-estate-mcp >= 0.15.1 (rules.recall on the MCP surface)
#
# Exit codes: 0 = full chain PASS · 1 = an assertion failed · 2 = environment/launch failure.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
RULESET="$HERE/ruleset"
TS="$(date +%Y%m%d-%H%M%S)"
AW25_WORK="${AW25_WORK:-${TMPDIR:-/tmp}/aw25-golden-$TS}"
AW25_PORT="${AW25_PORT:-7907}"
EVID="${AW25_EVIDENCE_DIR:-$AW25_WORK/evidence}"
BASE="http://127.0.0.1:$AW25_PORT/api/v1"
MARKER="AW25-GOLDEN-DENY-ME"

WICKED_CORE_BIN="${WICKED_CORE_BIN:-wicked-core}"
CREW_CLI="${CREW_CLI:-wicked-crew}"
ESTATE_MCP_BIN="${ESTATE_MCP_BIN:-wicked-estate-mcp}"
PY="${AW25_PYTHON:-python3}"

mkdir -p "$AW25_WORK/state" "$AW25_WORK/stores" "$EVID"

fail() { echo "AW25 FAIL: $*" >&2; exit 1; }
envfail() { echo "AW25 ENV FAILURE: $*" >&2; exit 2; }

# ── preflight ────────────────────────────────────────────────────────────────
"$WICKED_CORE_BIN" rules --help 2>&1 | grep -q "rules ingest" \
  || envfail "$WICKED_CORE_BIN lacks the 'rules' subcommands — build wicked-core from main (>= #310)"
command -v curl >/dev/null || envfail "curl not found"
# Cross-platform python resolution (macOS/Linux `python3`, Windows Git Bash may only have `python`).
command -v "$PY" >/dev/null || PY=python
command -v "$PY" >/dev/null || envfail "no python3/python on PATH"
if ! command -v "$ESTATE_MCP_BIN" >/dev/null && [ ! -x "$ESTATE_MCP_BIN" ]; then
  envfail "$ESTATE_MCP_BIN not found — cargo install wicked-estate-mcp (>= 0.15.1)"
fi
# Refuse to aim at the operator's real daemon state, ever.
case "$AW25_WORK" in "$HOME/.wicked-crew"*) envfail "AW25_WORK must never resolve under ~/.wicked-crew";; esac
[ "$AW25_PORT" = "7701" ] && envfail "port 7701 is the operator's real daemon — use an isolated 79xx port"

# Wiki lifecycle events (AW-22) from the rules CLIs land in a scratch store, not the home outbox.
export WICKED_ESTATE_DB="$AW25_WORK/stores/events.db"

# ── daemon up (isolated) ─────────────────────────────────────────────────────
export WICKED_CREW_PROJECT_GRAPH_ROOT="$AW25_WORK/state/project-graphs"
export WICKED_ESTATE_REPO_GRAPH_ROOT="$AW25_WORK/state/repo-graphs"
export WICKED_BUS_DATA_DIR="$AW25_WORK/state/bus-data"
mkdir -p "$WICKED_CREW_PROJECT_GRAPH_ROOT" "$WICKED_ESTATE_REPO_GRAPH_ROOT" "$WICKED_BUS_DATA_DIR"

# $CREW_CLI may be a program name or a multi-word "node /path/to/dist/cli/index.js".
# shellcheck disable=SC2086
$CREW_CLI serve --port "$AW25_PORT" \
  --db "$AW25_WORK/state/core.db" \
  --bus-db "$AW25_WORK/state/bus-data/bus.db" \
  > "$EVID/00-daemon-ready.txt" 2>&1 &
DAEMON_PID=$!
cleanup() {
  if kill -0 "$DAEMON_PID" 2>/dev/null; then
    kill "$DAEMON_PID" 2>/dev/null
    wait "$DAEMON_PID" 2>/dev/null
    echo "AW25: isolated daemon (pid $DAEMON_PID) stopped"
  fi
}
trap cleanup EXIT

for _ in $(seq 1 60); do
  curl -sf "$BASE/health" >/dev/null 2>&1 && break
  kill -0 "$DAEMON_PID" 2>/dev/null || { cat "$EVID/00-daemon-ready.txt" >&2; envfail "daemon died on startup"; }
  sleep 0.5
done
curl -sf "$BASE/health" >/dev/null || envfail "daemon never became healthy on :$AW25_PORT"
echo "AW25: isolated daemon up on :$AW25_PORT (state under $AW25_WORK/state)"

# ── 1+2. ingest + fanout the seed ruleset into ISOLATED stores ──────────────
"$WICKED_CORE_BIN" rules ingest "$RULESET" --db "$AW25_WORK/stores/ops.db" \
  > "$EVID/01-ingest.txt" 2>&1 || { cat "$EVID/01-ingest.txt" >&2; fail "rules ingest refused"; }

"$WICKED_CORE_BIN" rules fanout "$RULESET" \
  --enforcement-crew-api "$BASE" \
  --discovery-db "$AW25_WORK/stores/discovery.db" \
  --knowledge-db "$AW25_WORK/stores/knowledge.db" \
  --manifest "$EVID/02-fanout-manifest.json" \
  > "$EVID/02-fanout.txt" 2>&1 || { cat "$EVID/02-fanout.txt" >&2; fail "rules fanout refused"; }

# The enforcement lane is daemon-held → deliver the emitted payload over the crew API
# (audited, single-writer safe; the transport the fanout manifest records as PENDING).
"$PY" - "$EVID/02-fanout-manifest.json.crew-payload.json" "$BASE" <<'PYEOF' > "$EVID/03-enforcement-post.json" || fail "posting enforcement payload failed"
import json, sys, urllib.request
payload = json.load(open(sys.argv[1])); base = sys.argv[2]
out = {"posted_policies": [], "posted_rules": []}
def post(path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        return r.status
for p in payload["policies"]:
    out["posted_policies"].append({"id": p["id"], "status": post("/governance/policies", p)})
for r in payload["rules"]:
    out["posted_rules"].append({"id": r["id"], "status": post("/governance/rules", r)})
with urllib.request.urlopen(base + "/governance/rules/preview") as resp:
    out["rules_preview_after"] = json.load(resp)
print(json.dumps(out, indent=2))
PYEOF

grep -q '"POL-2500"' "$EVID/03-enforcement-post.json" || fail "enforcement lane: POL-2500 not visible in rules/preview after POST"

# ── 3. rules.recall over the INSTALLED estate MCP, against the discovery lane ─
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"rules.recall","arguments":{"rule_type":"policy"}}}' \
  | "$ESTATE_MCP_BIN" --db "$AW25_WORK/stores/discovery.db" 2>/dev/null \
  | "$PY" -c '
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    d = json.loads(line)
    if d.get("id") == 2:
        body = json.loads(d["result"]["content"][0]["text"])
        print(json.dumps(body, indent=2))
        rules = {r["id"]: r for r in body.get("rules", [])}
        r = rules.get("POL-2500")
        assert r is not None, "rules.recall did not return POL-2500"
        ref = r["provenance"]["ref"]
        assert ref.startswith("aw25-golden.md@") and ref.endswith("#POL-2500"), f"citation missing: {ref}"
        assert "wiki://aw25-golden#POL-2500" in r["statement"], "statement lost its wiki URI"
        sys.exit(0)
sys.exit(3)
' > "$EVID/04-rules-recall.json" || fail "rules.recall over the installed estate MCP did not return the cited rule"
echo "AW25: rules.recall returned POL-2500 with its provenance citation"

# ── 4. governed run that TRIPS the trigger ───────────────────────────────────
# The run intent carries the marker, so the unit's evaluated governance context
# (description + work) deterministically matches POL-2500's contains-trigger —
# no reliance on any worker model choosing to echo the token. Kept well under
# the 1022-byte PTY line limit. The reply-length ask matters: a governed unit
# whose output is under 200 trimmed chars is substance-rejected BEFORE the
# governance gate runs (actor.rs PHASE SUBSTANCE GATE), which would skip the
# very claim this scenario proves.
PROBLEM="AW-25 golden-path acceptance canary: the token $MARKER is deliberately planted in this intent so the platform's deterministic governance gate (wiki rule POL-2500) evaluates and denies this unit AFTER your reply — that denial is the expected, correct outcome and is not your job. Do not use tools. Reply with a short paragraph (3-5 sentences, at least 250 characters) explaining why a guardrails pipeline should prove its own deny path with evidence."

# Pin the worker seat (default claude) so re-runs don't wander across the council
# roster — the denial is evaluator-side either way; the pin only removes variance.
AW25_SEAT="${AW25_SEAT:-claude}"
CLIS_JSON=$(curl -sf "$BASE/roster" | "$PY" -c "
import json, sys
seats = [s for s in json.load(sys.stdin)['roster'] if s.get('key') == '$AW25_SEAT']
assert seats, 'seat $AW25_SEAT not in the roster'
print(json.dumps(seats))") || fail "could not pin worker seat '$AW25_SEAT' from the roster"

LAUNCH_BODY=$("$PY" - "$PROBLEM" "$CLIS_JSON" <<'PYEOF'
import json, sys
print(json.dumps({"problem": sys.argv[1], "workflow": "chat", "humanConfirm": "none", "clisJson": sys.argv[2]}))
PYEOF
) || fail "could not build launch body"
RUN_ID=$(curl -sf -X POST "$BASE/runs" -H 'Content-Type: application/json' -d "$LAUNCH_BODY" \
  | "$PY" -c "import json,sys; print(json.load(sys.stdin)['runId'])") || fail "run launch failed"
echo "AW25: governed run launched: $RUN_ID"

# Poll to a TERMINAL state (launch != done — E2E-verified requires terminal state).
STATUS=""
for _ in $(seq 1 240); do
  STATUS=$(curl -sf "$BASE/runs?include=archived" | "$PY" -c "
import json, sys
views = json.load(sys.stdin)['runs']
mine = [v for v in views if v['session']['id'] == '$RUN_ID']
print(mine[0]['session']['status'] if mine else '')")
  case "$STATUS" in
    failed|completed|cancelled) break ;;
  esac
  sleep 5
done
curl -sf "$BASE/runs?include=archived" | "$PY" -c "
import json, sys
views = json.load(sys.stdin)['runs']
mine = [v for v in views if v['session']['id'] == '$RUN_ID']
print(json.dumps(mine[0] if mine else {}, indent=2))" > "$EVID/05-run-terminal.json" 2>/dev/null
case "$STATUS" in
  failed|completed|cancelled) echo "AW25: run terminal: $STATUS" ;;
  *) fail "run $RUN_ID never reached a terminal state (last: '$STATUS')" ;;
esac

# ── 5. the denial cites the rule id + wiki URI ───────────────────────────────
curl -sf "$BASE/governance/claims" > "$EVID/06-governance-claims.json" || fail "claims read failed"
"$PY" - "$EVID/06-governance-claims.json" "$RUN_ID" <<'PYEOF' || fail "no run-scoped denial citing POL-2500 + the wiki URI"
import json, sys
claims = json.load(open(sys.argv[1]))["claims"]
run_id = sys.argv[2]
mine = [c for c in claims if c["scope"].startswith(f"wicked-agent/{run_id}/")]
denies = [c for c in mine if c["decision"] == "deny"]
assert denies, f"no deny claim scoped to run {run_id} (run-scoped claims: {len(mine)})"
cited = [c for c in denies if "POL-2500" in c.get("policy_ids", [])]
assert cited, "deny claim does not name policy POL-2500"
d = cited[0]
text = json.dumps(d)
assert "wiki://aw25-golden#POL-2500" in text, "denial text does not cite the wiki URI"
print(f"denial ok: claim {d['claim_id'][:12]}… policy_ids={d['policy_ids']} cites wiki://aw25-golden#POL-2500", file=sys.stderr)
PYEOF
echo "AW25: gate denial recorded, citing POL-2500 + wiki://aw25-golden#POL-2500"

# ── 6. the ConformanceClaim in GET /runs/:id/acceptance ──────────────────────
curl -sf "$BASE/runs/$RUN_ID/acceptance" > "$EVID/07-acceptance.json" || fail "acceptance read failed"
"$PY" - "$EVID/07-acceptance.json" <<'PYEOF' || fail "acceptance payload does not carry the citing ConformanceClaim"
import json, sys
a = json.load(open(sys.argv[1]))
c = a["conformance"]
assert c["claimsAvailable"] is True, "claims wire unreadable"
assert c["denied"] is True and c["denials"] >= 1, f"no standing denial: {c['denials']}"
deny = [cl for cl in c["claims"] if cl["decision"] == "deny" and "POL-2500" in cl["policyIds"]]
assert deny, "acceptance carries no deny claim naming POL-2500"
cl = deny[0]
cites = [r for r in cl["rules"] if r["ruleId"] == "POL-2500"]
assert cites, "deny claim carries no parsed citation of wiki rule POL-2500"
assert "wiki://aw25-golden#POL-2500" in cites[0]["statement"], "citation statement lost the wiki URI"
assert c["guardrailed"] is False, "a denied run must never read guardrailed"
assert "POL-2500" in c["summary"], f"summary does not cite the rule id: {c['summary']}"
print("acceptance ok: ConformanceClaim visible, deny-dominates, cites POL-2500 + wiki URI", file=sys.stderr)
PYEOF
echo "AW25: acceptance payload carries the ConformanceClaim (deny-dominates, cited)"

echo
echo "AW25 GOLDEN PATH: PASS — evidence chain in $EVID"
