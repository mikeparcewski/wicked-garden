import { useState } from "react";
import CopyChip from "./CopyChip";
import Reveal from "./Reveal";

/* ── Silhouette icons — clean single-color line marks, one per tool ──────────*/
const I = {
  prove: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 3l2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 15.9 7.2 18l.9-5.4L4.2 8.7l5.4-.8z" />
      <path d="M9.4 12.2l1.9 1.9 3.4-3.6" />
    </svg>
  ),
  search: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="7" cy="7" r="2.2" /><circle cx="17" cy="8" r="2.2" /><circle cx="12" cy="17" r="2.2" />
      <path d="M8.9 8.2l6.2.9M8.4 8.9l2.9 6.3M15.3 9.9l-2.6 5.4" />
      <path d="M18.5 9.6l3 3" />
    </svg>
  ),
  patch: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="4" y="3.5" width="9" height="12" rx="1.6" /><rect x="11" y="8.5" width="9" height="12" rx="1.6" />
      <path d="M13.5 12.5h4M13.5 15.5h4" />
    </svg>
  ),
  council: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="7" cy="8" r="2.4" /><circle cx="17" cy="8" r="2.4" /><circle cx="12" cy="6.5" r="2.4" />
      <path d="M3.5 19c0-2.5 1.8-4 3.5-4M20.5 19c0-2.5-1.8-4-3.5-4M8.2 20c0-2.8 1.7-4.5 3.8-4.5S15.8 17.2 15.8 20" />
    </svg>
  ),
  playbooks: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 5.5C10.5 4.3 8 4 5.5 4.6v12C8 16 10.5 16.3 12 17.5M12 5.5c1.5-1.2 4-1.5 6.5-.9v12c-2.5-.6-5-.3-6.5.9M12 5.5v12" />
    </svg>
  ),
  compile: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <path d="M8.5 9.5l2.2 2.2-2.2 2.2M12.5 14.5h3.5" />
    </svg>
  ),
  vault: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="4" y="4.5" width="16" height="15" rx="2" /><circle cx="12" cy="12" r="3.4" />
      <path d="M12 12v3.4M12 8.6v.8" /><path d="M8.4 20v1.4M15.6 20v1.4" />
    </svg>
  ),
  testing: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M9.5 3.5v6L5 18a1.6 1.6 0 0 0 1.5 2.3h11A1.6 1.6 0 0 0 19 18l-4.5-8.5v-6" />
      <path d="M8 3.5h8M8 13.5h8" />
    </svg>
  ),
  brain: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M9 5a3 3 0 0 0-3 3 3 3 0 0 0-1 5.5A2.8 2.8 0 0 0 9 19V5z" />
      <path d="M15 5a3 3 0 0 1 3 3 3 3 0 0 1 1 5.5A2.8 2.8 0 0 1 15 19V5z" />
      <path d="M9 5a3 3 0 0 1 6 0" />
    </svg>
  ),
  understanding: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M9.5 17a4 4 0 1 1 5 0v1.5h-5V17z" /><path d="M10 20.5h4" />
      <path d="M12 3.5v1.4M5.8 6l1 1M18.2 6l-1 1M4 12h1.4M18.6 12H20" />
    </svg>
  ),
  bus: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M3 8h18M3 16h18" /><circle cx="7" cy="8" r="1.8" fill="currentColor" stroke="none" />
      <circle cx="15" cy="8" r="1.8" fill="currentColor" stroke="none" />
      <circle cx="10" cy="16" r="1.8" fill="currentColor" stroke="none" />
      <circle cx="18" cy="16" r="1.8" fill="currentColor" stroke="none" />
    </svg>
  ),
  interactive: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3.5" y="4" width="17" height="12" rx="2" /><path d="M8 20h8M12 16v4" />
      <path d="M11 8.5l3 1.8-3 1.8z" fill="currentColor" stroke="none" />
    </svg>
  ),
} as const;

type ToolKey = keyof typeof I;

interface Tool {
  id: ToolKey;
  name: string;
  kind: string;
  color: string;
  desc: string;
  cmd: string;
  cmdLabel: string;
}

/* garden's OWN bench tools — the gap-fillers a planner-executor can't do alone */
const OWN: Tool[] = [
  {
    id: "prove", name: "prove", kind: "evidence gate", color: "var(--c-floor)",
    desc: "Re-derives “done” by re-running the verifier and re-hashing the recording — a claimed pass that can’t be reproduced is REJECTED, never trusted.",
    cmd: "/wicked-garden:prove", cmdLabel: "slash command",
  },
  {
    id: "search", name: "search", kind: "blast-radius · lineage", color: "var(--c-layer)",
    desc: "Traces what breaks across injected bus / dispatch / capability edges that grep and a single-file LSP can never see.",
    cmd: "/wicked-garden:search:blast-radius", cmdLabel: "slash command",
  },
  {
    id: "patch", name: "patch", kind: "graph refactor", color: "var(--c-workflow)",
    desc: "Renames and moves symbols across every file as one graph operation — not a fragile find-and-replace.",
    cmd: "/wicked-garden:engineering:rename", cmdLabel: "slash command",
  },
  {
    id: "council", name: "council", kind: "multi-model panel", color: "var(--c-solo)",
    desc: "Convenes a real panel of independent external models — second opinions you can’t get from one model grading itself.",
    cmd: "/wicked-garden:jam:council", cmdLabel: "slash command",
  },
  {
    id: "playbooks", name: "archetypes", kind: "repo playbooks", color: "var(--c-floor)",
    desc: "Reads the shape of your prompt and loads the matching playbook — the right rigor and gates for build / migrate / review, steering not a fixed pipeline.",
    cmd: "/wicked-garden:archetype", cmdLabel: "slash command",
  },
  {
    id: "compile", name: "compile", kind: "portable gate", color: "var(--c-creation)",
    desc: "Stamps a self-contained evidence gate into any repo — stdlib-only, runs with no wicked-garden installed.",
    cmd: "/wicked-garden:compile <repo>", cmdLabel: "slash command",
  },
];

