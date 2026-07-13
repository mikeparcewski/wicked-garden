import { useEffect, useRef, useState } from "react";
import Reveal from "./Reveal";
import { CONDITIONS } from "../../data/garden";

/* ============================================================================
   The Gate — the ONE differentiator, made drivable AND self-playing.
   It animates itself: breaks a condition, pulls PROVE, and re-stamps the
   verdict — cycling through every failure mode. Flip a switch or pull the
   lever yourself and you take control. "Done is re-derived, not asserted."
   Gate logic mirrors garden's real fail-closed ordering (vault first).
============================================================================ */

type Status = "proved" | "rejected" | "unavailable";
interface Verdict { status: Status; word: string; sub: string; tag: string; cls: string; }

function derive(s: Record<string, boolean>): Verdict {
  if (!s.vault)
    return { status: "unavailable", word: "FAILS CLOSED",
      sub: "gate: unavailable — the vault it re-derives against is gone.",
      tag: "a missing backend is never a vacuous pass.", cls: "is-unavail" };
  if (!s.verifier)
    return { status: "rejected", word: "REJECTED",
      sub: "the verifier never ran — there is nothing to re-derive.",
      tag: "you claimed done; the evidence disagrees.", cls: "is-rejected" };
  if (!s.hash)
    return { status: "rejected", word: "REJECTED",
      sub: "evidence hash ≠ the recording — the claim was edited after the run.",
      tag: "you claimed done; the evidence disagrees.", cls: "is-rejected" };
  if (!s.attest)
    return { status: "rejected", word: "REJECTED",
      sub: "no independent attestation — the evaluator is the author (self-grading).",
      tag: "you claimed done; the evidence disagrees.", cls: "is-rejected" };
  return { status: "proved", word: "PROVED",
    sub: "the gate re-ran the verifier and re-hashed the recording. Every condition holds.",
    tag: "done is re-derived, not asserted.", cls: "is-proved" };
}

const ALL_ON: Record<string, boolean> = { verifier: true, hash: true, vault: true, attest: true };

/* Auto-play script: each step breaks one condition (or none) to showcase a
   verdict — proved, then every way it can refuse. */
const SCRIPT: (string | null)[] = [null, "verifier", "vault", "attest"];

