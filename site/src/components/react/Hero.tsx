import { useEffect, useState } from "react";
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useReducedMotion,
  useSpring,
  useTransform,
} from "motion/react";
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

// The toolkit — the concrete capabilities garden hands an AI engineer
const PLOT_BEDS = [
  { id: "prove",     name: "prove",     tagline: "re-derive done",       color: "var(--accent)",       span: 2 },
  { id: "search",    name: "search",    tagline: "edges grep can't see", color: "var(--c-layer)",      span: 2 },
  { id: "patch",     name: "patch",     tagline: "refactor as a graph",  color: "var(--c-workflow)",   span: 1 },
  { id: "council",   name: "council",   tagline: "a real 2nd opinion",   color: "var(--c-solo)",       span: 1 },
  { id: "playbooks", name: "playbooks", tagline: "the repo's how-to",    color: "var(--c-foundation)", span: 1 },
  { id: "compile",   name: "compile",   tagline: "gate any repo",        color: "var(--c-creation)",   span: 1 },
] as const;

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
      {/* atmosphere — grid-floor removed; the page-level trellis motif covers this */}
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
        <div className="grid items-center gap-14 lg:grid-cols-2">

          {/* ── Left: hero copy ── */}
          <div>
            <p className="rise kicker" style={{ animationDelay: "0.05s" }}>
              the garden · open-source · MIT
            </p>

            <h1 className="mt-6 font-display text-[clamp(2rem,5vw,4rem)] font-extrabold leading-[0.94] tracking-[-0.02em]">
              <span className="rise block" style={{ animationDelay: "0.12s" }}>
                agents that are
              </span>
              <span className="rise mt-1 block" style={{ animationDelay: "0.2s" }}>
                wicked <AnimatedWord reduce={!!reduce} />
              </span>
            </h1>

            <p
              className="rise mt-8 max-w-xl text-balance text-lg leading-relaxed text-muted sm:text-xl"
              style={{ animationDelay: "0.32s" }}
            >
              Your agent already plans, swarms, and ships. wicked-garden hands it the tools it can't build alone — re-derive “done” from evidence, see the edges grep can't, refactor across files as one graph operation, and pull a real second opinion.
            </p>

            <div className="rise mt-9 flex flex-wrap items-center gap-3" style={{ animationDelay: "0.42s" }}>
              <a
                href="https://github.com/mikeparcewski/wicked-garden"
                target="_blank"
                rel="noreferrer"
                className="group inline-flex items-center gap-2 rounded-full bg-accent px-6 py-3.5 font-mono text-[0.8rem] font-semibold uppercase tracking-[0.12em] text-on-accent transition-transform duration-300 hover:-translate-y-0.5"
                style={{ boxShadow: "0 12px 40px -12px var(--accent)" }}
              >
                View on GitHub
                <span className="transition-transform duration-300 group-hover:translate-x-1">↗</span>
              </a>
              <a
                href="https://github.com/mikeparcewski"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-full border border-line-strong px-6 py-3.5 font-mono text-[0.8rem] uppercase tracking-[0.12em] text-ink transition-colors hover:border-accent hover:text-accent"
              >
                More projects ↗
              </a>
            </div>

          </div>

          {/* ── Right: garden plot (lg+ only) ── */}
          <div className="hidden lg:block">
            <GardenPlot />
          </div>

        </div>
      </div>
    </section>
  );
}

/* ── HTML garden plot ──────────────────────────────────────────────────────── */

function GardenPlot() {
  return (
    <div
      aria-label="wicked-garden capability toolkit"
      className="grid grid-cols-2 gap-2.5 rounded-2xl p-4"
      style={{ background: "var(--canvas-2)", border: "1px solid var(--hairline)" }}
    >
      {PLOT_BEDS.map((bed) => (
        <div
          key={bed.id}
          style={{
            gridColumn: bed.span === 2 ? "span 2" : "span 1",
            borderColor: bed.color,
            background: `color-mix(in oklab, ${bed.color} 9%, transparent)`,
          }}
          className="flex items-center gap-3 rounded-xl border px-3.5 py-3.5"
        >
          <SproutIcon color={bed.color} large={bed.span === 2} />
          <div className="min-w-0">
            <div
              className="truncate font-mono text-[0.72rem] font-bold leading-none tracking-[0.03em]"
              style={{ color: bed.color }}
            >
              {bed.name}
            </div>
            <div className="mt-1 truncate font-mono text-[0.57rem] uppercase tracking-[0.13em] text-muted">
              {bed.tagline}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function SproutIcon({ color, large = false }: { color: string; large?: boolean }) {
  const s = large ? 14 : 11;
  const h = large ? 17 : 13;
  return (
    <svg width={s} height={h} viewBox="0 0 11 13" fill="none" aria-hidden className="shrink-0">
      <path d="M 5.5 12.5 L 5.5 5.5" stroke={color} strokeWidth="1.6" strokeLinecap="round" />
      <path d="M 5.5 6.5 C 5.5 4 3.5 2.5 1 2.5 C 1 5 3 6.5 5.5 6.5 Z" stroke={color} strokeWidth="1.3" strokeLinejoin="round" />
      <path d="M 5.5 5.5 C 5.5 3 7.5 1.5 10 1.5 C 10 4 8 5.5 5.5 5.5 Z" stroke={color} strokeWidth="1.3" strokeLinejoin="round" />
    </svg>
  );
}

/* ── Animated word ─────────────────────────────────────────────────────────── */

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
