/* ============================================================================
   wicked-garden — capability-plane site content (single source of truth)
   Positioning: the CAPABILITY plane of the wicked platform — THE catalog of
   what agents act through. The toolkit for what a coding agent can't do alone.
   The soul: "done is re-derived from evidence, never asserted."
   All claims code-grounded against the wicked-garden repo (skills/**,
   .claude-plugin/plugin.json): the SKILL.md count is counted at build time (G.skills), grouped into the
   catalog's skill families; 40 qe-* specialist skills + the 3-agent acceptance pipeline (absorbed
   from the retired wicked-testing plugin in Phase 6b/6c), the estate-backed // historical
   mem + search + patch stack, and the open {vendor}-{domain}-{role} naming
   contract. Honest status only — MIT, local-first.
============================================================================ */

export type Hue = "gate" | "floor" | "layer" | "solo" | "creation" | "workflow" | "qe";

/** The colour a hue resolves to (CSS var; site.css maps each onto a plane or
    status hue of the design package, never signal yellow). The qe hue is the
    family's capability green (wicked-web tokens.css). */
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
export type CheckId = "vault" | "verifier" | "hash" | "attest";

/** The gate's checks in the order it runs them (ProveGate derive(): the vault first, so a missing
    backend fails closed before anything else is read). */
export const CHECK_ORDER: { id: CheckId; short: string }[] = [
  { id: "vault", short: "vault" },
  { id: "verifier", short: "verifier" },
  { id: "hash", short: "hash" },
  { id: "attest", short: "attestation" },
];

export interface Claim {
  archetype: string;
  claim: string;
  verdict: "REJECTED" | "PROVED" | "FAILS CLOSED";
  reason: string;
  /** the check that fails (none for a re-derived claim) */
  fails?: CheckId;
}

export const CLAIMS: Claim[] = [
  {
    archetype: "build",
    claim: "the retry change: all acceptance tests pass",
    verdict: "REJECTED",
    reason: "re-ran the verifier — two never executed",
    fails: "verifier",
  },
  {
    archetype: "review",
    claim: "reviewed — safe to merge",
    verdict: "PROVED",
    reason: "independent evaluator agreed · evaluator ≠ author",
  },
  {
    archetype: "migrate",
    claim: "backfill is complete",
    verdict: "REJECTED",
    reason: "recorded evidence hash ≠ the claim",
    fails: "hash",
  },
  {
    archetype: "build",
    claim: "tests pass",
    verdict: "FAILS CLOSED",
    reason: "evidence backend unreachable — never a vacuous green",
    fails: "vault",
  },
];

/* ── Memory, the one garden tool the page reads from data (the memory frame) ──
   `cmd` is the README-style skill call you paste into your agent. */
export interface Tool {
  id: string;
  fill: string;       // the frame's lead
  cmd: string;
}

export const TOOLS: Tool[] = [
  {
    id: "mem",
    fill: "Cross-session memory and knowledge on wicked-estate: your agent stores decisions, ingests documents (PDFs included) and gets cited answers back. In a wicked-crew job an agent can only propose: each memory waits for your approval, with its source recorded.",
    cmd: "/wicked-garden-mem recall \"why cap retries at 1?\"",
  },
];

/* ── The wider surface — the skill families the catalog groups its skills into ─
   Every chip below is a real skill or routed action in the repo (skills/<dir>/).
   The total (G.skills) is counted at build time from skills/**. Per-domain counts
   are not shown: they were typed by hand and drifted (they summed to 142 against
   139 SKILL.md files). Each domain names the skill you invoke to try it. */
export interface Domain {
  id: string;
  name: string;
  hue: Hue;
  blurb: string;
  cmds: string[];     // representative skills / routed actions (not exhaustive)
  try: string;        // the skill you invoke to try the domain (a real skills/<dir>/SKILL.md name)
}

