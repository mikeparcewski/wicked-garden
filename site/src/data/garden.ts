/* ============================================================================
   wicked-garden — reimagined site content (single source of truth)
   Positioning: the curated TOOLKIT for what a coding agent can't do alone.
   The soul: "done is re-derived from evidence, never asserted."
   All claims code-grounded against the wicked-garden repo (README/ETHOS/commands)
   and the canonical messaging file. Honest status only — v12.27.0, MIT.
============================================================================ */

export type Hue = "gate" | "floor" | "layer" | "solo" | "creation" | "workflow";

/** The colour a hue resolves to (CSS var). Signal-yellow (gate) is reserved
    for verdict stamps + the primary CTA only — never a tool tint. */
export const HUE_VAR: Record<Hue, string> = {
  gate: "--c-gate",
  floor: "--c-floor",
  layer: "--c-layer",
  solo: "--c-solo",
  creation: "--c-creation",
  workflow: "--c-workflow",
};

/* ── The hero proof: agent CLAIMS that garden re-derives instead of trusting ─
   Each is stamped after the agent asserts it. Mixed verdicts on purpose —
   the point is it CHECKS, and a false claim is caught. */
export interface Claim {
  archetype: string;
  claim: string;
  verdict: "REJECTED" | "RE-DERIVED" | "FAILS CLOSED";
  reason: string;
}

export const CLAIMS: Claim[] = [
  {
    archetype: "build",
    claim: "all acceptance tests pass",
    verdict: "REJECTED",
    reason: "re-ran the verifier — two never executed",
  },
  {
    archetype: "review",
    claim: "reviewed — safe to merge",
    verdict: "RE-DERIVED",
    reason: "independent evaluator agreed · evaluator ≠ author",
  },
  {
    archetype: "migrate",
    claim: "backfill is complete",
    verdict: "REJECTED",
    reason: "recorded evidence hash ≠ the claim",
  },
  {
    archetype: "build",
    claim: "tests pass",
    verdict: "FAILS CLOSED",
    reason: "evidence backend unreachable — never a vacuous green",
  },
];

/* ── garden's OWN tools — the gap-fillers a planner-executor can't do alone ── */
export interface Tool {
  id: string;
  name: string;
  kind: string;
  hue: Hue;
  gap: string;        // the gap in the agent (what it can't do alone)
  fill: string;       // what the tool does — cut hard
  cmd: string;
  cmdLabel: string;
}

export const TOOLS: Tool[] = [
  {
    id: "prove",
    name: "prove",
    kind: "evidence gate",
    hue: "floor",
    gap: "says “done” — sometimes it’s lying",
    fill: "Re-runs the proof behind the claim. A false pass is REJECTED; a missing backend FAILS CLOSED. Never a vacuous green.",
    cmd: "/wicked-garden:prove",
    cmdLabel: "slash command",
  },
  {
    id: "search",
    name: "search",
    kind: "blast-radius · lineage",
    hue: "layer",
    gap: "greps — blind to string-wired links",
    fill: "Sees the injected edges grep can’t — event→consumer, command→agent, agent→capability — so impact analysis is real, not a text match.",
    cmd: "/wicked-garden:search:blast-radius",
    cmdLabel: "slash command",
  },
  {
    id: "patch",
    name: "patch",
    kind: "graph refactor",
    hue: "workflow",
    gap: "refactors on a hope and a prayer",
    fill: "Renames and moves symbols across every file as one graph operation — not find-and-replace roulette.",
    cmd: "/wicked-garden:engineering:rename",
    cmdLabel: "slash command",
  },
  {
    id: "council",
    name: "council",
    kind: "multi-model panel",
    hue: "solo",
    gap: "asks itself for a second opinion",
    fill: "Convenes a real panel of independent external models (Gemini · Codex · …) — a second opinion that isn’t the model grading itself.",
    cmd: "/wicked-garden:jam:council",
    cmdLabel: "slash command",
  },
  {
    id: "archetypes",
    name: "archetypes",
    kind: "work-shape rigor",
    hue: "creation",
    gap: "gives a typo and a migration the same ceremony",
    fill: "Reads the shape of the prompt and applies exactly that much rigor — ten work-shapes, steering not a fixed pipeline.",
    cmd: "/wicked-garden:archetype",
    cmdLabel: "slash command",
  },
  {
    id: "deliberate",
    name: "deliberate",
    kind: "challenge the ask",
    hue: "creation",
    gap: "rushes to build exactly what you typed",
    fill: "Runs the ask through five lenses before a line is written — challenges assumptions, hunts the root cause, and reframes the request when the stated ask isn’t the real one.",
    cmd: "/wicked-garden:deliberate",
    cmdLabel: "slash command",
  },
];

