import { useEffect, useState } from "react";
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useReducedMotion,
  useSpring,
  useTransform,
} from "motion/react";
import { ROLES, STATS } from "../../data/projects";
import Marker from "./Marker";

const WORDS = [
  { t: "smart", c: "var(--c-workflow)" },
  { t: "handy", c: "var(--c-creation)" },
  { t: "autonomous", c: "var(--c-foundation)" },
  { t: "honest", c: "var(--c-creation)" },
  { t: "fast", c: "var(--accent-bright)" },
  { t: "yours", c: "var(--c-workflow)" },
];

const ease = [0.16, 1, 0.3, 1] as const;

export default function Hero() {
  const reduce = useReducedMotion();
  const mx = useMotionValue(0.64);
  const my = useMotionValue(0.34);
  const sx = useSpring(mx, { stiffness: 48, damping: 18, mass: 0.7 });
  const sy = useSpring(my, { stiffness: 48, damping: 18, mass: 0.7 });
  const bx = useTransform(sx, (v) => (v - 0.5) * 260);
  const by = useTransform(sy, (v) => (v - 0.5) * 220);

  function onMove(e: React.PointerEvent<HTMLElement>) {
    if (reduce) return;
    const r = e.currentTarget.getBoundingClientRect();
    mx.set((e.clientX - r.left) / r.width);
    my.set((e.clientY - r.top) / r.height);
  }

  return (
    <section
      id="top"
      onPointerMove={onMove}
      className="relative flex min-h-[100svh] items-center overflow-hidden px-5 pb-20 pt-28 sm:px-8"
    >
      {/* atmosphere */}
      <div className="grid-floor pointer-events-none absolute inset-0 -z-20 opacity-70" aria-hidden />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 m-auto h-[62vmax] w-[62vmax] rounded-full"
        style={{
          x: bx,
          y: by,
          background: "radial-gradient(closest-side, var(--mesh-1), transparent 70%)",
          filter: "blur(44px)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -right-[12%] top-[6%] -z-10 h-[42vmax] w-[42vmax] rounded-full"
        style={{ background: "radial-gradient(closest-side, var(--mesh-2), transparent 70%)", filter: "blur(52px)" }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -left-[10%] bottom-[0%] -z-10 h-[36vmax] w-[36vmax] rounded-full"
        style={{ background: "radial-gradient(closest-side, var(--mesh-3), transparent 72%)", filter: "blur(56px)" }}
      />

      <div className="mx-auto w-full max-w-[1240px]">
        <p className="rise kicker" style={{ animationDelay: "0.05s" }}>
          {STATS.projects} open-source tools · one garden · MIT
        </p>

        <h1 className="mt-6 font-display text-[clamp(2.6rem,7.3vw,6rem)] font-extrabold leading-[0.94] tracking-[-0.02em]">
          <span className="rise block" style={{ animationDelay: "0.12s" }}>
            tools that are
          </span>
          <span className="rise mt-1 block" style={{ animationDelay: "0.2s" }}>
            wicked <AnimatedWord reduce={!!reduce} />
          </span>
        </h1>

        <p
          className="rise mt-8 max-w-xl text-balance text-lg leading-relaxed text-muted sm:text-xl"
          style={{ animationDelay: "0.32s" }}
        >
          The open-source toolkit for AI-native engineers — one garden, {STATS.projects} tools.
          Your agent already plans and swarms; this is{" "}
          <em className="font-medium not-italic text-ink">everything it can't do alone</em> —
          memory, evidence, and verdicts you can trust.
        </p>

        <div className="rise mt-9 flex flex-wrap items-center gap-3" style={{ animationDelay: "0.42s" }}>
          <a
            href="#tour"
            className="group inline-flex items-center gap-2 rounded-full bg-accent px-6 py-3.5 font-mono text-[0.8rem] font-semibold uppercase tracking-[0.12em] text-on-accent transition-transform duration-300 hover:-translate-y-0.5"
            style={{ boxShadow: "0 12px 40px -12px var(--accent)" }}
          >
            Walk the garden
            <span className="transition-transform duration-300 group-hover:translate-x-1">→</span>
          </a>
          <a
            href="https://github.com/mikeparcewski"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-full border border-line-strong px-6 py-3.5 font-mono text-[0.8rem] uppercase tracking-[0.12em] text-ink transition-colors hover:border-accent hover:text-accent"
          >
            View on GitHub ↗
          </a>
        </div>

        <ul className="rise mt-10 flex flex-wrap gap-2.5" style={{ animationDelay: "0.52s" }} aria-label="Garden roles">
          {ROLES.map((r) => (
            <li key={r.id}>
              <a
                href="#tour"
                className="inline-flex items-center gap-2 rounded-full border border-line bg-surface/40 px-3.5 py-1.5 font-mono text-[0.72rem] lowercase tracking-[0.08em] text-muted transition-colors hover:text-ink"
              >
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: `var(${r.colorVar})` }} />
                {r.label}
              </a>
            </li>
          ))}
        </ul>

        <dl
          className="rise mt-14 flex flex-wrap gap-x-10 gap-y-4 border-t border-line pt-7 font-mono"
          style={{ animationDelay: "0.62s" }}
        >
          <Stat n={STATS.projects} label="tools" />
          <Stat n={STATS.accounts} label="accounts" />
          <Stat n={STATS.agents} label="QE agents" />
          <Stat n={STATS.archetypes} label="archetypes" />
          <Stat n={STATS.harnesses} label="harnesses" />
        </dl>
      </div>

      {/* scroll cue */}
      <a
        href="#manifesto"
        className="absolute bottom-6 left-1/2 hidden -translate-x-1/2 flex-col items-center gap-2 text-muted md:flex"
        aria-label="Scroll to manifesto"
      >
        <span className="font-mono text-[0.64rem] uppercase tracking-[0.3em]">scroll</span>
        <span
          className="block h-7 w-px bg-current"
          style={reduce ? undefined : { animation: "scroll-bob 1.8s ease-in-out infinite" }}
        />
      </a>
    </section>
  );
}

function Stat({ n, label }: { n: number; label: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <dt className="sr-only">{label}</dt>
      <dd className="text-2xl font-semibold tabular-nums" style={{ color: "var(--accent)" }}>
        {n}
      </dd>
      <span className="text-[0.78rem] uppercase tracking-[0.14em] text-muted">{label}</span>
    </div>
  );
}

function AnimatedWord({ reduce }: { reduce: boolean }) {
  const [i, setI] = useState(0);

  useEffect(() => {
    if (reduce) return;
    const id = setInterval(() => setI((p) => (p + 1) % WORDS.length), 2300);
    return () => clearInterval(id);
  }, [reduce]);

  if (reduce) {
    return <Marker color={WORDS[0].c}>{WORDS[0].t}</Marker>;
  }

  return (
    <span className="relative inline-block">
      <AnimatePresence mode="wait">
        <motion.span
          key={WORDS[i].t}
          className="inline-block"
          initial={{ y: "0.42em", opacity: 0, filter: "blur(7px)" }}
          animate={{ y: 0, opacity: 1, filter: "blur(0px)" }}
          exit={{ y: "-0.42em", opacity: 0, filter: "blur(7px)" }}
          transition={{ duration: 0.44, ease }}
        >
          <Marker color={WORDS[i].c} delay={0.1}>
            {WORDS[i].t}
          </Marker>
        </motion.span>
      </AnimatePresence>
    </span>
  );
}
