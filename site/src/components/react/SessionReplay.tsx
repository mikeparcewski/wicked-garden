import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import Marker from "./Marker";
import Reveal from "./Reveal";

const SESSION_LOG = [
  {
    tool: "prompt",
    color: "var(--muted)",
    bg: "transparent",
    text: "\"refactor auth middleware — session tokens leaking into logs\"",
    desc: null,
  },
  {
    tool: "garden",
    color: "var(--accent)",
    bg: "color-mix(in oklab, var(--accent) 12%, transparent)",
    text: "BUILD archetype · 4 phases · evidence-gated",
    desc: "reads the shape of each task and applies exactly that much rigor",
  },
  {
    tool: "brain",
    color: "var(--c-workflow)",
    bg: "color-mix(in oklab, var(--c-workflow) 12%, transparent)",
    text: "3 memories surfaced · last auth PR · INC-42 security note · session.ts types",
    desc: "surfaces relevant memory across sessions — your agent never starts cold",
  },
  {
    tool: "loom",
    color: "var(--c-foundation)",
    bg: "color-mix(in oklab, var(--c-foundation) 12%, transparent)",
    text: "gate open · evidence required before phase 2 unlocks",
    desc: "the gate engine — re-derives evidence rather than trusting the agent's claim",
  },
  {
    tool: "vault",
    color: "var(--c-foundation)",
    bg: "color-mix(in oklab, var(--c-foundation) 12%, transparent)",
    text: "recording · actor: garden-prove · run-id: 4f2a · hash: a3f7b2c1",
    desc: "tamper-evident evidence store — every claim has a verifiable hash",
  },
  {
    tool: "bus",
    color: "var(--c-layer)",
    bg: "color-mix(in oklab, var(--c-layer) 12%, transparent)",
    text: "3 events → phase.start · evidence.record · gate.check",
    desc: "local event bus — coordinates tools without a cloud intermediary",
  },
  {
    tool: "testing",
    color: "var(--c-creation)",
    bg: "color-mix(in oklab, var(--c-creation) 12%, transparent)",
    text: "3 verdicts rendered · PASS · evaluator ≠ implementer · re-derived",
    desc: "evidence-gated test verdicts — the reviewer never graded its own work",
  },
  {
    tool: "loom",
    color: "var(--c-foundation)",
    bg: "color-mix(in oklab, var(--c-foundation) 12%, transparent)",
    text: "GATE PASSED · proven, not self-reported ✓",
    desc: null,
  },
  {
    tool: "patch",
    color: "var(--c-layer)",
    bg: "color-mix(in oklab, var(--c-layer) 12%, transparent)",
    text: "4 files changed · auth.ts · middleware.ts · session.ts · types.ts",
    desc: "tracks exactly what the agent changed — diffable, auditable",
  },
] as const;

function SessionLine({
  line,
  index,
  reduce,
}: {
  line: (typeof SESSION_LOG)[number];
  index: number;
  reduce: boolean;
}) {
  const [hovered, setHovered] = useState(false);

  const isSuccess =
    line.tool === "loom" && line.text.startsWith("GATE PASSED");

  const content = (
    <div
      className={`session-line${isSuccess ? " is-success" : ""}`}
    >
      <span
        className="session-pill"
        style={{ color: line.color, background: line.bg }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {line.tool}
        {line.desc && (
          <span
            className="session-tooltip"
            style={{ opacity: hovered ? 1 : 0 }}
          >
            {line.desc}
          </span>
        )}
      </span>
      <span className="session-text">{line.text}</span>
    </div>
  );

  if (reduce) {
    return content;
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -16 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true, margin: "-5% 0px" }}
      transition={{
        duration: 0.4,
        delay: index * 0.1,
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      {content}
    </motion.div>
  );
}

export default function SessionReplay() {
  const reduce = useReducedMotion();

  return (
    <section id="session">
      <div className="mx-auto max-w-[1240px] px-5 py-28 sm:px-8">
        <Reveal>
          <p className="kicker">02 / in practice</p>
          <h2 className="mt-5 font-display text-[clamp(1.9rem,4.4vw,3.4rem)] font-extrabold leading-[1.02] tracking-tight">
            One prompt.{" "}
            <Marker color="var(--c-workflow)">Eight tools working.</Marker>
          </h2>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">
            This is what a guarded session looks like.
          </p>
        </Reveal>

        <div className="session-panel">
          {SESSION_LOG.map((line, i) => (
            <SessionLine
              key={`${line.tool}-${i}`}
              line={line}
              index={i}
              reduce={!!reduce}
            />
          ))}
        </div>

        <p className="session-caption">
          Every line is a tool. Every tool is one install command. Nothing phones home.
        </p>
      </div>
    </section>
  );
}