/* ── The wider surface — the domains the toolbox samples from ────────────────
   Every command below is a real slash command in the repo (commands/<domain>/).
   This is the breadth the six signature tools only hint at. Counts are honest:
   81 commands across these domains, 10 work-shapes, 23 garden agents. */
export interface Domain {
  id: string;
  name: string;
  hue: Hue;
  blurb: string;
  count: number;      // real command count in commands/<id>/
  cmds: string[];     // representative commands (not exhaustive)
}

export const DOMAINS: Domain[] = [
  {
    id: "archetype",
    name: "work-shapes",
    hue: "creation",
    blurb: "Ten shapes the hook reads off each prompt — steering how much rigor the work earns, from a typo to a migration cutover.",
    count: 10,
    cmds: ["triage", "explore", "specify", "decide", "build", "review", "ship", "incident", "migrate", "modernize"],
  },
  {
    id: "search",
    name: "code intelligence",
    hue: "layer",
    blurb: "Impact and lineage over the real graph — including the injected edges (bus, dispatch, capability) grep and a static call-graph can’t see.",
    count: 5,
    cmds: ["blast-radius", "lineage", "hotspots", "service-map", "index"],
  },
  {
    id: "engineering",
    name: "engineering",
    hue: "workflow",
    blurb: "Deterministic, graph-driven change: rename and move symbols across files, plan a patch, debug from a stack trace, generate scaffolding.",
    count: 11,
    cmds: ["rename", "debug", "plan", "arch", "patch-plan", "add-field", "remove", "docs", "new-generator"],
  },
  {
    id: "jam",
    name: "multi-model",
    hue: "solo",
    blurb: "A real second opinion that isn’t the model grading itself — convene an independent panel of external CLIs, or brainstorm across personas.",
    count: 4,
    cmds: ["council", "brainstorm", "quick", "revisit"],
  },
  {
    id: "product",
    name: "product & UX",
    hue: "creation",
    blurb: "Turn a vague ask into SMART criteria, review UX and accessibility, draft mockups and visual direction, synthesize user signal.",
    count: 13,
    cmds: ["elicit", "acceptance", "ux", "ux-review", "a11y", "mockup", "strategy", "visual-direction"],
  },
  {
    id: "platform",
    name: "platform & ops",
    hue: "floor",
    blurb: "The rubric loaded on demand — security, compliance, incident response, infra and toolchain audits, GitHub Actions, distributed traces.",
    count: 13,
    cmds: ["security", "compliance", "audit", "incident", "infra", "traces", "actions", "health"],
  },
  {
    id: "data",
    name: "data & ML",
    hue: "layer",
    blurb: "Design ETL pipelines, assess data quality, map an ontology, and reason about ML workflows with the same evidence discipline.",
    count: 5,
    cmds: ["pipeline", "data", "ml", "ontology", "analyze"],
  },
  {
    id: "smaht",
    name: "context & memory",
    hue: "solo",
    blurb: "Pull-model context assembly — a briefing of what happened since last session, live crew state, and imported events, gathered on demand.",
    count: 3,
    cmds: ["briefing", "state", "events-import"],
  },
  {
    id: "agentic",
    name: "agentic review",
    hue: "workflow",
    blurb: "Review an agentic codebase itself — detect frameworks, map agent topology and orchestration, and produce a remediation roadmap.",
    count: 4,
    cmds: ["review", "audit", "design", "frameworks"],
  },
  {
    id: "persona",
    name: "personas",
    hue: "creation",
    blurb: "Run any task under a named behavioral profile — define a persona, act as it, and keep a reusable cast for reviews and brainstorms.",
    count: 3,
    cmds: ["as", "define", "list"],
  },
];

