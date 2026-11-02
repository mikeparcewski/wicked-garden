import { useEffect, useRef, useState } from "react";
import Reveal from "./Reveal";
import CopyChip from "./CopyChip";
import PlayToggle from "./PlayToggle";
import { useAutoplay } from "./useAutoplay";

/* ============================================================================
   The graph — the search and patch demos as one stage on wicked-estate's code graph.
   It runs on the change the page follows: the retry change.
   1. grep vs the estate graph: grep finds the three files that spell maxRetry; the
      graph also draws the event→consumer edge grep never sees (retry.ts emits
      "job.retried", notify.ts consumes it), in the foundation hue.
   2. the rename: the field maxRetry → maxRetries lands across three files as one graph
      operation, the old and new names side by side with a visible arrow between them.
      It is the rename the patch skill's TypeScript generator performs (a field
      declaration, a property access, a destructuring: scripts/engineering/patch/
      generators/typescript_generator.py _rename_field).
   Auto-plays grep → graph → rename → reset; any control takes over. Fixed-size
   panes: nothing on the page moves while it plays.
============================================================================ */

type Mode = "grep" | "graph";
const FILES = [
  { f: "retry.ts", pre: "interface Policy { ", post: ": number }" },
  { f: "queue.ts", pre: "if (n > policy.", post: ") fail(job);" },
  { f: "worker.ts", pre: "const { ", post: " } = policy;" },
];
const STEPS = [2600, 3000, 3400, 1400]; // grep, graph, rename, reset

