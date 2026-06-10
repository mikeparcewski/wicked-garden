export type RoleId = "gate" | "floor" | "layer" | "solo";

export interface Role {
  id: RoleId;
  label: string;
  tag: string;
  blurb: string;
  colorVar: string; // CSS custom property name
}

export interface Project {
  id: string; // full package id, e.g. "wicked-bus"
  short: string; // display name, e.g. "bus"
  role: RoleId;
  kicker: string; // mono kicker, e.g. "agent event bus"
  tagline: string; // short hook
  outcome: string; // the result an engineer gets — the headline of the card
  blurb: string; // one or two sentences of substance
  points: string[]; // capability bullets
  uses: string[]; // use-case bullets ("use it for")
  install: string; // primary install / invoke command
  repo: string;
  badges: string[];
  featured?: boolean;
}

/** One stop on the garden tour. `tools` are project ids presented at the stop. */
export interface TourStop {
  stop: number; // 1-based
  kicker: string; // e.g. "stop 03 / 07 — the proving bed"
  headline: { pre: string; mark: string }; // display headline; `mark` gets the marker swipe
  body: string; // stop-level narrative
  unlock: string; // capability caption once planted, e.g. "now it remembers"
  plant: "locked" | "optin"; // locked = pre-planted, can't unplant
  tools: string[];
}

export const ROLES: Role[] = [
  {
    id: "gate",
    label: "The gate",
    tag: "start here",
    blurb: "One install that curates the rest — reads the shape of your work and applies exactly that much rigor.",
    colorVar: "--c-gate",
  },
  {
    id: "floor",
    label: "The floor",
    tag: "required peers",
    blurb: "The two peers the evidence gate stands on. Garden blocks without them — this floor is the point.",
    colorVar: "--c-floor",
  },
  {
    id: "layer",
    label: "The layers",
    tag: "opt-in",
    blurb: "Add what you want, skip the rest — honest QE, memory, repo playbooks, an audit trail. The kit works either way.",
    colorVar: "--c-layer",
  },
  {
    id: "solo",
    label: "Solo beds",
    tag: "standalone",
    blurb: "Same ethos, no garden required. Grab them on their own when the deck is due at 11pm.",
    colorVar: "--c-solo",
  },
];

const GH = "https://github.com/mikeparcewski";

