import { useEffect, useRef, useState } from "react";
import Reveal from "./Reveal";
import CopyChip from "./CopyChip";
import PlayToggle from "./PlayToggle";
import { useAutoplay } from "./useAutoplay";
import { TOOLS, NEW_IN, NEW_RELEASE } from "../../data/garden";

/* ============================================================================
   Memory you approve — the estate-backed memory and its propose surface.
   An agent's proposal slides into your queue; Approve or Drop it. Approved, a
   later session's question recalls it with a citation; dropped, there is nothing
   to cite. Three fixed columns, so no state resizes the stage. The decision text
   is illustrative. The section foot carries what's new in this release.
============================================================================ */

type Fate = "pending" | "approved" | "dropped";
const STEPS = [1500, 1700, 1500, 3600]; // proposed, queued, decided, recalled

export default function MemoryQueue() {
  const root = useRef<HTMLDivElement>(null);
  const ap = useAutoplay(root, 0.4);
  const [s, setS] = useState(0);
  const [fate, setFate] = useState<Fate>("pending");
  const [manual, setManual] = useState(false);
  const [cyc, setCyc] = useState(0);

  // reduced motion settles the demo on its end state, unless the visitor already decided
  useEffect(() => {
    if (ap.reduced && !manual) { setS(3); setFate("approved"); }
  }, [ap.reduced, manual]);

  useEffect(() => {
    if (manual || !ap.active) return;
    const id = window.setTimeout(() => {
      const n = (s + 1) % STEPS.length;
      if (n === 0) { setFate("pending"); setCyc((c) => c + 1); }
      if (n === 2) setFate("approved");
      setS(n);
    }, STEPS[s]);
    return () => window.clearTimeout(id);
  }, [s, manual, ap.active]);

  function decide(f: Fate) {
    setManual(true);
    setFate(f);
    setS(3);
  }
  function resume() {
    setManual(false);
    setFate("pending");
    setS(0);
    ap.play();
  }

  const queued = s >= 1;
  const later = s >= 3 && fate !== "pending";
  const mem = TOOLS.find((t) => t.id === "mem")!;

  return (
    <div className="sx sx--memory">
      <Reveal className="sx-title">
        <p className="kicker sx-kicker"><span className="sx-num">06</span>memory you approve</p>
        <h2 className="sx-h2">Agents propose. You approve.</h2>
      </Reveal>
      <Reveal className="sx-lead" delay={0.04}>
        <p>{mem.fill}</p>
      </Reveal>

      <div className="sx-stage">
        <div ref={root} className={`mq-stage mq--${fate}`} {...ap.bind} role="group" aria-label="Live demo: an agent's memory proposal waits for your approval">
          <div className="mq-col mq-propose">
            <span className="mq-col-h">1 · the agent proposes</span>
            <div className={`mq-card${queued ? " is-sent" : ""}`} key={`p-${cyc}`}>
              <span className="mq-kind">decision · proposed</span>
              <span className="mq-text">“WAL mode for the ledger — fsync JSON first”</span>
              <span className="mq-src">source: <code>ledger.ts</code> · witnessed in this job</span>
            </div>
          </div>

          <div className="mq-col mq-queue">
            <span className="mq-col-h">2 · your queue</span>
            <div className={`mq-slot${queued ? " is-full" : ""} is-${fate}`}>
              {queued ? (
                <>
                  <span className="mq-slot-text">WAL mode for the ledger</span>
                  <span className="mq-slot-state">{fate === "pending" ? "waiting for you" : fate}</span>
                </>
              ) : (
                <span className="mq-slot-empty">nothing waiting</span>
              )}
            </div>
            <div className="mq-btns">
              <button type="button" className="mq-btn mq-btn--ok" aria-pressed={fate === "approved"} onClick={() => decide("approved")}>Approve</button>
              <button type="button" className="mq-btn mq-btn--drop" aria-pressed={fate === "dropped"} onClick={() => decide("dropped")}>Drop</button>
            </div>
          </div>

          <div className="mq-col mq-later">
            <span className="mq-col-h">3 · three weeks later, a new session</span>
            <div className={`mq-ask${later ? " is-on" : ""}`}>“why did we pick WAL again?”</div>
            <div className={`mq-answer${later ? " is-on" : ""} is-${fate}`} aria-live="polite">
              {later && fate === "approved" ? (
                <>
                  <span className="mq-answer-tag">recalled</span> crash-safe writes without a server — decided 3 weeks ago{" "}
                  <span className="mq-cite">[cited · estate record]</span>
                </>
              ) : later && fate === "dropped" ? (
                <><span className="mq-answer-tag">no record</span> you dropped the proposal, so there is nothing to cite</>
              ) : (
                <span className="mq-answer-wait">the answer cites what you approved</span>
              )}
            </div>
            <div className="mq-cmd"><CopyChip text={mem.cmd} label="copy" /></div>
          </div>

          <div className="mq-afford">
            <span className="mq-afford-text">{manual ? "you’re driving" : ap.paused ? "paused" : "auto-playing — approve or drop it yourself"}</span>
            {manual ? (
              <button type="button" className="pg-afford-btn" onClick={resume}>▶ resume</button>
            ) : (
              <PlayToggle paused={ap.paused} onToggle={ap.toggle} label="the memory demo" />
            )}
          </div>
        </div>
      </div>

      <div className="sx-foot mq-new">
        <h3 className="mq-new-h" id="new-h">What’s new in {NEW_RELEASE}</h3>
        <ul className="mq-new-list" role="list" aria-labelledby="new-h">
          {NEW_IN.map((n) => (
            <li key={n.b}>
              {n.href ? <a href={n.href}><b>{n.b}</b></a> : <b>{n.b}</b>}
              {n.code ? <>{" "}<code>{n.code}</code></> : null}
              {n.rest}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
