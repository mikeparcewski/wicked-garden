/* ============================================================================
   wicked-garden — capability-plane site content (single source of truth)
   Positioning: the CAPABILITY plane of the wicked platform — THE catalog of
   what agents act through. The toolkit for what a coding agent can't do alone.
   The soul: "done is re-derived from evidence, never asserted."
   All claims code-grounded against the wicked-garden repo (skills/**,
   .claude-plugin/plugin.json v12.29.1): 141 SKILL.md across 14 domain groups,
   40 qe-* specialist fork skills + the 3-agent acceptance pipeline (absorbed
   from the retired wicked-testing plugin in Phase 6b/6c), the estate-backed
   mem + search + patch stack, and the open {vendor}-{domain}-{role} naming
   contract. Honest status only — MIT, local-first.
============================================================================ */

export type Hue = "gate" | "floor" | "layer" | "solo" | "creation" | "workflow" | "qe";

/** The colour a hue resolves to (CSS var). Signal-yellow (gate) is reserved
    for verdict stamps + the primary CTA — never a tool tint. The qe hue is
    the family's CAPABILITY plane green (wicked-web tokens.css). */
export const HUE_VAR: Record<Hue, string> = {
  gate: "--c-gate",
  floor: "--c-floor",
  layer: "--c-layer",
  solo: "--c-solo",
  creation: "--c-creation",
  workflow: "--c-workflow",
  qe: "--c-qe",
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
    fill: "Sees the injected edges grep can’t — event→consumer, command→agent, agent→capability — over wicked-estate’s code graph, so impact analysis is real, not a text match.",
    cmd: "wicked-garden-search",
    cmdLabel: "garden skill · blast-radius",
  },
  {
    id: "patch",
    name: "patch",
    kind: "graph refactor",
    hue: "workflow",
    gap: "refactors on a hope and a prayer",
    fill: "Renames and moves symbols across every file as one graph operation on wicked-estate’s cross-language graph — not find-and-replace roulette.",
    cmd: "wicked-garden-engineering",
    cmdLabel: "garden skill · patch / rename",
  },
  {
    id: "council",
    name: "council",
    kind: "multi-model panel",
    hue: "solo",
    gap: "asks itself for a second opinion",
    fill: "Convenes a real panel of independent external models (Antigravity · Codex · …) — a second opinion that isn’t the model grading itself.",
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
    id: "mem",
    name: "mem",
    kind: "estate-backed memory",
    hue: "solo",
    gap: "forgets everything when the session ends",
    fill: "Cross-session memory + knowledge on wicked-estate — store decisions, ingest documents (vision-parsed PDFs included), and get cited answers back from the record.",
    cmd: "wicked-garden-mem",
    cmdLabel: "garden skill · store / recall / answer",
  },
];

/* ── The wider surface — the 14 domains the toolbox samples from ─────────────
   Every chip below is a real skill or routed action in the repo (skills/<dir>/).
   Counts are honest: 141 SKILL.md under skills/** folded into these 14 domain
   groups (per-domain routers, routed actions, and fork workers), 10 work-shapes
   — verified against skills/** at v12.29.1. */
export interface Domain {
  id: string;
  name: string;
  hue: Hue;
  blurb: string;
  count: number;      // real SKILL.md count under skills/** for this domain group
  cmds: string[];     // representative skills / routed actions (not exhaustive)
}

