import { useEffect, useState } from "react";
import Reveal from "./Reveal";
import { QE_SPECIALISTS, QE_SURFACES, type Surface } from "../../data/garden";

/* ============================================================================
   THE FLEET — the 40 qe-* specialist fork skills, tabbed by orchestrator
   surface. Mechanic absorbed from the retired wicked-testing site: [data-surf] // historical
   filter tabs that auto-cycle through the five surfaces until the visitor
   clicks one — then they're driving. Reduced motion: no auto-cycle.
   Every name is a real skills/qe-* dir; every specialist ships context: fork.
============================================================================ */

const ORDER: Surface[] = ["plan", "authoring", "execution", "review", "insight"];
const CYCLE_MS = 2200;

export default function QeFleet() {
  const [surf, setSurf] = useState<Surface | "all">("all");
  const [auto, setAuto] = useState(true);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setAuto(false);
      return;
    }
  }, []);

  // auto-demo: cycle through the five surfaces until the user interacts
  useEffect(() => {
    if (!auto) return;
    let i = -1;
    const id = window.setInterval(() => {
      i = (i + 1) % ORDER.length;
      setSurf(ORDER[i]);
    }, CYCLE_MS);
    return () => window.clearInterval(id);
  }, [auto]);

  function pick(s: Surface | "all") {
    setAuto(false);
    setSurf(s);
  }

  const count = (k: Surface) => QE_SPECIALISTS.filter((a) => a.s === k).length;

  return (
    <div className="mx-auto w-full max-w-[1240px] px-5 sm:px-8">
      <Reveal>
        <p className="kicker qw-kicker">05 / the qe domain · the fleet</p>
        <h2 className="qf-h2">Forty specialists. Five surfaces. One contract.</h2>
        <p className="qf-intro">
          The absorbed fleet: <span className="qw-em">40 qe-* specialist skills</span>{" "}
          route beneath five orchestrator surfaces of the{" "}
          <span className="font-mono">wicked-garden-qe</span> router. Every
          specialist runs in an <span className="qw-em">isolated forked context</span>.
          Pick a surface — see who reports to it.
        </p>
      </Reveal>

      <div className="qf-afford" data-pinned={!auto}>
        {auto ? (
          <>
            <span className="qf-afford-state qf-afford-live" aria-hidden>▶</span>
            <span className="qf-afford-text">
              auto-cycling the surfaces — <b>click one to take control</b>
            </span>
          </>
        ) : (
          <>
            <span className="qf-afford-state" aria-hidden>❚❚</span>
            <span className="qf-afford-text">you’re driving the fleet</span>
          </>
        )}
      </div>

      <Reveal delay={0.06}>
        <div className="qf-filter" role="tablist" aria-label="Filter specialists by orchestrator surface">
          <span className="qf-lbl" id="qfSurfLbl">surface</span>
          <button
            type="button"
            role="tab"
            className={`qf-btn${surf === "all" ? " is-on" : ""}`}
            data-surf="all"
            aria-selected={surf === "all"}
            onClick={() => pick("all")}
          >
            all<span className="qf-n">{QE_SPECIALISTS.length}</span>
          </button>
          {QE_SURFACES.map((s) => (
            <button
              key={s.key}
              type="button"
              role="tab"
              className={`qf-btn${surf === s.key ? " is-on" : ""}`}
              data-surf={s.key}
              aria-selected={surf === s.key}
              title={s.line}
              onClick={() => pick(s.key)}
            >
              /{s.key}<span className="qf-n">{count(s.key)}</span>
            </button>
          ))}
        </div>

        <div
          className={`qf-grid${surf !== "all" ? " is-filtered" : ""}`}
          role="tabpanel"
          aria-labelledby="qfSurfLbl"
        >
          {QE_SPECIALISTS.map((a) => (
            <div
              key={a.n}
              className={`qf-agent${surf !== "all" && a.s === surf ? " is-match" : ""}`}
              data-surf={a.s}
              title={a.n}
            >
              <span className="qf-agent-dot" aria-hidden />
              <span className="qf-agent-name">{a.n}</span>
            </div>
          ))}
        </div>

        <div className="qf-legend">
          <span>40 specialists · real skills/qe-* dirs</span>
          <span>five surfaces of one router — <span className="font-mono">wicked-garden-qe</span></span>
          <span>every specialist ships with <code>context: fork</code></span>
        </div>
      </Reveal>
    </div>
  );
}
