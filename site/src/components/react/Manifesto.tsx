import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import Marker from "./Marker";

const ease = [0.16, 1, 0.3, 1] as const;

const REFUSALS = [
  {
    no: "cloud",
    clause:
      "Your machine is the backend. The few local servers auto-start and never phone home — nothing to deploy, no cloud bill.",
    color: "var(--c-foundation)",
  },
  {
    no: "black box",
    clause:
      "Plain markdown and full-text search you can open, diff, grep, and audit.",
    color: "var(--c-workflow)",
  },
  {
    no: "lock-in",
    clause:
      "MIT, cross-CLI, composable. Every tool stands alone, degrades gracefully — the gate even runs with nothing installed.",
    color: "var(--accent-bright)",
  },
];

const SENTINEL_COUNT = REFUSALS.length + 1;

export default function Manifesto() {
  const [crossedIdx, setCrossedIdx] = useState(-1);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const sentinels = Array.from(wrap.querySelectorAll<HTMLElement>(".m-sentinel"));
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setCrossedIdx(Number((e.target as HTMLElement).dataset.idx) - 1);
          }
        }
      },
      { threshold: 0.5 },
    );
    sentinels.forEach((s) => io.observe(s));
    return () => io.disconnect();
  }, []);

  return (
    <div ref={wrapRef} className="m-wrap" style={{ height: `${SENTINEL_COUNT * 100}vh` }}>
      <div className="m-sentinels" aria-hidden="true">
        {Array.from({ length: SENTINEL_COUNT }, (_, i) => (
          <div key={i} className="m-sentinel" data-idx={i} />
        ))}
      </div>

      <div className="m-stage">
        <section
          id="manifesto"
          className="mx-auto max-w-[1240px] px-5 pb-4 sm:px-8"
          style={{ paddingTop: "1rem" }}
        >
          <p className="kicker">01 / the manifesto</p>

          {/* Single two-column grid — intro row + refusal rows share the same columns */}
          <div className="mt-3 grid gap-x-10 sm:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">

            {/* Title — spans both columns */}
            <div className="col-span-full pt-4 pb-8 sm:pt-5 sm:pb-10">
              <h2 className="font-display text-[clamp(1.7rem,3.8vw,2.8rem)] font-extrabold leading-[1.04] tracking-tight">
                Most dev tools ask you to trust them.{" "}
                <Marker color="var(--accent-bright)">Ours hand you the receipts.</Marker>
              </h2>
            </div>

            {/* Refusal rows — each is two siblings in the grid */}
            {REFUSALS.map((r, i) => (
              <RefusalRow key={r.no} refusal={r} crossed={i <= crossedIdx} isFirst={i === 0} />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function RefusalRow({
  refusal,
  crossed,
  isFirst,
}: {
  refusal: (typeof REFUSALS)[0];
  crossed: boolean;
  isFirst?: boolean;
}) {
  const border = isFirst ? "" : "border-t border-line";
  return (
    <>
      <div className={`${border} py-4 sm:py-5`}>
        <p className="font-display text-[clamp(2rem,4.8vw,3.8rem)] font-extrabold leading-[0.9] tracking-[-0.025em]">
          No{" "}
          <Strike color={refusal.color} crossed={crossed}>
            {refusal.no}
          </Strike>
          .
        </p>
      </div>
      <div className={`${border} py-4 sm:flex sm:items-center sm:py-5`}>
        <p className="text-base leading-relaxed text-muted sm:text-lg">
          {refusal.clause}
        </p>
      </div>
    </>
  );
}

function Strike({
  children,
  color,
  crossed,
}: {
  children: ReactNode;
  color: string;
  crossed: boolean;
}) {
  const reduce = useReducedMotion();
  return (
    <span className="relative inline-block" style={{ color }}>
      <span>{children}</span>
      <motion.span
        aria-hidden
        className="absolute left-[-2%] right-[-2%] top-[52%] h-[0.1em] rounded-full"
        style={{ background: "currentColor", originX: 0 }}
        animate={{ scaleX: crossed ? 1 : 0 }}
        transition={reduce ? { duration: 0 } : { duration: 0.55, ease }}
      />
    </span>
  );
}