export const DOMAINS: Domain[] = [
  {
    id: "qe",
    name: "quality engineering",
    hue: "qe",
    blurb: "The absorbed QE fleet — 40 specialists on five surfaces, the 3-agent acceptance pipeline, and the prove gate. See the wall below.",
    count: 42,
    cmds: ["accept", "plan", "author", "execute", "review", "insight", "prove"],
  },
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
    blurb: "Graph-driven change — rename & patch across files on estate's graph, debug from a trace, architecture, docs.",
    count: 15,
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
    blurb: "Pull-model context assembly on the estate-backed stack — briefing, intent, propose-skills, grounded in the repo.",
    count: 7,
    cmds: ["discovery", "intent", "propose-skills", "classify", "ground"],
  },
  {
    id: "domain",
    name: "domain modeling",
    hue: "creation",
    blurb: "Extract the domain from the codebase — testable business rules with confidence + provenance, on estate's graph.",
    count: 4,
    cmds: ["domain", "domain-extractor", "domain-coverage", "domain-modeler"],
  },
  {
    id: "mem",
    name: "memory & knowledge",
    hue: "solo",
    blurb: "Estate-backed memory — store / recall / cited answers; document ingest (binary docs via vision); session capture.",
    count: 3,
    cmds: ["store", "recall", "answer", "ingest", "capture"],
  },
  {
    id: "jam",
    name: "multi-model",
    hue: "solo",
    blurb: "A second opinion that isn’t self-grading — an independent external-model panel and facilitator.",
    count: 3,
    cmds: ["council", "brainstorm", "multi-model"],
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
    blurb: "Impact & lineage over estate's real graph — the injected edges grep and a static call-graph can’t see.",
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

/* ============================================================================
   THE QE DOMAIN — absorbed from the retired wicked-testing plugin (Phase 6b/6c).
   The wall story now lives here: the agent that runs the tests is never the
   one that grades them. All data below is grounded against skills/qe*:
   - 40 qe-* specialist fork skills, each `context: fork`
   - the 3-agent acceptance pipeline with per-role `allowed-tools` boundaries
   - evidence lands in .wicked-qe/evidence/<run-id>/
============================================================================ */

export type Surface = "plan" | "authoring" | "execution" | "review" | "insight";

export interface QeSurface {
  key: Surface;
  line: string;
}

/** The five orchestrator surfaces the specialists route under (qe router actions). */
export const QE_SURFACES: QeSurface[] = [
  { key: "plan", line: "Shift-left strategy — strategist, risk, testability, AC-quality." },
  { key: "authoring", line: "Author scenarios and generate test code in your framework." },
  { key: "execution", line: "Run scenarios and capture evidence. No judgment." },
  { key: "review", line: "Independent verdict from cold evidence. Gap Report per criterion." },
  { key: "insight", line: "Domain health and history, answered by a fixed-SQL oracle." },
];

/** The 40 qe-* specialist fork skills, by surface — verified against skills/qe-*. */
export const QE_SPECIALISTS: { n: string; s: Surface }[] = [
  // plan
  { n: "qe-test-strategist", s: "plan" },
  { n: "qe-risk-assessor", s: "plan" },
  { n: "qe-testability-reviewer", s: "plan" },
  { n: "qe-requirements-quality-analyst", s: "plan" },
  { n: "qe-code-analyzer", s: "plan" },
  { n: "qe-coverage-archaeologist", s: "plan" },
  { n: "qe-test-impact-analyzer", s: "plan" },
  // authoring
  { n: "qe-acceptance-test-writer", s: "authoring" },
  { n: "qe-test-designer", s: "authoring" },
  { n: "qe-test-automation-engineer", s: "authoring" },
  { n: "qe-contract-testing-engineer", s: "authoring" },
  { n: "qe-ui-component-test-engineer", s: "authoring" },
  { n: "qe-integration-test-engineer", s: "authoring" },
  { n: "qe-e2e-orchestrator", s: "authoring" },
  { n: "qe-fuzz-property-engineer", s: "authoring" },
  { n: "qe-test-data-manager", s: "authoring" },
  { n: "qe-incident-to-scenario-synthesizer", s: "authoring" },
  // execution
  { n: "qe-acceptance-test-executor", s: "execution" },
  { n: "qe-scenario-executor", s: "execution" },
  { n: "qe-load-performance-engineer", s: "execution" },
  { n: "qe-chaos-test-engineer", s: "execution" },
  { n: "qe-security-test-engineer", s: "execution" },
  { n: "qe-a11y-test-engineer", s: "execution" },
  { n: "qe-mutation-test-engineer", s: "execution" },
  { n: "qe-ai-feature-test-engineer", s: "execution" },
  { n: "qe-iac-test-engineer", s: "execution" },
  { n: "qe-localization-test-engineer", s: "execution" },
  { n: "qe-observability-test-engineer", s: "execution" },
  { n: "qe-data-quality-tester", s: "execution" },
  { n: "qe-visual-regression-engineer", s: "execution" },
  { n: "qe-exploratory-tester", s: "execution" },
  // review
  { n: "qe-acceptance-test-reviewer", s: "review" },
  { n: "qe-semantic-reviewer", s: "review" },
  { n: "qe-test-code-quality-auditor", s: "review" },
  { n: "qe-snapshot-hygiene-auditor", s: "review" },
  { n: "qe-flaky-test-hunter", s: "review" },
  { n: "qe-release-readiness-engineer", s: "review" },
  // insight
  { n: "qe-test-oracle", s: "insight" },
  { n: "qe-production-quality-engineer", s: "insight" },
  { n: "qe-compliance-test-engineer", s: "insight" },
];

/** The 3-agent acceptance pipeline — per-role tool boundaries taken from each
    skill's `allowed-tools` frontmatter (skills/qe-acceptance-test-*). */
export interface AcceptanceRole {
  id: "writer" | "executor" | "reviewer";
  step: string;
  name: string;
  tools: string[];
  line: string;
  lit: string;        // the isolation copy shown when this role is lit
}

export const ACCEPTANCE_ROLES: AcceptanceRole[] = [
  {
    id: "writer",
    step: "step 1 · authors",
    name: "Writer",
    tools: ["Read", "Grep", "Glob", "Skill"],
    line: "Turns the scenario into an evidence-gated plan — every step declares its expected evidence and an assertion. Can’t execute.",
    lit: "The writer designs the exam but never sits it — no Bash, no Write. It can’t run a single test it authors.",
  },
  {
    id: "executor",
    step: "step 2 · runs",
    name: "Executor",
    tools: ["Read", "Write", "Bash"],
    line: "Follows the plan mechanically. Captures stdout, exit codes, and artifacts. Makes no judgment.",
    lit: "The executor runs everything and judges nothing — it records what happened and stops. PASS isn’t in its vocabulary.",
  },
  {
    id: "reviewer",
    step: "step 3 · judges",
    name: "Reviewer",
    tools: ["Read"],
    line: "Reads the evidence files and nothing else. Never sees how they were produced. One tool — Read. Can’t execute.",
    lit: "The reviewer never sees who did the work — cold evidence files only, in a forked context, with a single tool: Read.",
  },
];

/** Evidence that crosses the wall vs signals bounced at it. */
export const WALL_CROSSES = ["manifest.json", "evidence.json", "step-N.json", "context.md"];
export const WALL_BLOCKED = ["executor context", "chain-of-thought", "raw stdout", "prior verdicts"];

/* ── The shelf: the opt-in wicked-* peers garden composes with ─────────────
   HONEST: the kit works without any of them. wicked-estate is the system of
   record the mem/search/patch/domain stack reads and writes; wicked-vault is
   the evidence backend the gate re-derives against (npm, installed directly);
   bus and interactive are optional layers. The gate/resolve engine (loom) and
   the QE pipeline both ship IN-PACKAGE — not peers you install. */
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
    id: "estate",
    name: "wicked-estate",
    tier: "opt-in",
    hue: "layer",
    gives: "The system of record — a 75-language code graph, memory, and knowledge in one MCP binary. mem, search, patch, and domain all run on it.",
    cmd: "github.com/mikeparcewski/wicked-estate",
    cmdLabel: "the foundation plane",
  },
  {
    id: "vault",
    name: "wicked-vault",
    tier: "opt-in",
    hue: "floor",
    gives: "The evidence backend the gate re-derives against — hash-chained records, re-run verifiers, independent attestation.",
    cmd: "npm i wicked-vault",
    cmdLabel: "evidence backend",
  },
  {
    id: "bus",
    name: "wicked-bus",
    tier: "opt-in",
    hue: "layer",
    gives: "A local-first SQLite event bus — the audit trail of what every tool did. At-least-once delivery, no server, no infra.",
    cmd: "npm i -g wicked-bus && npx wicked-bus-install",
    cmdLabel: "opt-in layer",
  },
  {
    id: "interactive",
    name: "wicked-interactive",
    tier: "opt-in",
    hue: "creation",
    gives: "The foundation's document engine — storage, version lineage, HTML / PDF / PPTX / video rendering. Crew spawns and proxies it; you depend on it, you don't visit it.",
    cmd: "claude plugins marketplace add mikeparcewski/wicked-interactive && claude plugins install wicked-interactive",
    cmdLabel: "document engine",
  },
];

/* ── The extension pitch: ship your own domain pack ─────────────────────────
   Grounded in the repo's naming contract (kebab-case, ≤64 chars; one
   user-invocable router per domain; {vendor}-{domain}-{role} fork workers with
   `context: fork`) and the prove compiler (`prove compile <repo>` stamps a
   self-contained vault-backed gate into ANY repo — runs with no garden
   installed). */
export const PACK_SCAFFOLD = [
  { dir: "acme-fintech/", note: "your domain router · user-invocable" },
  { dir: "acme-fintech-risk-modeler/", note: "fork worker · context: fork" },
  { dir: "acme-fintech-auditor/", note: "fork worker · evaluator ≠ creator" },
];

export const G = {
  version: "v12.29.1",
  ownTools: TOOLS.length,
  peers: PEERS.length,
  domains: DOMAINS.length,   // 14
  skills: 141,               // real SKILL.md count under skills/**
  qeSpecialists: QE_SPECIALISTS.length, // 40
  workShapes: 10,
};