/* ── The evidence conditions the gate re-derives (the drivable centrepiece) ── */
export interface Condition {
  id: string;
  label: string;
  on: string;
  off: string;
}

export const CONDITIONS: Condition[] = [
  { id: "verifier", label: "verifier actually ran", on: "the test command executed", off: "no run — nothing to re-derive" },
  { id: "hash", label: "evidence hash matches", on: "recording is unaltered", off: "hash ≠ recording — edited after the fact" },
  { id: "vault", label: "vault backend present", on: "wicked-vault resolvable", off: "vault pulled — gate can’t re-check" },
  { id: "attest", label: "independent attestation", on: "evaluator ≠ author", off: "evaluator = author — self-grading" },
];

/* ── The shelf: the wider wicked-* family one install puts within reach ─────
   HONEST: vault is the ONE required external peer (>= 0.4.0). The rest are
   opt-in layers. The gate/resolve engine (loom) is ABSORBED in-package as of
   v12.27.0 — it is NOT a peer you install. */
export interface Peer {
  id: string;
  name: string;
  tier: "required" | "opt-in";
  hue: Hue;
  gives: string;
  cmd: string;
  cmdLabel: string;
}

export const PEERS: Peer[] = [
  {
    id: "vault",
    name: "wicked-vault",
    tier: "required",
    hue: "floor",
    gives: "The evidence backend the gate re-derives against — re-hashes, re-runs, and fails closed on a weak worker identity so “evaluator ≠ author” actually means something.",
    cmd: "npx wicked-vault-install",
    cmdLabel: "required peer · ≥ 0.4.0",
  },
  {
    id: "testing",
    name: "wicked-testing",
    tier: "opt-in",
    hue: "layer",
    gives: "A full QE team for coding agents — runs the tests and records the evidence, with the runner kept separate from the judge.",
    cmd: "npx wicked-testing install",
    cmdLabel: "opt-in layer",
  },
  {
    id: "brain",
    name: "wicked-brain",
    tier: "opt-in",
    hue: "solo",
    gives: "Cross-session memory plus the codegraph that blast-radius and lineage read from — context that survives between sessions.",
    cmd: "npx wicked-brain",
    cmdLabel: "opt-in layer",
  },
  {
    id: "understanding",
    name: "wicked-understanding",
    tier: "opt-in",
    hue: "floor",
    gives: "The repo’s own how-to playbooks, loaded from HEAD as on-demand skills — the wiring step and the gotcha that bites.",
    cmd: "npx skills add mikeparcewski/wicked-understanding --all",
    cmdLabel: "opt-in layer",
  },
  {
    id: "bus",
    name: "wicked-bus",
    tier: "opt-in",
    hue: "layer",
    gives: "A local-first SQLite event bus — the audit trail of what every tool did. At-least-once delivery, no server, no infra.",
    cmd: "npm i wicked-bus",
    cmdLabel: "opt-in layer",
  },
  {
    id: "interactive",
    name: "wicked-interactive",
    tier: "opt-in",
    hue: "creation",
    gives: "Describe it, watch it build in the browser, export HTML / PDF / PPTX / video — the visual surface off the same shelf.",
    cmd: "claude plugins install wicked-interactive",
    cmdLabel: "opt-in layer",
  },
];

export const G = {
  version: "v12.27.0",
  ownTools: TOOLS.length,
  peers: PEERS.length,
  domains: DOMAINS.length,
  commands: 81,          // real .md count under commands/**
  agents: 23,            // real .md count under agents/**
  workShapes: 10,
};
