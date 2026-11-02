import { useEffect, useRef, useState } from "react";
import Reveal from "./Reveal";
import PlayToggle from "./PlayToggle";
import { useAutoplay } from "./useAutoplay";
import { CONDITIONS, CHECK_ORDER, type CheckId } from "../../data/garden";

/* ============================================================================
   The Gate — the one differentiator, made drivable AND self-playing.
   It plays itself: resets the bench, breaks one condition, pulls PROVE, lights
   the evidence trail in the gate's real check order (vault first, the fail-closed
   ordering), and stamps the verdict in its status colour, cycling every way it can
   refuse. Flip a switch or pull the lever and you drive. Every state lives inside
   a fixed-height machine, so nothing on the page moves while it plays.
============================================================================ */

type Status = "proved" | "rejected" | "unavailable";
interface Verdict { status: Status; word: string; sub: string; tag: string; cls: string; failed?: CheckId }

function derive(s: Record<string, boolean>): Verdict {
  if (!s.vault)
    return { status: "unavailable", word: "FAILS CLOSED", failed: "vault",
      sub: "gate: unavailable — the vault it re-derives against is gone.",
      tag: "a missing backend is never a vacuous pass.", cls: "is-warn" };
  if (!s.verifier)
    return { status: "rejected", word: "REJECTED", failed: "verifier",
      sub: "the verifier never ran — there is nothing to re-derive.",
      tag: "you claimed done; the evidence disagrees.", cls: "is-fail" };
  if (!s.hash)
    return { status: "rejected", word: "REJECTED", failed: "hash",
      sub: "evidence hash ≠ the recording — the claim was edited after the run.",
      tag: "you claimed done; the evidence disagrees.", cls: "is-fail" };
  if (!s.attest)
    return { status: "rejected", word: "REJECTED", failed: "attest",
      sub: "no independent attestation — the evaluator is the author (self-grading).",
      tag: "you claimed done; the evidence disagrees.", cls: "is-fail" };
  return { status: "proved", word: "PROVED",
    sub: "the gate re-ran the verifier and re-hashed the recording. Every condition holds.",
    tag: "done is re-derived, not asserted.", cls: "is-pass" };
}

const ALL_ON: Record<string, boolean> = { verifier: true, hash: true, vault: true, attest: true };

/* Auto-play script: each cycle breaks one condition (or none) to show a verdict. */
const SCRIPT: (string | null)[] = [null, "verifier", "vault", "attest"];

/* Step machine. s=0 armed, s=1 a condition broken, s=2 the lever is pulled and check 0 runs,
   s=2+k check k runs, s=2+runs every check that runs has a result and the verdict lands. */
const DUR = { armed: 1000, broken: 950, check: 260, hold: 2800 };

const ADVISE_ID = "pg-advise";

