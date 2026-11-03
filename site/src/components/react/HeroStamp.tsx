import { useEffect, useRef, useState } from "react";
import CopyChip from "./CopyChip";
import PlayToggle from "./PlayToggle";
import { useAutoplay } from "./useAutoplay";
import { focusFromKey } from "./focusFromKey";
import { CLAIMS, CHECK_ORDER } from "../../data/garden";

/* ── The hero proof, made kinetic ────────────────────────────────────────────
   An agent asserts a claim. The gate runs its checks in its real order (vault,
   verifier, hash, attestation: ProveGate derive()), each tick filling in, and the
   verdict slams in its status colour: PROVED = pass, REJECTED = fail,
   FAILS CLOSED = warn (the same words the gate below stamps). Its first claim is
   the one the page follows: the retry change. It cycles four claims (mixed verdicts, because the point is
   that it CHECKS). Pauses on hover, on focus and off-screen; a pip pins a claim;
   reduced motion starts paused on a stamped claim. The card's height is fixed, so
   the cycle never moves the page. */

const VERDICT_CLASS: Record<string, string> = {
  PROVED: "is-pass",
  REJECTED: "is-fail",
  "FAILS CLOSED": "is-warn",
};

const ASSERT_MS = 700;
const CHECK_MS = 320;
const HOLD_MS = 2600;

export default function HeroStamp() {
  const root = useRef<HTMLDivElement>(null);
  const ap = useAutoplay(root, 0.25);
  const [i, setI] = useState(0);
  const [step, setStep] = useState(0);
  const [pinned, setPinned] = useState(false);

  const c = CLAIMS[i];
  const failIdx = c.fails ? CHECK_ORDER.findIndex((x) => x.id === c.fails) : -1;
  const runs = failIdx >= 0 ? failIdx + 1 : CHECK_ORDER.length;
  const STAMP = runs + 1;
  const stamped = step >= STAMP;

  // reduced motion: no tick-by-tick animation, the claim shows stamped
  useEffect(() => {
    if (ap.reduced) setStep(STAMP);
  }, [ap.reduced, i, STAMP]);

  useEffect(() => {
    if (stamped) {
      if (!ap.active || pinned) return;
      const t = window.setTimeout(() => {
        setI((n) => (n + 1) % CLAIMS.length);
        setStep(0);
      }, HOLD_MS);
      return () => window.clearTimeout(t);
    }
    if (!(ap.active || pinned)) return;
    const t = window.setTimeout(() => setStep((s) => s + 1), step === 0 ? ASSERT_MS : CHECK_MS);
    return () => window.clearTimeout(t);
  }, [step, stamped, ap.active, pinned]);

  function pick(n: number) {
    setPinned(true);
    setI(n);
    setStep(ap.reduced ? CHECK_ORDER.length + 1 : 0);
  }

  const dots = useRef<HTMLDivElement>(null);
  // one tab stop for the claim pips (the shown claim); arrow keys, Home and End pick another
  function onDotsKey(e: React.KeyboardEvent) {
    const keys = ["ArrowRight", "ArrowLeft", "Home", "End"];
    if (!keys.includes(e.key)) return;
    e.preventDefault();
    const n = e.key === "Home" ? 0 : e.key === "End" ? CLAIMS.length - 1
      : (i + (e.key === "ArrowRight" ? 1 : -1) + CLAIMS.length) % CLAIMS.length;
    pick(n);
    focusFromKey(dots.current?.querySelectorAll<HTMLButtonElement>(".hs-pip")[n]);
  }

  function togglePlay() {
    if (ap.paused || pinned) {
      setPinned(false);
      ap.play();
    } else ap.pause();
  }

  // step 0 = asserted; step k + 1 = check k is running; step >= k + 2 = check k has a result;
  // step runs + 1 = every check that runs has a result, and the stamp lands
  const tickState = (k: number) => {
    if (k >= runs) return stamped ? "is-skip" : "is-pending";
    if (step >= k + 2) return k === failIdx ? "is-fail" : "is-ok";
    if (step === k + 1) return "is-checking";
    return "is-pending";
  };

  const state = stamped ? "checked" : step === 0 ? "asserted" : "checking";
  const vcls = VERDICT_CLASS[c.verdict];

  return (
    <div
      ref={root}
      className={`hs-card${stamped ? ` hs-stamped ${vcls}` : ""}`}
      {...ap.bind}
      role="group"
      aria-label="Live demo: an agent's claim, re-derived by the evidence gate"
    >
      <div className="hs-head">
        <span className="hs-dot" aria-hidden />
        <span className="hs-head-l">agent · {c.archetype}</span>
        <span className="hs-head-r">{state}</span>
      </div>

      <div className="hs-claim" key={`claim-${i}`}>
        <span className="hs-claim-q" aria-hidden>“</span>
        {c.claim}
        <span className="hs-claim-q" aria-hidden>”</span>
      </div>
      <div className="hs-asserted">the agent says so. the gate checks the evidence itself.</div>

      <ol className="hs-ticks" aria-label="the gate's checks, in order">
        {CHECK_ORDER.map((x, k) => {
          const st = tickState(k);
          return (
            <li key={x.id} className={`hs-tick ${st}`}>
              <span className="hs-tick-mark" aria-hidden>
                {st === "is-ok" ? "✓" : st === "is-fail" ? "✕" : st === "is-skip" ? "–" : "·"}
              </span>
              <span className="hs-tick-name">{x.short}</span>
            </li>
          );
        })}
      </ol>

      <div className="hs-stage" aria-live="polite">
        {stamped ? (
          <div className={`hs-mark ${vcls}`} key={`mark-${i}`}>
            <span className="hs-word">{c.verdict}</span>
            <span className="hs-reason">{c.reason}</span>
          </div>
        ) : (
          <span className="hs-idle">checking the evidence…</span>
        )}
      </div>

      <div className="hs-controls">
        <div className="hs-dots" role="tablist" aria-label="pick a claim" ref={dots} onKeyDown={onDotsKey}>
          {CLAIMS.map((claim, n) => (
            <button
              key={n}
              type="button"
              role="tab"
              aria-selected={n === i}
              aria-label={`claim ${n + 1}: ${claim.claim}`}
              tabIndex={n === i ? 0 : -1}
              className={`hs-pip${n === i ? " is-on" : ""}`}
              onClick={() => pick(n)}
            />
          ))}
        </div>
        <span className="hs-afford">
          {pinned ? "pinned — you’re driving" : ap.paused ? "paused" : "hover to hold · pick a claim"}
        </span>
        <PlayToggle paused={ap.paused || pinned} onToggle={togglePlay} label="the claim demo" />
      </div>

      <div className="hs-foot">
        <CopyChip text="/wicked-garden-prove" label="in your agent" kind="agent" />
        <p className="gd-hero-call">
          Call a skill by name: in Claude Code, <code>/wicked-garden-prove</code>; in Codex, OpenCode, Pi or
          Antigravity, ask your agent to use <code>wicked-garden-prove</code>.
        </p>
      </div>
    </div>
  );
}