export default function GraphStage() {
  const root = useRef<HTMLDivElement>(null);
  const ap = useAutoplay(root, 0.4);
  const [mode, setMode] = useState<Mode>("grep");
  const [renamed, setRenamed] = useState(false);
  const [nonce, setNonce] = useState(0);
  const [manual, setManual] = useState(false);
  const [s, setS] = useState(0);

  useEffect(() => {
    if (manual || !ap.active) return;
    const t = window.setTimeout(() => {
      const n = (s + 1) % STEPS.length;
      if (n === 0) { setMode("grep"); setRenamed(false); }
      if (n === 1) setMode("graph");
      if (n === 2) { setRenamed(true); setNonce((x) => x + 1); }
      if (n === 3) setRenamed(false);
      setS(n);
    }, STEPS[s]);
    return () => window.clearTimeout(t);
  }, [s, manual, ap.active]);

  function pickMode(m: Mode) {
    setManual(true);
    setMode(m);
  }
  function rename() {
    setManual(true);
    if (renamed) setRenamed(false);
    else { setRenamed(true); setNonce((x) => x + 1); }
  }
  function resume() {
    setManual(false);
    setMode("grep");
    setRenamed(false);
    setS(0);
    ap.play();
  }

  const graph = mode === "graph";

  return (
    <div className="sx sx--graph">
      <Reveal className="sx-title">
        <p className="kicker sx-kicker"><span className="sx-num">02</span>the graph</p>
        <h2 className="sx-h2">Sees what grep can’t, with <span className="sx-key">wicked-estate.</span></h2>
      </Reveal>
      <Reveal className="sx-lead" delay={0.12}>
        <p>
          On estate’s code graph it finds the event and command links grep never sees, for blast
          radius, and its patch skill renames across files as a graph operation.
        </p>
      </Reveal>

      <div className="sx-stage">
        <div ref={root} className={`gx-stage${graph ? " is-graph" : ""}`} {...ap.bind}
          role="group" aria-label="Live demo: grep against the estate graph, then a rename across files">
          <div className="gx-pane gx-impact">
            <div className="gx-pane-h">
              <span className="gx-pane-t">blast radius of <code>maxRetry</code></span>
              <span className="gx-seg" role="group" aria-label="search with">
                <button type="button" className="gx-seg-btn" aria-pressed={!graph} onClick={() => pickMode("grep")}>grep</button>
                <button type="button" className="gx-seg-btn" aria-pressed={graph} onClick={() => pickMode("graph")}>estate graph</button>
              </span>
            </div>
            <div className="gx-canvas">
              <svg viewBox="0 0 400 190" className="gx-svg" aria-hidden>
                <path className="gx-edge gx-edge-a" d="M112 95 L218 40" />
                <path className="gx-edge gx-edge-b" d="M112 95 L218 150" />
                <path className={`gx-edge gx-edge-inj${graph ? " is-on" : ""}`} d="M112 95 C 190 95, 230 95, 292 95" key={`inj-${graph}`} />
                <g className="gx-node is-hit"><rect x="22" y="78" width="90" height="34" rx="9" /><text x="67" y="100">retry.ts</text></g>
                <g className="gx-node is-hit"><rect x="218" y="23" width="92" height="34" rx="9" /><text x="264" y="45">queue.ts</text></g>
                <g className="gx-node is-hit"><rect x="218" y="133" width="92" height="34" rx="9" /><text x="264" y="155">worker.ts</text></g>
                <g className={`gx-node gx-node-inj${graph ? " is-on" : ""}`}><rect x="292" y="78" width="96" height="34" rx="9" /><text x="340" y="100">notify.ts</text></g>
              </svg>
              <span className={`gx-tag${graph ? " is-on" : ""}`} aria-hidden={!graph}>+ injected edge · event→consumer</span>
            </div>
            <p className="gx-result" aria-live="polite">
              {graph ? (
                <><b className="gx-res-k">estate graph</b> the same 3 files + <b className="gx-res-inj">notify.ts</b>, which consumes the <code>job.retried</code> event retry.ts emits: 4 files affected</>
              ) : (
                <><b className="gx-res-k">grep -rn maxRetry</b> 3 hits: retry.ts, queue.ts, worker.ts. notify.ts never shows up.</>
              )}
            </p>
            <div className="gx-cmd"><CopyChip text="/wicked-garden-search blast-radius maxRetry" label="in your agent" kind="agent" /></div>
          </div>

          <div className="gx-pane gx-patch">
            <div className="gx-pane-h">
              <span className="gx-pane-t">patch · one graph operation</span>
              {/* both labels share one cell, so the swap never changes the button's width */}
              <button type="button" className="gx-rename-btn" aria-pressed={renamed} onClick={rename}
                aria-label={renamed ? "undo the rename" : "rename maxRetry → maxRetries"}>
                <span className={`gx-rename-l${renamed ? "" : " is-on"}`} aria-hidden>rename maxRetry → maxRetries</span>
                <span className={`gx-rename-l${renamed ? " is-on" : ""}`} aria-hidden>undo the rename</span>
              </button>
            </div>
            <div className="gx-files" key={`files-${nonce}`}>
              {FILES.map((x, n) => (
                <div className={`gx-file${renamed ? " is-renamed" : ""}`} key={x.f} style={{ ["--d" as string]: `${n * 0.28}s` }}>
                  <span className="gx-file-name">{x.f}</span>
                  <code className="gx-file-line">
                    {x.pre}
                    <span className="gx-old">maxRetry</span>
                    <span className="gx-arrow">{" → "}</span>
                    <span className="gx-new">maxRetries</span>
                    {x.post}
                  </code>
                </div>
              ))}
            </div>
            <p className="gx-result">
              {renamed
                ? <><b className="gx-res-k">3 files touched</b> in one graph operation (notify.ts reads the event, not the field)</>
                : <>the field appears in three files; the rename edits all three as one graph operation</>}
            </p>
            <div className="gx-cmd"><CopyChip text="/wicked-garden-engineering-patch rename maxRetry maxRetries" label="in your agent" kind="agent" /></div>
          </div>

          <div className="gx-afford">
            <span className="gx-afford-text">
              {manual ? "you’re driving" : ap.paused ? "paused" : "auto-playing — pick grep or the graph, or run the rename"}
            </span>
            {manual ? (
              <button type="button" className="pg-afford-btn" onClick={resume}>▶ resume auto-play</button>
            ) : (
              <PlayToggle paused={ap.paused} onToggle={ap.toggle} label="the graph demo" />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