export default function ProveGate() {
  const machine = useRef<HTMLDivElement>(null);
  const ap = useAutoplay(machine, 0.4);
  const [state, setState] = useState<Record<string, boolean>>({ ...ALL_ON });
  const [s, setS] = useState(0);
  const [manual, setManual] = useState(false);
  const [cycle, setCycle] = useState(0);
  const [advise, setAdvise] = useState(false);
  const adviseBtn = useRef<HTMLButtonElement>(null);
  const adviseClose = useRef<HTMLButtonElement>(null);

  const v = derive(state);
  const failIdx = v.failed ? CHECK_ORDER.findIndex((x) => x.id === v.failed) : -1;
  const runs = failIdx >= 0 ? failIdx + 1 : CHECK_ORDER.length;
  const pulled = s >= 2;
  const stamped = s >= 2 + runs;

  // the timeline: auto-play advances while active; a manual pull plays its own trail to the verdict
  useEffect(() => {
    if (manual) {
      if (!pulled || stamped) return;
      if (ap.reduced) { setS(2 + runs); return; }
      const t = window.setTimeout(() => setS((x) => x + 1), DUR.check);
      return () => window.clearTimeout(t);
    }
    if (!ap.active) return;
    const brk = SCRIPT[cycle % SCRIPT.length];
    let ms = DUR.check;
    let next = () => setS((x) => x + 1);
    if (s === 0) ms = DUR.armed;
    else if (s === 1) ms = DUR.broken;
    if (s === 0 && !brk) next = () => setS(2); // nothing to break: straight to the pull
    if (stamped) {
      ms = DUR.hold;
      next = () => {
        setState({ ...ALL_ON });
        setS(0);
        setCycle((c) => c + 1);
      };
    }
    const t = window.setTimeout(() => {
      if (s === 0 && brk) setState({ ...ALL_ON, [brk]: false });
      next();
    }, ms);
    return () => window.clearTimeout(t);
  }, [s, manual, ap.active, ap.reduced, cycle, pulled, stamped, runs]);

  // Escape closes the advise panel; focus returns to its toggle
  useEffect(() => {
    if (!advise) return;
    // no scroll: on a phone the panel opens as a sheet right above the link that opened it
    adviseClose.current?.focus({ preventScroll: true });
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") closeAdvise(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [advise]);

  function closeAdvise() {
    setAdvise(false);
    window.requestAnimationFrame(() => adviseBtn.current?.focus({ preventScroll: true }));
  }

  function flip(id: string) {
    setManual(true);
    setState((x) => ({ ...x, [id]: !x[id] }));
    setS(0);
  }
  function pull() {
    if (pulled) return;
    setManual(true);
    setS(2);
  }
  function reset() {
    setManual(true);
    setState({ ...ALL_ON });
    setS(0);
  }
  function resume() {
    setState({ ...ALL_ON });
    setS(0);
    setCycle((c) => c + 1);
    setManual(false);
    ap.play();
  }

  const trail = (k: number) => {
    if (k >= runs) return stamped ? "is-skip" : "is-pending";
    if (s >= k + 3 || (stamped && k < runs)) return k === failIdx ? `is-fail ${v.cls}` : "is-ok";
    if (s === k + 2) return "is-checking";
    return "is-pending";
  };

  const gateState = stamped ? "gate: checked" : pulled ? "gate: checking" : "gate: armed";
  const failedShort = v.failed ? CHECK_ORDER.find((x) => x.id === v.failed)?.short : null;

  return (
    <div className="sx sx--gate">
      <Reveal className="sx-title">
        <p className="kicker sx-kicker"><span className="sx-num">01</span>the gate</p>
        <h2 className="sx-h2">Play the lying agent. Watch the gate <span className="sx-key">refuse.</span></h2>
      </Reveal>
      <Reveal className="sx-lead" delay={0.12}>
        <p>
          <b>Proof, not claims.</b> Run the proof gate and “done” is re-checked from evidence: an
          unsupported claim is rejected, and by default the gate fails closed if its checks cannot run
          (an explicit claim-only fallback is labelled). Which entry paths block and which only advise
          is{" "}<a href="https://github.com/mikeparcewski/wicked-garden#what-blocks-what-advises">spelled out</a>.
        </p>
      </Reveal>

      <div className="sx-stage">
        <div
          ref={machine}
          className={`pg-machine${stamped ? ` is-stamped ${v.cls}` : ""}`}
          role="region"
          aria-label="Evidence gate — interactive demo: break a condition, pull PROVE, and watch the gate re-derive the verdict"
          {...ap.bind}
        >
          {/* covered by the advise overlay: out of the tab order and the accessibility tree while it is open */}
          <div className="pg-inner" inert={advise} aria-hidden={advise || undefined}>
          <div className="pg-head">
            <span className="pg-claimline">
              <span className="pg-claim-k">claim</span>{" "}
              <code className="pg-claim-v">the retry change: all acceptance tests pass</code>
            </span>
            <span className="pg-state">{gateState}</span>
          </div>

          <div className="pg-body">
            <div className="pg-switches">
              {CONDITIONS.map((c) => {
                const on = state[c.id];
                return (
                  <button key={c.id} type="button" role="switch" aria-checked={on}
                    className="pg-switch" onClick={() => flip(c.id)}>
                    <span className="pg-toggle" aria-hidden />
                    <span className="pg-switch-body">
                      <span className="pg-switch-label">{c.label}</span>
                      {/* both copies in one cell: the switch is as tall as its longer copy, on or off */}
                      <span className="pg-switch-cond">
                        <span className={`pg-cond${on ? " is-on" : ""}`} aria-hidden={!on}>{c.on}</span>
                        <span className={`pg-cond${on ? "" : " is-on"}`} aria-hidden={on}>{c.off}</span>
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="pg-right">
              <div className="pg-action">
                <button type="button" className="pg-lever" data-pulled={pulled}
                  disabled={pulled} onClick={pull} aria-label="Pull the PROVE lever">
                  <span className="pg-lever-slot" aria-hidden><span className="pg-lever-knob" /></span>
                  <span className="pg-lever-word">prove</span>
                </button>

                <div className="pg-stamp" aria-live="polite">
                  {stamped ? (
                    <div className={`pg-mark ${v.cls}`} key={v.word + v.sub}>
                      <span className="pg-mark-word">{v.word}</span>
                      <span className="pg-mark-sub">
                        {failedShort ? <b className="pg-mark-at">failed at: {failedShort}</b> : null}
                        {failedShort ? " — " : null}
                        {v.sub}
                      </span>
                      <span className="pg-mark-tag">{v.tag}</span>
                    </div>
                  ) : (
                    <span className="pg-stamp-idle">
                      {pulled
                        ? "checking the evidence…"
                        : "pull the lever — the gate re-runs the verifier, re-hashes the recording and checks the vault is there"}
                    </span>
                  )}
                </div>
              </div>

              <ol className="pg-trail" aria-label="evidence trail, in the order the gate checks it">
                {CHECK_ORDER.map((x, k) => {
                  const st = trail(k);
                  return (
                    <li key={x.id} className={`pg-chip ${st}`}>
                      <span className="pg-chip-n" aria-hidden>{k + 1}</span>
                      <span className="pg-chip-name">{x.short}</span>
                      <span className="pg-chip-mark" aria-hidden>
                        {st.startsWith("is-ok") ? "✓" : st.startsWith("is-fail") ? "✕" : st === "is-skip" ? "–" : st === "is-checking" ? "…" : ""}
                      </span>
                      {st === "is-skip" ? <span className="vh">not reached</span> : null}
                    </li>
                  );
                })}
              </ol>
            </div>
          </div>

          <div className="pg-foot">
            <div className="pg-afford" data-pinned={manual}>
              {manual ? (
                <>
                  <span className="pg-afford-state" aria-hidden>❚❚</span>
                  <span className="pg-afford-text">you’re driving the gate</span>
                </>
              ) : (
                <>
                  <span className={`pg-afford-state${ap.paused ? "" : " pg-afford-live"}`} aria-hidden>{ap.paused ? "❚❚" : "▶"}</span>
                  <span className="pg-afford-text">
                    {ap.paused ? "paused — " : "auto-playing — "}<b>flip a switch or pull the lever</b> to take control
                  </span>
                </>
              )}
            </div>
            <div className="pg-foot-btns">
              {manual ? (
                <button type="button" className="pg-afford-btn" onClick={resume}>▶ resume auto-play</button>
              ) : (
                <PlayToggle paused={ap.paused} onToggle={ap.toggle} label="the gate demo" />
              )}
              <button type="button" className="pg-reset" onClick={reset}>reset the bench</button>
            </div>
          </div>
          </div>

          {/* the hooks-advise detail: an overlay inside the machine, so opening it never grows the frame */}
          <div className="pg-advise" id={ADVISE_ID} hidden={!advise} role="region" aria-label="Where the gate only advises">
            <p>
              The Claude Code plugin’s hooks mostly advise — a few specific tool denials and a setup gate,
              none of which rejects a false “done” — and skills-only hosts (Codex, OpenCode, Pi, Antigravity)
              have no hooks —{" "}
              <a href="https://github.com/mikeparcewski/wicked-garden#what-blocks-what-advises">what blocks, what advises</a>.
            </p>
            <button type="button" ref={adviseClose} className="pg-advise-close" onClick={closeAdvise}>close</button>
          </div>
        </div>
      </div>

      <div className="sx-foot pg-where">
        <p>
          It refuses where it runs: when a skill invokes it, in a compiled pre-push or CI trigger, or
          inside a wicked-crew job.{" "}
          <button
            type="button"
            ref={adviseBtn}
            className="pg-where-btn"
            aria-expanded={advise}
            aria-controls={ADVISE_ID}
            onClick={() => (advise ? closeAdvise() : setAdvise(true))}
          >
            where it only advises
          </button>
        </p>
      </div>
    </div>
  );
}
