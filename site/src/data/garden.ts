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

/* ── garden's OWN tools — the gap-fillers a planner-executor can't do alone ──
   The plugin is skills-only: `cmd` is the real dash-separated skill name
   (skills/<dir>/SKILL.md `name:`), invoked by name — no colon namespace, no
   slash commands. `cmdLabel` names the garden skill (and its representative
   action) the signature tool maps to. */
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
    cmd: "wicked-garden-prove",
    cmdLabel: "garden skill",
  },
  {
    id: "search",
    name: "search",
    kind: "blast-radius · lineage",
    hue: "layer",
    gap: "greps — blind to string-wired links",
    fill: "Sees the injected edges grep can’t — event→consumer, command→agent, agent→capability — so impact analysis is real, not a text match.",
    cmd: "wicked-garden-search",
    cmdLabel: "garden skill · blast-radius",
  },
  {
    id: "patch",
    name: "patch",
    kind: "graph refactor",
    hue: "workflow",
    gap: "refactors on a hope and a prayer",
    fill: "Renames and moves symbols across every file as one graph operation — not find-and-replace roulette.",
    cmd: "wicked-garden-engineering",
    cmdLabel: "garden skill · patch / rename",
  },
  {
    id: "council",
    name: "council",
    kind: "multi-model panel",
    hue: "solo",
    gap: "asks itself for a second opinion",
    fill: "Convenes a real panel of independent external models (Gemini · Codex · …) — a second opinion that isn’t the model grading itself.",
    cmd: "wicked-garden-jam",
    cmdLabel: "garden skill · council",
  },
  {
    id: "archetypes",
    name: "archetypes",
    kind: "work-shape rigor",
    hue: "creation",
    gap: "gives a typo and a migration the same ceremony",
    fill: "Reads the shape of the prompt and applies exactly that much rigor — ten work-shapes, steering not a fixed pipeline.",
    cmd: "wicked-garden-archetype",
    cmdLabel: "garden skill",
  },
  {
    id: "deliberate",
    name: "deliberate",
    kind: "challenge the ask",
    hue: "creation",
    gap: "rushes to build exactly what you typed",
    fill: "Runs the ask through five lenses before a line is written — challenges assumptions, hunts the root cause, and reframes the request when the stated ask isn’t the real one.",
    cmd: "wicked-garden-deliberate",
    cmdLabel: "garden skill",
  },
];

/* ── The wider surface — the 12 domains the toolbox samples from ─────────────
   Every chip below is a real skill or routed action in the repo (skills/<dir>/).
   This is the breadth the six signature tools only hint at. Counts are honest:
   94 skills folded into these 12 domains (per-domain routers + fork workers),
   10 work-shapes, 34 fork/worker skills — verified against skills/**. */
export interface Domain {
  id: string;
  name: string;
  hue: Hue;
  blurb: string;
  count: number;      // real SKILL.md count under skills/** for this domain (routers + fork workers folded in)
  cmds: string[];     // representative skills / routed actions (not exhaustive)
}

export const DOMAINS: Domain[] = [
  {
    id: "product",
    name: "product & UX",
    hue: "creation",
    blurb: "Vague ask → SMART criteria, UX & a11y review, mockups, visual direction, user-signal synthesis.",
    count: 25,
    cmds: ["requirements-analysis", "acceptance-criteria", "ux-review", "accessibility", "mockup", "strategy"],
  },
  {
    id: "platform",
    name: "platform & ops",
    hue: "floor",
    blurb: "The rubric on demand — security, compliance, incident, infra, distributed traces, CI.",
    count: 16,
    cmds: ["audit", "compliance", "incident", "infra", "observability", "github-actions"],
  },
  {
    id: "engineering",
    name: "engineering",
    hue: "workflow",
    blurb: "Graph-driven change — rename & patch across files, debug from a trace, architecture, docs.",
    count: 14,
    cmds: ["architecture", "debugging", "patch", "system-design", "integration", "large-scale-migration"],
  },
  {
    id: "agentic",
    name: "agentic review",
    hue: "workflow",
    blurb: "Review the agentic codebase itself — topology, framework detection, trust & safety.",
    count: 9,
    cmds: ["agentic-patterns", "context-engineering", "frameworks", "review-methodology", "trust-and-safety"],
  },
  {
    id: "crew",
    name: "orchestration",
    hue: "layer",
    blurb: "Orchestration workers — implement, research, review; swarm, worktrees, workflow runners.",
    count: 9,
    cmds: ["crew-implementer", "crew-researcher", "crew-reviewer", "swarm", "worktrees", "workflow"],
  },
  {
    id: "smaht",
    name: "context",
    hue: "solo",
    blurb: "Pull-model context — briefing, intent, propose-skills, classify a request, ground it in the repo.",
    count: 7,
    cmds: ["discovery", "intent", "propose-skills", "classify", "ground"],
  },
  {
    id: "jam",
    name: "multi-model",
    hue: "solo",
    blurb: "A second opinion that isn’t self-grading — an independent external-model panel and facilitator.",
    count: 4,
    cmds: ["council", "brainstorm", "multi-model"],
  },
  {
    id: "qe",
    name: "evidence",
    hue: "floor",
    blurb: "Evidence, re-derived — prove re-runs the proof; a semantic reviewer checks intent, not just diffs.",
    count: 2,
    cmds: ["prove", "qe-semantic-reviewer"],
  },
  {
    id: "data",
    name: "data & ML",
    hue: "layer",
    blurb: "ETL, data-quality, ontology, and ML workflows under the same evidence discipline.",
    count: 2,
    cmds: ["data", "data-engineer"],
  },
  {
    id: "persona",
    name: "personas",
    hue: "creation",
    blurb: "Run any task under a named behavioral profile — a reusable review cast on demand.",
    count: 2,
    cmds: ["persona", "persona-agent"],
  },
  {
    id: "search",
    name: "code intelligence",
    hue: "layer",
    blurb: "Impact & lineage over the real graph — the injected edges grep and a static call-graph can’t see.",
    count: 2,
    cmds: ["blast-radius", "lineage", "codebase-narrator"],
  },
  {
    id: "work-shapes",
    name: "work-shapes",
    hue: "creation",
    blurb: "Ten shapes read off each prompt — a typo to a cutover; deliberate challenges the ask first.",
    count: 2,
    cmds: ["triage", "build", "migrate", "review", "deliberate"],
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

/* ── The shelf: the opt-in wicked-* peers garden integrates with ───────────
   HONEST: every peer here is an opt-in layer — the kit works without any of
   them. The evidence backend the gate re-derives against (wicked-vault) rides
   inside wicked-testing; it is NOT a separate install. The gate/resolve engine
   (loom) is ABSORBED in-package as of v12.27.0 — also NOT a peer you install. */
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
    id: "testing",
    name: "wicked-testing",
    tier: "opt-in",
    hue: "layer",
    gives: "A full QE team for coding agents — runs the tests and records the evidence the gate re-derives against, with the runner kept separate from the judge so a verdict is re-derived, not trusted.",
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
  domains: DOMAINS.length,   // 12
  skills: 94,                // real SKILL.md count under skills/**
  forkSkills: 34,            // context:fork worker skills (skills/<domain>-<role>/)
  workShapes: 10,
};
