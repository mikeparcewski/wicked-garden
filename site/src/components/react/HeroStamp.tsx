import { useEffect, useRef, useState } from "react";
import CopyChip from "./CopyChip";
import { CLAIMS } from "../../data/garden";

/* ── The hero proof, made kinetic ────────────────────────────────────────────
   An agent asserts a claim; garden re-derives it and slams a verdict. Cycles
   through real claims — mixed verdicts, because the point is it CHECKS. Pauses
   when hovered/focused so a visitor can read. This teases the gate below. */

const VERDICT_CLASS: Record<string, string> = {
  "RE-DERIVED": "hs-proved",
  REJECTED: "hs-rejected",
  "FAILS CLOSED": "hs-unavail",
};

export default function HeroStamp() {
  const [i, setI] = useState(0);
  const [phase, setPhase] = useState<"asserting" | "stamped">("asserting");
  const paused = useRef(false);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let t1: number, t2: number;
    const run = () => {
      setPhase("asserting");
      t1 = window.setTimeout(() => setPhase("stamped"), reduce ? 200 : 1100);
      t2 = window.setTimeout(() => {
        if (!paused.current) setI((n) => (n + 1) % CLAIMS.length);
      }, reduce ? 3200 : 3400);
    };
    run();
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, [i]);

  const c = CLAIMS[i];

  return (
    <div
      className="hs-card"
      onMouseEnter={() => (paused.current = true)}
      onMouseLeave={() => (paused.current = false)}
      onFocus={() => (paused.current = true)}
      onBlur={() => (paused.current = false)}
      tabIndex={0}
      aria-label="Live demo: an agent claim being re-derived by the evidence gate"
    >
      <div className="hs-head">
        <span className="hs-dot" aria-hidden />
        <span className="hs-head-l">agent · {c.archetype}</span>
        <span className="hs-head-r">{phase === "stamped" ? "re-derived" : "armed"}</span>
      </div>

      <div className="hs-claim" key={`claim-${i}`}>
        <span className="hs-claim-q" aria-hidden>“</span>
        {c.claim}
        <span className="hs-claim-q" aria-hidden>”</span>
      </div>
      <div className="hs-asserted">the agent asserted this. the gate doesn’t trust the stamp.</div>

      <div className="hs-stage" aria-live="polite">
        {phase === "stamped" ? (
          <div className={`hs-mark ${VERDICT_CLASS[c.verdict]}`} key={`mark-${i}`}>
            <span className="hs-word">{c.verdict}</span>
            <span className="hs-reason">{c.reason}</span>
          </div>
        ) : (
          <span className="hs-idle">re-deriving from evidence…</span>
        )}
      </div>

      <div className="hs-dots" aria-hidden>
        {CLAIMS.map((_, n) => (
          <span key={n} className={`hs-pip${n === i ? " is-on" : ""}`} />
        ))}
      </div>

      <div className="hs-foot">
        <CopyChip text="/wicked-garden:prove" label="try prove" />
      </div>
    </div>
  );
}
