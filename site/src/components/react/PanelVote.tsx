import { useEffect, useRef, useState } from "react";
import Reveal from "./Reveal";
import CopyChip from "./CopyChip";
import PlayToggle from "./PlayToggle";
import { useAutoplay } from "./useAutoplay";

/* ============================================================================
   A second opinion — the review panel for a disputed decision (garden
   skills/jam-council: usable external model CLIs sit on the panel; short of two,
   isolated same-family workers, labelled weaker diversity; short of two workers,
   no quorum and no verdict). Pick what you have installed and watch the panel
   form. Three vote rows are always reserved, so switching never resizes it.
   The agent names and votes are illustrative.
============================================================================ */

type Mode = "several" | "family" | "none";
interface Vote { who: string; v: string; dissent?: boolean }

const MODES: { id: Mode; label: string }[] = [
  { id: "several", label: "several other agents" },
  { id: "family", label: "one model family" },
  { id: "none", label: "fewer than two" },
];

const VOTES: Record<Mode, (Vote | null)[]> = {
  several: [
    { who: "codex", v: "ship" },
    { who: "antigravity", v: "ship" },
    { who: "opencode", v: "blocks: race in retry", dissent: true },
  ],
  family: [
    { who: "same family · worker 1", v: "ship" },
    { who: "same family · worker 2", v: "blocks: race in retry", dissent: true },
    null,
  ],
  none: [{ who: "one worker available", v: "—" }, null, null],
};

const RESULT: Record<Mode, { k: string; t: string; cls: string }> = {
  several: { k: "panel 2 of 3", t: "ship · 1 dissent surfaced: a race in retry", cls: "is-pass" },
  family: { k: "weaker diversity", t: "same-family workers, labelled weaker diversity", cls: "is-warn" },
  none: { k: "no quorum", t: "fewer than two workers: no verdict", cls: "is-fail" },
};

const STEP_MS = 4600;

export default function PanelVote() {
  const root = useRef<HTMLDivElement>(null);
  const ap = useAutoplay(root, 0.4);
  const [mode, setMode] = useState<Mode>("several");
  const [manual, setManual] = useState(false);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (manual || !ap.active) return;
    const id = window.setTimeout(() => {
      setMode((m) => MODES[(MODES.findIndex((x) => x.id === m) + 1) % MODES.length].id);
      setNonce((x) => x + 1);
    }, STEP_MS);
    return () => window.clearTimeout(id);
  }, [mode, manual, ap.active]);

  function pick(m: Mode) {
    setManual(true);
    setMode(m);
    setNonce((x) => x + 1);
  }
  function resume() {
    setManual(false);
    ap.play();
  }
  function onRadioKey(e: React.KeyboardEvent) {
    const i = MODES.findIndex((x) => x.id === mode);
    const n = e.key === "ArrowDown" || e.key === "ArrowRight" ? (i + 1) % MODES.length
      : e.key === "ArrowUp" || e.key === "ArrowLeft" ? (i - 1 + MODES.length) % MODES.length
      : e.key === "Home" ? 0 : e.key === "End" ? MODES.length - 1 : -1;
    if (n < 0) return;
    e.preventDefault();
    pick(MODES[n].id);
    (e.currentTarget as HTMLElement).querySelector<HTMLButtonElement>(`[data-mode="${MODES[n].id}"]`)?.focus();
  }

  const r = RESULT[mode];

  return (
    <div className="sx sx--panel">
      <Reveal className="sx-title">
        <p className="kicker sx-kicker"><span className="sx-num">05</span>a second opinion</p>
        <h2 className="sx-h2">A disputed decision gets a second opinion.</h2>
      </Reveal>
      <Reveal className="sx-lead" delay={0.04}>
        <p>
          When a decision is disputed, a review panel weighs in using the other agents you have
          installed; a same-family fallback is labelled, and without a quorum it gives no verdict.
        </p>
      </Reveal>

      <div className="sx-stage">
        <div ref={root} className={`pv-stage pv--${mode}`} {...ap.bind} role="group" aria-label="Live demo: a review panel forms from the agents you have installed">
          <div className="pv-left">
            <div className="pv-q">
              <span className="pv-q-k">disputed</span>
              <span className="pv-q-t">ship the retry change? the builder says yes, a reviewer says no</span>
            </div>
            <p className="pv-sel-h" id="pv-sel-h">agents you have installed</p>
            <div className="pv-sel" role="radiogroup" aria-labelledby="pv-sel-h" onKeyDown={onRadioKey}>
              {MODES.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  role="radio"
                  data-mode={m.id}
                  tabIndex={mode === m.id ? 0 : -1}
                  aria-checked={mode === m.id}
                  className={`pv-opt${mode === m.id ? " is-on" : ""}`}
                  onClick={() => pick(m.id)}
                >
                  {m.label}
                </button>
              ))}
            </div>
            <div className="pv-afford">
              <span className="pv-afford-text">{manual ? "you’re driving" : ap.paused ? "paused" : "auto-playing"}</span>
              {manual ? (
                <button type="button" className="pg-afford-btn" onClick={resume}>▶ resume</button>
              ) : (
                <PlayToggle paused={ap.paused} onToggle={ap.toggle} label="the panel demo" />
              )}
            </div>
          </div>

          <div className="pv-right">
            <ol className="pv-votes" key={`v-${mode}-${nonce}`} aria-live="polite">
              {VOTES[mode].map((x, n) =>
                x ? (
                  <li key={n} className={`pv-vote${x.dissent ? " is-dissent" : ""}`} style={{ ["--d" as string]: `${n * 0.32}s` }}>
                    <span className="pv-who">{x.who}</span>
                    <span className="pv-v">{x.v}</span>
                  </li>
                ) : (
                  <li key={n} className="pv-vote is-empty" style={{ ["--d" as string]: `${n * 0.32}s` }}>
                    <span className="pv-who">no one to ask</span>
                    <span className="pv-v" aria-hidden>—</span>
                  </li>
                ),
              )}
            </ol>
            <div className={`pv-result ${r.cls}`} key={`r-${mode}-${nonce}`}>
              <span className="pv-result-k">{r.k}</span>
              <span className="pv-result-t">{r.t}</span>
            </div>
            <div className="pv-cmd"><CopyChip text="wicked-garden-jam" label="try the panel" /></div>
          </div>
        </div>
      </div>
    </div>
  );
}