export default function ProveGate() {
  const [state, setState] = useState<Record<string, boolean>>({ ...ALL_ON });
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [pulled, setPulled] = useState(false);
  const [auto, setAuto] = useState(true);
  const [cycle, setCycle] = useState(0);
  const timers = useRef<number[]>([]);

  function clearTimers() {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
  }

  // Any hands-on interaction pins the gate — the visitor is now driving.
  function takeControl() {
    if (auto) { setAuto(false); clearTimers(); }
  }

  // Self-playing timeline: reset → break a condition → pull → re-stamp → next.
  useEffect(() => {
    if (!auto) return;
    clearTimers();
    const brk = SCRIPT[cycle % SCRIPT.length];
    const target = brk ? { ...ALL_ON, [brk]: false } : { ...ALL_ON };
    setState({ ...ALL_ON });
    setVerdict(null);
    setPulled(false);
    const at = (fn: () => void, ms: number) => timers.current.push(window.setTimeout(fn, ms));
    if (brk) at(() => setState(target), 850);
    at(() => setPulled(true), 1750);
    at(() => setVerdict(derive(target)), 2210);
    at(() => setCycle((c) => c + 1), 4500);
    return clearTimers;
  }, [auto, cycle]);

  function flip(id: string) {
    takeControl();
    setState((s) => ({ ...s, [id]: !s[id] }));
    setVerdict(null);
    setPulled(false);
  }
  function pull() {
    takeControl();
    if (pulled) return;
    setPulled(true);
    window.setTimeout(() => setVerdict(derive(state)), 460);
  }
  function reset() {
    takeControl();
    setState({ ...ALL_ON });
    setVerdict(null);
    setPulled(false);
  }
  function resume() {
    setState({ ...ALL_ON });
    setVerdict(null);
    setPulled(false);
    setCycle((c) => c + 1);
    setAuto(true);
  }

  return (
    <div className="mx-auto w-full max-w-[1240px] px-5 sm:px-8">
      {/* ── the auto-playing gate — full width, across the top ── */}
      <Reveal>
        <div
          className="pg-machine pg-machine--wide"
          role="group"
          aria-label="Evidence gate — interactive demo: break a condition, pull PROVE, and watch the gate re-derive the verdict"
        >
          <div className="pg-machine-head">
            <span>evidence conditions</span>
            <span>{verdict ? "gate: re-derived" : pulled ? "gate: re-deriving" : "gate: armed"}</span>
          </div>

          <div className="pg-machine-body">
            <div className="pg-switches">
              {CONDITIONS.map((c) => {
                const on = state[c.id];
                return (
                  <button key={c.id} type="button" role="switch" aria-checked={on}
                    className="pg-switch" onClick={() => flip(c.id)}>
                    <span className="pg-toggle" aria-hidden />
                    <span className="pg-switch-body">
                      <span className="pg-switch-label">{c.label}</span>
                      <span className="pg-switch-cond">{on ? c.on : c.off}</span>
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="pg-action">
              <button type="button" className="pg-lever" data-pulled={pulled}
                disabled={pulled} onClick={pull} aria-label="Pull the PROVE lever">
                <span className="pg-lever-slot" aria-hidden><span className="pg-lever-knob" /></span>
                <span className="pg-lever-word">prove</span>
              </button>

              <div className="pg-stamp" aria-live="polite">
                {verdict ? (
                  <div className={`pg-mark ${verdict.cls}`} key={verdict.word + verdict.sub}>
                    <span className="pg-mark-word">{verdict.word}</span>
                    <span className="pg-mark-sub">{verdict.sub}</span>
                    <span className="pg-mark-tag">{verdict.tag}</span>
                  </div>
                ) : (
                  <span className="pg-stamp-idle">
                    {pulled ? "re-deriving…" : "pull the lever — the gate stamps a verdict"}
                  </span>
                )}
              </div>
            </div>
          </div>

          <button type="button" className="pg-reset" onClick={reset}>reset the bench</button>
        </div>
      </Reveal>

      {/* persistent affordance — live state + how to take control */}
      <div className="pg-afford" data-pinned={!auto}>
        {auto ? (
          <>
            <span className="pg-afford-state pg-afford-live" aria-hidden>▶</span>
            <span className="pg-afford-text">
              auto-playing the gate — <b>flip a switch or pull the lever</b> to take control
            </span>
          </>
        ) : (
          <>
            <span className="pg-afford-state" aria-hidden>❚❚</span>
            <span className="pg-afford-text">you’re driving the gate</span>
            <button type="button" className="pg-afford-btn" onClick={resume}>
              ▶ resume auto-play
            </button>
          </>
        )}
      </div>

      {/* ── title/intro (left) + the claim it re-derives (right) ── */}
      <Reveal delay={0.06}>
        <div className="pg-shell">
          <div className="pg-intro-col">
            <p className="kicker" style={{ color: "var(--accent)" }}>02 / the gate</p>
            <h2 className="pg-h2">Play the lying agent. Watch the gate refuse.</h2>
            <p className="pg-intro">
              Garden’s one non-negotiable, made drivable. It plays itself — breaking the
              evidence and re-stamping the verdict. Flip a switch or pull the lever to take
              control: the gate re-derives the claim instead of taking your word for it.
            </p>
          </div>

          {/* the claim handed to the visitor */}
          <div className="pg-claim">
            <span className="pg-claim-tape" aria-hidden />
            <div className="pg-claim-kind">claim card · archetype: build</div>
            <div className="pg-claim-text"><b>build:</b> all acceptance tests pass</div>
            <p className="pg-claim-note">
              The agent stamped this “done.” The gate re-runs the verifier, re-hashes
              the recording, and checks the vault is even there. Break a condition and
              prove it can’t be fooled.
            </p>
          </div>
        </div>
      </Reveal>
    </div>
  );
}