export const PROJECTS: Project[] = [
  // ── The gate ───────────────────────────────────────────────────
  {
    id: "wicked-garden",
    short: "garden",
    role: "gate",
    kicker: "the curated toolkit",
    tagline: "Your agent plans and swarms. This is the rest.",
    outcome: "your agent's gaps, filled — with exactly the right rigor",
    blurb:
      "Your coding agent already plans and swarms. Garden fills what it can't do alone: it re-runs the proof behind every “done,” reads the shape of each task — triage, build, migrate, incident — and applies that much rigor. No more, no less.",
    points: [
      "9 work-shape archetypes route the right amount of rigor",
      "Evidence-gated phases fail closed — never a vacuous green",
      "The gate compiles into any repo and runs with nothing installed",
    ],
    uses: [
      "autonomous work that needs governing, not babysitting",
      "phase gates that fail closed instead of rubber-stamping",
      "a typo fix and a migration getting different rigor",
    ],
    install: "claude plugins marketplace add mikeparcewski/wicked-garden && claude plugins install wicked-garden",
    repo: `${GH}/wicked-garden`,
    badges: ["MIT", "Claude plugin"],
    featured: true,
  },

  // ── The floor ──────────────────────────────────────────────────
  {
    id: "wicked-vault",
    short: "vault",
    role: "floor",
    kicker: "evidence primitive",
    tagline: "Don't trust “done.” Re-derive it.",
    outcome: "you ship on evidence, not on an agent's word",
    blurb:
      "Records the evidence behind a claim with the criteria it must clear, then checks it on two tiers: integrity — deterministic, re-derivable, model-free — and judgment, from an independent evaluator that isn't the agent who did the work.",
    points: [
      "Integrity tier — recompute the hashes, re-run the verifier, CI-safe",
      "Judgment tier — independent judge ≠ worker, fail-closed",
      "Append-only, tamper-evident attestations — criteria frozen to evidence",
    ],
    uses: [
      "CI gates that re-verify instead of trusting a green badge",
      "audit-ready evidence trails behind every claim",
      "stopping agents from grading their own homework",
    ],
    install: "npx wicked-vault-install",
    repo: `${GH}/wicked-vault`,
    badges: ["MIT", "npm", "7 harnesses"],
    featured: true,
  },
  {
    id: "wicked-loom",
    short: "loom",
    role: "floor",
    kicker: "orchestration runtime",
    tagline: "The kit, wired right and gated on proof.",
    outcome: "the whole kit verified wired-right — and gated on re-derived proof",
    blurb:
      "Local-first orchestration for the wicked-* set. Compose resolves, version-checks, and installs every peer through an env → PATH → npx ladder; the conduct gate re-runs verifiers through the vault and fails closed.",
    points: [
      "doctor — every peer's health in a single call",
      "Resolution ladder respects where you installed each peer",
      "Fail-closed gate verdicts, with attestations",
    ],
    uses: [
      "one doctor call before a demo or a release",
      "installing and version-pinning the whole set at once",
      "re-running gate verifiers from CI",
    ],
    install: "npm i -g wicked-loom",
    repo: `${GH}/wicked-loom`,
    badges: ["MIT", "npm", "no server"],
  },

  // ── The layers ─────────────────────────────────────────────────
  {
    id: "wicked-testing",
    short: "testing",
    role: "layer",
    kicker: "QE pipeline",
    tagline: "Verdicts your agent can't fake.",
    outcome: "green means green — test verdicts you can trust",
    blurb:
      "A complete QE team for your AI CLI: a Writer → Executor → Reviewer pipeline with hard-enforced separation. The reviewer reads cold evidence and never sees the executor's context, so the agent can't grade its own homework.",
    points: [
      "41 specialist agents · 5 Tier-1 skills (mutation, chaos, flake, a11y…)",
      "Independent verdicts — reviewer never sees executor context",
      "SQLite ledger with a plain-English oracle",
    ],
    uses: [
      "acceptance runs the author can't influence",
      "flake hunts and mutation audits on suspicious suites",
      "asking your test history questions in plain English",
    ],
    install: "npx wicked-testing install",
    repo: `${GH}/wicked-testing`,
    badges: ["MIT", "npm", "6 CLIs"],
    featured: true,
  },
  {
    id: "wicked-brain",
    short: "brain",
    role: "layer",
    kicker: "agent memory",
    tagline: "Memory that survives the session.",
    outcome: "your agent picks up exactly where it left off",
    blurb:
      "Persistent, searchable knowledge built on plain markdown and SQLite full-text search — the LLM works as a research librarian over files you can read, diff, and git-commit. No vector DB, no embeddings, no infrastructure.",
    points: [
      "Full-text search + agent reasoning, not cosine distance",
      "Chunks → synthesized wiki — every claim traces back to a file",
      "Browser viewer included · works across 5 CLIs",
    ],
    uses: [
      "picking up tomorrow exactly where today ended",
      "onboarding an agent to a project's tribal knowledge",
      "memory you can open, diff, and git-commit",
    ],
    install: "npx wicked-brain",
    repo: `${GH}/wicked-brain`,
    badges: ["MIT", "npm", "local-first"],
    featured: true,
  },
  {
    id: "wicked-understanding",
    short: "understanding",
    role: "layer",
    kicker: "repo playbooks",
    tagline: "Give your agent the repo's “how.”",
    outcome: "your agent fixes the bug instead of re-learning the repo",
    blurb:
      "Memory tells your agent what your repo is. This hands it how to change it — repo-specific playbooks (fix-bug, add-feature, verify) generated from HEAD, with the exact files, the wiring step, and the gotcha that bites.",
    points: [
      "Playbooks read HEAD, so they track your code instead of rotting",
      "Diff-aware refresh — only what moved re-runs",
      "Cross-CLI via the skills standard",
    ],
    uses: [
      "fixing the bug without re-learning the repo",
      "playbooks that onboard agents — and new engineers",
      "keeping the “how” fresh as the code moves",
    ],
    install: "npx skills add mikeparcewski/wicked-understanding --all",
    repo: `${GH}/wicked-understanding`,
    badges: ["MIT", "cross-CLI"],
  },
  {
    id: "wicked-bus",
    short: "bus",
    role: "layer",
    kicker: "agent event bus",
    tagline: "The bus your tools talk over.",
    outcome: "your tools coordinate without integration glue",
    blurb:
      "Wire your tools together without building glue for every pair. Producers emit fire-and-forget; subscribers catch up at their own pace with at-least-once delivery. One SQLite file — no broker, no daemon, no ports.",
    points: [
      "Fire-and-forget — producers never block, degrade gracefully if absent",
      "At-least-once delivery with cursors that survive restarts",
      "One SQLite file. No server. No infrastructure.",
    ],
    uses: [
      "tools coordinating without point-to-point glue",
      "an audit trail of what every agent did",
      "local event-driven automation, zero infra",
    ],
    install: "npm i wicked-bus",
    repo: `${GH}/wicked-bus`,
    badges: ["MIT", "npm", "no server"],
  },

  // ── Solo beds ──────────────────────────────────────────────────
  {
    id: "wicked-interactive",
    short: "interactive",
    role: "solo",
    kicker: "live HTML builder",
    tagline: "Describe it out loud. Watch it build.",
    outcome: "a shareable page, deck, or demo — built while you describe it",
    blurb:
      "It's 11pm, the deck's due, and you haven't opened PowerPoint — good news, you don't have to. Say what you need, point at what's wrong, and watch it rebuild live. Every version is saved.",
    points: [
      "Point-and-describe live edits — no save / export / reopen loop",
      "Records a real demo deterministically — the agent writes the clicks",
      "Rewind or fork any version; nothing is ever lost",
    ],
    uses: [
      "the 11pm board deck",
      "launch pages and one-pagers on demand",
      "narrated demo videos of your live app",
    ],
    install: "claude plugins marketplace add mikeparcewski/wicked-interactive && claude plugins install wicked-interactive",
    repo: `${GH}/wicked-interactive`,
    badges: ["MIT", "Claude plugin"],
    featured: true,
  },
];