/* BUNDLED peers off the shelf — capabilities garden hands you from wicked-* */
const BUNDLED: Tool[] = [
  {
    id: "vault", name: "vault", kind: "peer · wicked-vault", color: "var(--c-floor)",
    desc: "The evidence backend the gate re-derives against — re-hashes and re-runs, and fails closed on a weak worker identity so “evaluator ≠ author” actually means something.",
    cmd: "installed automatically via wicked-testing", cmdLabel: "bundled dependency",
  },
  {
    id: "testing", name: "testing", kind: "peer · wicked-testing", color: "var(--c-layer)",
    desc: "A full QE team for coding agents — runs the tests and records the evidence, with the runner kept separate from the judge.",
    cmd: "claude plugins install wicked-testing", cmdLabel: "opt-in layer",
  },
  {
    id: "brain", name: "brain", kind: "peer · wicked-brain", color: "var(--c-solo)",
    desc: "Cross-session memory plus the codegraph that blast-radius and lineage read from — context that survives between sessions.",
    cmd: "claude plugins install wicked-brain", cmdLabel: "opt-in layer",
  },
  {
    id: "understanding", name: "understanding", kind: "peer · wicked-understanding", color: "var(--c-floor)",
    desc: "The repo’s own how-to playbooks, loaded from HEAD as on-demand skill-refs — portable expertise the agent didn’t have.",
    cmd: "claude plugins install wicked-understanding", cmdLabel: "opt-in layer",
  },
  {
    id: "bus", name: "bus", kind: "peer · wicked-bus", color: "var(--c-layer)",
    desc: "A local-first SQLite event bus that decouples the tools — at-least-once delivery, no network, no infra.",
    cmd: "claude plugins install wicked-bus", cmdLabel: "opt-in layer",
  },
  {
    id: "interactive", name: "interactive", kind: "peer · wicked-interactive", color: "var(--c-creation)",
    desc: "Describe it, watch it build in the browser, export HTML / PDF / PPTX / video — the visual surface off the same shelf.",
    cmd: "claude plugins install wicked-interactive", cmdLabel: "opt-in layer",
  },
];

function ToolPeg({
  tool, open, onToggle,
}: { tool: Tool; open: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      className={`tw-tool${open ? " is-open" : ""}`}
      style={{ ["--tool-c" as string]: tool.color }}
      aria-expanded={open}
      onClick={onToggle}
    >
      <span className="tw-peg" aria-hidden />
      <span className="tw-hook" aria-hidden />
      <span className="tw-body">{I[tool.id]}</span>
      <span className="tw-tag">{tool.name}</span>
      <span className="tw-grab">{open ? "on the bench" : "grab ›"}</span>
    </button>
  );
}

function ToolGroup({
  eyebrow, title, sub, tools,
}: { eyebrow: string; title: string; sub: string; tools: Tool[] }) {
  const [openId, setOpenId] = useState<ToolKey | null>(null);
  const openTool = tools.find((t) => t.id === openId) ?? null;

  return (
    <div>
      <div className="tw-group-head">
        <span className="kicker" style={{ color: "var(--c-floor)" }}>{eyebrow}</span>
        <span className="tw-group-name">{title}</span>
        <span className="tw-group-sub">{sub}</span>
      </div>
      <div className="pegboard">
        <div className="tw-grid">
          {tools.map((t) => (
            <ToolPeg
              key={t.id}
              tool={t}
              open={openId === t.id}
              onToggle={() => setOpenId((cur) => (cur === t.id ? null : t.id))}
            />
          ))}

          {openTool && (
            <div
              className="tw-spec"
              style={{ ["--tool-c" as string]: openTool.color }}
              role="region"
              aria-label={`${openTool.name} spec`}
            >
              <div className="tw-spec-top">
                <span className="tw-spec-name">{openTool.name}</span>
                <span className="tw-spec-kind">{openTool.kind}</span>
              </div>
              <p className="tw-spec-desc">{openTool.desc}</p>
              <div className="tw-spec-cmdlabel">{openTool.cmdLabel}</div>
              <CopyChip text={openTool.cmd} />
            </div>
          )}
        </div>
      </div>
      <div className="bench-lip" aria-hidden />
    </div>
  );
}

export default function ToolWall() {
  return (
    <div className="relative mx-auto w-full max-w-[1240px] px-5 sm:px-8">
      <Reveal>
        <p className="kicker">01 / the tool wall</p>
        <h2 className="mt-6 max-w-[20ch] font-display text-[clamp(1.9rem,5vw,3.4rem)] font-extrabold leading-[1.0] tracking-[-0.02em]">
          Not a workflow. A wall you load out from.
        </h2>
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted">
          Every capability hangs in its own silhouette. Grab any tool to read the
          one-line spec and the exact command. You leave knowing the set you get —
          garden’s own bench tools, and the peers it hands you off the shelf.
        </p>
      </Reveal>

      <Reveal delay={0.06}>
        <div className="mt-10 flex flex-col gap-12">
          <ToolGroup
            eyebrow="own"
            title="garden’s own bench tools"
            sub="the gap-fillers a planner-executor can’t do alone"
            tools={OWN}
          />
          <ToolGroup
            eyebrow="bundled"
            title="peers off the shelf"
            sub="capabilities garden hands you from the wicked-* family"
            tools={BUNDLED}
          />
        </div>
      </Reveal>
    </div>
  );
}