export const DOMAINS: Domain[] = [
  {
    id: "qe",
    name: "quality engineering",
    hue: "qe",
    blurb: "The QE fleet — 40 specialists under five router actions, the 3-agent acceptance pipeline, and the prove gate. See the wall.",
    cmds: ["accept", "plan", "author", "execute", "review", "insight", "prove"],
    try: "wicked-garden-qe",
  },
  {
    id: "product",
    name: "product & UX",
    hue: "creation",
    blurb: "Vague ask → SMART acceptance criteria, laid out as a traceable requirements graph of small markdown files; plus UX & a11y review, mockups, visual direction, user-signal synthesis, and draft for document deliverables (contrast, page budget, cited claims).",
    cmds: ["requirements-analysis", "acceptance-criteria", "ux-review", "accessibility", "mockup", "strategy", "draft"],
    try: "wicked-garden-product",
  },
  {
    id: "platform",
    name: "platform & ops",
    hue: "floor",
    blurb: "The rubric on demand — security, compliance, incident, infra, distributed traces, CI.",
    cmds: ["audit", "compliance", "incident", "infra", "observability", "github-actions"],
    try: "wicked-garden-platform",
  },
  {
    id: "engineering",
    name: "engineering",
    hue: "workflow",
    blurb: "Graph-driven change — rename & patch across files on estate's graph, debug from a trace, architecture, docs.",
    cmds: ["architecture", "debugging", "patch", "system-design", "integration", "large-scale-migration"],
    try: "wicked-garden-engineering",
  },
  {
    id: "agentic",
    name: "agentic review",
    hue: "workflow",
    blurb: "Review the agentic codebase itself — topology, framework detection, trust & safety.",
    cmds: ["agentic-patterns", "context-engineering", "frameworks", "review-methodology", "trust-and-safety"],
    try: "wicked-garden-agentic",
  },
  {
    id: "crew",
    name: "orchestration",
    hue: "layer",
    blurb: "Orchestration — the worker discipline every agent in a wicked-crew job follows (creator / evaluator / neutral); swarm, worktrees, workflow runners.",
    cmds: ["governed-worker", "swarm", "worktrees", "workflow"],
    try: "wicked-garden-swarm",
  },
  {
    id: "ground",
    name: "grounding",
    hue: "solo",
    blurb: "Check before acting: when the agent is unsure, ground pulls related memories, knowledge and recent events from wicked-estate and the bus, ranked by relevance.",
    cmds: ["ground"],
    try: "wicked-garden-ground",
  },
  {
    id: "domain",
    name: "domain modeling",
    hue: "creation",
    blurb: "Mine the code's real requirements — testable business rules with confidence + provenance on estate's graph, mapped page by page to the minimum. A placeholder is shown, never counted.",
    cmds: ["domain", "domain-extractor", "domain-coverage", "domain-modeler"],
    try: "wicked-garden-domain",
  },
  {
    id: "mem",
    name: "memory & knowledge",
    hue: "solo",
    blurb: "Estate-backed memory: store / recall / cited answers, ingest and session capture. In a wicked-crew chat or job, answer can also read a connected data source and cite the read. In a job an agent can only propose, and each memory waits for your approval; repo-learn derives memories, policies and your working style as proposals.",
    cmds: ["store", "recall", "answer", "ingest", "capture", "repo-learn"],
    try: "wicked-garden-mem",
  },
  {
    id: "jam",
    name: "review panel",
    hue: "solo",
    blurb: "A review panel of the other agents you have installed weighs in on a disputed decision; a same-family fallback is labelled, and without a quorum it gives no verdict. Brainstorms run as a focus group of personas.",
    cmds: ["council", "brainstorm"],
    try: "wicked-garden-jam",
  },
  {
    id: "data",
    name: "data, apps & ML",
    hue: "layer",
    blurb: "ETL, data-quality, ontology, and ML workflows under the same evidence discipline. shapes proposes what a connected source's tables join and which code describes them, for you to approve (structure only, never a row); wicked-garden-apps builds and reviews the apps you make by chat in studio.",
    cmds: ["data", "data-engineer", "shapes", "apps"],
    try: "wicked-garden-data",
  },
  {
    id: "persona",
    name: "personas",
    hue: "creation",
    blurb: "Run any task under a named behavioral profile — a reusable review cast on demand.",
    cmds: ["persona"],
    try: "wicked-garden-persona",
  },
  {
    id: "search",
    name: "code intelligence",
    hue: "layer",
    blurb: "Impact & lineage over estate's real graph — the injected edges grep and a static call-graph can’t see.",
    cmds: ["blast-radius", "lineage", "codebase-narrator"],
    try: "wicked-garden-search",
  },
  {
    id: "work-shapes",
    name: "work-shapes",
    hue: "creation",
    blurb: `${__WICKED_GARDEN_WORK_SHAPES__} shapes read off each prompt — a typo to a cutover; deliberate challenges the ask first.`,
    cmds: ["triage", "build", "migrate", "review", "deliberate"],
    try: "wicked-garden-archetype",
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
   THE QE DOMAIN — absorbed from the retired wicked-testing plugin (Phase 6b/6c). // historical
   The wall story now lives here: the agent that runs the tests is never the
   one that grades them. All data below is grounded against skills/qe*:
   - 40 qe-* specialist skills (ls skills | grep -c '^qe-'), grouped under the
     qe router's five actions
   - the 3-agent acceptance pipeline: the reviewer judges from evidence paths only,
     as a separate worker; no separate worker = FAIL inconclusive (skills/qe §accept)
   - evidence lands in .wicked-qe/evidence/<run-id>/
============================================================================ */

export type Surface = "plan" | "author" | "execute" | "review" | "insight";

export interface QeSurface {
  key: Surface;
  line: string;
}

/** The five qe router actions the specialists are grouped under (skills/qe/SKILL.md ## plan … ## insight). */
export const QE_SURFACES: QeSurface[] = [
  { key: "plan", line: "Shift-left strategy — strategist, risk, testability, AC-quality." },
  { key: "author", line: "Author scenarios and generate test code in your framework." },
  { key: "execute", line: "Run scenarios and capture evidence. No judgment." },
  { key: "review", line: "Independent verdict from cold evidence. Gap Report per criterion." },
  { key: "insight", line: "Domain health and history, answered by a fixed-SQL oracle." },
];

/** The 40 qe-* specialist skills, by router action — verified against skills/qe-*. */
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
  { n: "qe-acceptance-test-writer", s: "author" },
  { n: "qe-test-designer", s: "author" },
  { n: "qe-test-automation-engineer", s: "author" },
  { n: "qe-contract-testing-engineer", s: "author" },
  { n: "qe-ui-component-test-engineer", s: "author" },
  { n: "qe-integration-test-engineer", s: "author" },
  { n: "qe-e2e-orchestrator", s: "author" },
  { n: "qe-fuzz-property-engineer", s: "author" },
  { n: "qe-test-data-manager", s: "author" },
  { n: "qe-incident-to-scenario-synthesizer", s: "author" },
  // execution
  { n: "qe-acceptance-test-executor", s: "execute" },
  { n: "qe-scenario-executor", s: "execute" },
  { n: "qe-load-performance-engineer", s: "execute" },
  { n: "qe-chaos-test-engineer", s: "execute" },
  { n: "qe-security-test-engineer", s: "execute" },
  { n: "qe-a11y-test-engineer", s: "execute" },
  { n: "qe-mutation-test-engineer", s: "execute" },
  { n: "qe-ai-feature-test-engineer", s: "execute" },
  { n: "qe-iac-test-engineer", s: "execute" },
  { n: "qe-localization-test-engineer", s: "execute" },
  { n: "qe-observability-test-engineer", s: "execute" },
  { n: "qe-data-quality-tester", s: "execute" },
  { n: "qe-visual-regression-engineer", s: "execute" },
  { n: "qe-exploratory-tester", s: "execute" },
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

/* N9, measured from source: the fleet above names exactly the skills/qe-* dirs (astro.config.mjs lists them).
   The build's server render runs this, so adding or removing a qe-* skill without this list fails the build;
   the browser bundle never carries the dir list (Vite drops the branch). */
if (import.meta.env.SSR) {
  const dirs = __WICKED_GARDEN_QE_DIRS__;
  const listed = QE_SPECIALISTS.map((x) => x.n).sort();
  const missing = dirs.filter((d) => !listed.includes(d));
  const extra = listed.filter((n) => !dirs.includes(n));
  if (missing.length || extra.length || listed.length !== dirs.length) {
    throw new Error(
      `QE_SPECIALISTS (${listed.length}) must name exactly the ${dirs.length} skills/qe-* dirs. ` +
        `Not listed: ${missing.join(", ") || "none"}. Listed without a dir: ${extra.join(", ") || "none"}.`,
    );
  }
}

/** The 3-agent acceptance pipeline — what each role is handed (skills/qe §accept: the writer plans, the
    executor captures, the reviewer judges from evidence paths only, as a separate worker). */
export interface AcceptanceRole {
  id: "writer" | "executor" | "reviewer";
  step: string;
  name: string;
  gets: string;       // what the role's brief carries
  line: string;
  lit: string;        // the isolation copy shown when this role is lit
}

export const ACCEPTANCE_ROLES: AcceptanceRole[] = [
  {
    id: "writer",
    step: "step 1 · authors",
    name: "Writer",
    gets: "the scenario",
    line: "Turns the scenario into an evidence-gated plan — every step declares its expected evidence and an assertion.",
    lit: "The writer designs the exam but never sits it: it writes the plan and stops.",
  },
  {
    id: "executor",
    step: "step 2 · runs",
    name: "Executor",
    gets: "the plan",
    line: "Follows the plan mechanically. Captures stdout, exit codes, and artifacts. Makes no judgment.",
    lit: "The executor runs everything and judges nothing — it records what happened and stops. PASS isn’t in its vocabulary.",
  },
  {
    id: "reviewer",
    step: "step 3 · judges",
    name: "Reviewer",
    gets: "evidence paths only",
    line: "Reads the evidence files and nothing else. Never sees how they were produced.",
    lit: "The reviewer never sees who did the work: a separate worker, handed evidence file paths and nothing else.",
  },
];

/** Evidence that crosses the wall vs signals bounced at it. */
export const WALL_CROSSES = ["manifest.json", "evidence.json", "step-N.json", "context.md"];
export const WALL_BLOCKED = ["executor context", "chain-of-thought", "executor’s notes", "prior verdicts"];

/* ── The shelf: the wicked-* peers garden composes with ─────────────────────
   wicked-vault is the one required peer: the proof gate re-derives against it and
   fails closed without it (README "One required peer, the rest opt-in";
   scripts/qe/vault_gate.py), and the family installer adds it with garden.
   wicked-estate is the layer the mem/search/patch/domain stack reads and writes;
   bus and interactive are optional. The gate/resolve engine (loom) and the QE
   pipeline both ship IN-PACKAGE — not peers you install. */
export interface Peer {
  id: string;
  name: string;
  tier: "required" | "opt-in";
  hue: Hue;
  cmdLabel: string;
}

export const PEERS: Peer[] = [
  {
    id: "estate",
    name: "wicked-estate",
    tier: "opt-in",
    hue: "layer",
    cmdLabel: "code graph + memory",
  },
  {
    id: "vault",
    name: "wicked-vault",
    tier: "required",
    hue: "floor",
    cmdLabel: "required by the gate",
  },
  {
    id: "bus",
    name: "wicked-bus",
    tier: "opt-in",
    hue: "layer",
    cmdLabel: "optional",
  },
  {
    id: "interactive",
    name: "wicked-interactive",
    tier: "opt-in",
    hue: "creation",
    cmdLabel: "optional",
  },
];

/* ── The extension pitch: ship your own domain pack ─────────────────────────
   Grounded in README "Build on it" and docs/extending.md: a pack is a directory
   with a `wicked-pack.json` manifest and a skills/ tree holding one
   `{vendor}-{domain}` router and `{vendor}-{domain}-{role}` workers; kebab-case
   SKILL.md names, ≤64 chars; a worker declares `metadata.role: worker`
   (scripts/pack/check.py PK016). `npx wicked-garden pack check <dir>` is the
   shipped conformance gate. The pack names are examples. */
function pack(dom: string, worker: string, auditor: string) {
  return [
    { dir: "wicked-pack.json", note: "the manifest" },
    { dir: `skills/acme-${dom}/`, note: "router · user-invocable" },
    { dir: `skills/acme-${dom}-${worker}/`, note: "worker" },
    { dir: `skills/acme-${dom}-${auditor}/`, note: "worker · evaluator ≠ creator" },
  ];
}

/** Example packs for the scaffold picker (names are examples; the shape is the contract). */
export const PACKS: { id: string; label: string; dir: string; rows: { dir: string; note: string }[] }[] = [
  { id: "fintech", label: "fintech-risk", dir: "acme-fintech-pack", rows: pack("fintech", "modeler", "auditor") },
  { id: "games", label: "games-QA", dir: "acme-gamesqa-pack", rows: pack("gamesqa", "tester", "reviewer") },
  { id: "compliance", label: "compliance", dir: "acme-compliance-pack", rows: pack("compliance", "mapper", "auditor") },
];

/* ── What's new in the release the words describe (garden 12.66.0; DES-CATALOG-002 rev 8 CS3, CS5, CS7) ──
   Each: a bold lead, an optional command (code), then the rest; spaces live in the
   strings, so no build step can fuse a word to the next inline tag. The respond and
   rework item links to its domain in the catalog (draft is a product command). An item
   is cut, never softened, if it did not ship. */
export const NEW_RELEASE = "12.66";
export const NEW_IN: { b: string; code?: string; rest: string; href?: string }[] = [
  { b: "Reports with sources:", code: "wicked-garden-learn", rest: " has a report mode for wicked-crew’s six report jobs, from research to due diligence: every claim is numbered, cites its source and is re-checked there." },
  { b: "Respond and rework:", code: "draft", rest: " answers an RFP, RFI or questionnaire from your materials, item by item, or reworks a document: condense, re-audience, generalize, convert or refresh.", href: "#dom-product" },
  { b: "Phase plugins:", code: "editor-scaffold", rest: " also scaffolds a run plugin: a section in every studio job’s details, drawn from its events, reading only the topics you approve." },
];

export const G = {
  // Injected at build time from .claude-plugin/plugin.json via
  // astro.config.mjs (vite define) — never hardcode a version here. (DT-7)
  version: `v${__WICKED_GARDEN_VERSION__}`,
  // no family count is published: the tab list is a hand-picked grouping, not a measured number (N9)
  skills: __WICKED_GARDEN_SKILLS__, // real SKILL.md count under skills/**, counted at build time
  qeSpecialists: QE_SPECIALISTS.length, // the skills/qe-* dirs: the check after QE_SPECIALISTS fails the build on drift
  workShapes: __WICKED_GARDEN_WORK_SHAPES__, // the archetypes in .claude-plugin/archetypes.json, counted at build time
};