export const TOUR: TourStop[] = [
  {
    stop: 1,
    kicker: "stop 01 / 08 — the garden gate",
    headline: { pre: "every garden starts at the", mark: "gate" },
    body:
      "wicked-garden reads the shape of each task — a typo fix, a schema migration, a 2am incident — and applies exactly that much rigor, gating each phase on re-derived evidence. Install it once; it curates everything that follows.",
    unlock: "the garden itself",
    plant: "locked",
    tools: ["wicked-garden"],
  },
  {
    stop: 2,
    kicker: "stop 02 / 08 — the evidence bed",
    headline: { pre: "a floor that can't", mark: "lie" },
    body:
      "Every claim is recorded with the criteria it must clear, then re-derived instead of trusted — integrity checked deterministically, judgment rendered by an independent evaluator that isn't the agent who did the work. Garden blocks without it.",
    unlock: "the evidence floor — in place",
    plant: "locked",
    tools: ["wicked-vault"],
  },
  {
    stop: 3,
    kicker: "stop 03 / 08 — the trellis",
    headline: { pre: "every bed, wired", mark: "right" },
    body:
      "The orchestration runtime the set stands on: compose resolves, version-checks, and installs every peer, and the conduct gate re-runs verifiers through the vault — failing closed, never rubber-stamping. One doctor call tells you what's missing.",
    unlock: "the kit, wired right",
    plant: "locked",
    tools: ["wicked-loom"],
  },
  {
    stop: 4,
    kicker: "stop 04 / 08 — the proving bed",
    headline: { pre: "green finally means", mark: "green" },
    body:
      "A Writer → Executor → Reviewer pipeline with enforced separation — the reviewer reads cold evidence and never sees the executor's context. 41 specialist agents, one SQLite ledger, a plain-English oracle.",
    unlock: "green means green",
    plant: "optin",
    tools: ["wicked-testing"],
  },
  {
    stop: 5,
    kicker: "stop 05 / 08 — the memory bed",
    headline: { pre: "your agent finally", mark: "remembers" },
    body:
      "Persistent, searchable knowledge from plain markdown and SQLite full-text search. No vector DB, no embeddings — session 47 picks up exactly where session 1 left off, and you can read every byte.",
    unlock: "now it remembers",
    plant: "optin",
    tools: ["wicked-brain"],
  },
  {
    stop: 6,
    kicker: "stop 06 / 08 — the playbook bed",
    headline: { pre: "it knows how, not just", mark: "what" },
    body:
      "Repo-specific playbooks generated from HEAD — fix-bug, add-feature, verify — with the exact files, the wiring step, and the gotcha that bites. Your agent stops re-deriving the method every session.",
    unlock: "now it knows your repo",
    plant: "optin",
    tools: ["wicked-understanding"],
  },
  {
    stop: 7,
    kicker: "stop 07 / 08 — the irrigation",
    headline: { pre: "your tools finally", mark: "talk" },
    body:
      "A local-first event bus over one SQLite file — producers fire and forget, subscribers catch up at their own pace. No broker, no daemon, no ports; the whole garden coordinates without glue.",
    unlock: "now your tools talk",
    plant: "optin",
    tools: ["wicked-bus"],
  },
  {
    stop: 8,
    kicker: "stop 08 / 08 — the greenhouse",
    headline: { pre: "the 11pm deck,", mark: "handled" },
    body:
      "A solo bed — no garden required. Describe the deck, page, or demo out loud and watch it build live in your browser; point at what's wrong and say what to fix. Every version saved.",
    unlock: "for the 11pm deck",
    plant: "optin",
    tools: ["wicked-interactive"],
  },
];

/** Tool ids that are always in the kit (the gate + the floor). */
export const LOCKED_TOOLS: string[] = TOUR.filter((s) => s.plant === "locked").flatMap((s) => s.tools);

/** Canonical tray / script order. */
export const KIT_ORDER: string[] = TOUR.flatMap((s) => s.tools);

export const FEATURED = PROJECTS.filter((p) => p.featured);

export function roleOf(id: RoleId): Role {
  return ROLES.find((r) => r.id === id)!;
}

export function colorVarOf(id: RoleId): string {
  return ROLES.find((r) => r.id === id)?.colorVar ?? "--accent";
}

export const STATS = {
  projects: PROJECTS.length,
  accounts: 0,
  agents: 41,
  archetypes: 9,
  harnesses: 7,
};
