export type RoleId = "gate" | "layer" | "solo";

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
  kicker: string; // e.g. "stop 03 / 05 — the proving bed"
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
    tagline: "Your agent plans and swarms. These are the tools.",
    outcome: "the tools your agent can't build alone, in one plugin",
    blurb:
      "Your coding agent already plans and swarms. wicked-garden hands it the tools it can't build alone — re-derive “done” from evidence, see the injected edges grep misses, refactor across files as one graph operation, and convene a real multi-model panel.",
    points: [
      "prove — re-derives “done” from evidence, fails closed on a missing backend",
      "search — blast-radius, lineage, hotspots see injected edges grep can't",
      "patch — deterministic multi-file refactor as one graph operation",
      "council — a real multi-model second opinion, not self-review",
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
      "40 specialist skills · 8 Tier-1 workflow skills (5 orchestrator surfaces: plan, authoring, execution, review, insight)",
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
    badges: ["MIT", "npm", "5 CLIs"],
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
      "Reads PDF, DOCX, PPTX, XLSX natively — the LLM parses, no libraries",
      "Browser viewer included · works across 5 CLIs",
    ],
    uses: [
      "picking up tomorrow exactly where today ended",
      "onboarding an agent to a project's tribal knowledge",
      "recalling the decisions and gotchas behind the code",
      "memory you can open, diff, and git-commit",
    ],
    install: "npx wicked-brain",
    repo: `${GH}/wicked-brain`,
    badges: ["MIT", "npm", "local-first"],
    featured: true,
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
    kicker: "stop 01 / 05 — the toolkit",
    headline: { pre: "the tools your agent", mark: "can't build alone" },
    body:
      "wicked-garden hands your agent five tools it can't build alone — prove (re-derive “done” from evidence), injected-edge search, multi-file refactor as a graph operation, a real multi-model council, and the repo's own playbooks. Its gate/resolve engine ships in-package (scripts/loom/) — nothing extra to install. Install it once; it curates everything that follows.",
    unlock: "the garden itself",
    plant: "locked",
    tools: ["wicked-garden"],
  },
  {
    stop: 2,
    kicker: "stop 02 / 05 — the proving bed",
    headline: { pre: "green finally means", mark: "green" },
    body:
      "A Writer → Executor → Reviewer pipeline with enforced separation — the reviewer reads cold evidence and never sees the executor's context, re-deriving each verdict from evidence instead of trusting it. 40 specialist skills, one SQLite ledger, a plain-English oracle.",
    unlock: "green means green",
    plant: "optin",
    tools: ["wicked-testing"],
  },
  {
    stop: 3,
    kicker: "stop 03 / 05 — the memory bed",
    headline: { pre: "your agent finally", mark: "remembers" },
    body:
      "Persistent, searchable knowledge from plain markdown and SQLite full-text search. No vector DB, no embeddings — session 47 picks up exactly where session 1 left off, and you can read every byte. Every claim traces back to a file you can open, diff, and git-commit.",
    unlock: "now it remembers",
    plant: "optin",
    tools: ["wicked-brain"],
  },
  {
    stop: 4,
    kicker: "stop 04 / 05 — the irrigation",
    headline: { pre: "your tools finally", mark: "talk" },
    body:
      "A local-first event bus over one SQLite file — producers fire and forget, subscribers catch up at their own pace. No broker, no daemon, no ports; the whole garden coordinates without glue.",
    unlock: "now your tools talk",
    plant: "optin",
    tools: ["wicked-bus"],
  },
  {
    stop: 5,
    kicker: "stop 05 / 05 — the greenhouse",
    headline: { pre: "the 11pm deck,", mark: "handled" },
    body:
      "A solo bed — no garden required. Describe the deck, page, or demo out loud and watch it build live in your browser; point at what's wrong and say what to fix. Every version saved.",
    unlock: "for the 11pm deck",
    plant: "optin",
    tools: ["wicked-interactive"],
  },
];

/** Tool ids that are always in the kit (the gate). */
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
  archetypes: 10,
  harnesses: 7,
};
