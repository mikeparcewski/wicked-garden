import type { ReactNode } from "react";
import { motion, useReducedMotion } from "motion/react";
import Reveal from "./Reveal";
import Marker from "./Marker";

const ease = [0.16, 1, 0.3, 1] as const;

const LINES = [
  { no: "cloud", clause: "Your machine is the backend. The few local servers auto-start and never phone home — nothing to deploy, no cloud bill.", color: "var(--c-foundation)" },
  { no: "black box", clause: "Plain markdown and full-text search you can open, diff, grep, and audit.", color: "var(--c-workflow)" },
  { no: "self-grading", clause: "Author ≠ executor ≠ reviewer. An independent judge reads cold evidence — work never grades its own “done.”", color: "var(--c-creation)" },
  { no: "lock-in", clause: "MIT, cross-CLI, composable. Every tool stands alone, degrades gracefully — the gate even runs with nothing installed.", color: "var(--accent-bright)" },
];

export default function Manifesto() {
  return (
    <div className="relative mx-auto max-w-[1240px] px-5 py-28 sm:px-8 sm:py-36">
      <Reveal>
        <p className="kicker">01 / the manifesto</p>
        <h2 className="mt-5 font-display text-[clamp(1.9rem,4.4vw,3.4rem)] font-extrabold leading-[1.02] tracking-tight">
          Most dev tools ask you to trust them.{" "}
          <Marker color="var(--accent-bright)">Ours hand you the receipts.</Marker>
        </h2>
        <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">
          Your agent already plans, swarms, and ships. What it can't do alone is prove the
          result, remember the decision, or know your repo's “how.” The garden fills those
          gaps — and the whole kit is built on four refusals.
        </p>
      </Reveal>

      <ul className="mt-16 sm:mt-20">
        {LINES.map((line, i) => (
          <li key={line.no} className="border-t border-line py-8 sm:py-10">
            <Reveal delay={i * 0.05}>
              <div className="grid items-baseline gap-x-8 gap-y-3 md:grid-cols-12">
                <p className="font-display text-[clamp(2.1rem,5.4vw,4.2rem)] font-extrabold leading-[0.95] tracking-[-0.02em] md:col-span-6">
                  No <Strike color={line.color}>{line.no}</Strike>.
                </p>
                <p className="text-balance text-base leading-relaxed text-muted md:col-span-6 md:pt-2 md:text-lg">
                  {line.clause}
                </p>
              </div>
            </Reveal>
          </li>
        ))}
      </ul>

      <Reveal delay={0.1}>
        <p className="mt-16 max-w-3xl text-balance font-display text-[clamp(1.5rem,3.2vw,2.4rem)] font-bold leading-[1.08] tracking-tight">
          Just files you can read, evidence you can re-run, and tools that{" "}
          <Marker color="var(--c-creation)">don't lie to you.</Marker>
        </p>
      </Reveal>
    </div>
  );
}

function Strike({ children, color }: { children: ReactNode; color: string }) {
  const reduce = useReducedMotion();
  return (
    <span className="relative inline-block" style={{ color }}>
      <span>{children}</span>
      <motion.span
        aria-hidden
        className="absolute left-[-2%] right-[-2%] top-[52%] h-[0.085em] rounded-full"
        style={{ background: "currentColor", originX: 0 }}
        initial={reduce ? { scaleX: 1 } : { scaleX: 0 }}
        whileInView={{ scaleX: 1 }}
        viewport={{ once: true, margin: "-18% 0px" }}
        transition={{ duration: 0.5, delay: 0.18, ease }}
      />
    </span>
  );
}
