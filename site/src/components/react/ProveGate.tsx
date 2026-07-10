import { useState } from "react";
import Reveal from "./Reveal";
import { CONDITIONS } from "../../data/garden";

/* ============================================================================
   The Gate — the ONE differentiator, made drivable.
   You play the lying agent: break a condition, pull PROVE, watch the gate
   re-derive and refuse to be fooled. "Done is re-derived, not asserted."
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

const ALL_ON = { verifier: true, hash: true, vault: true, attest: true };

export default function ProveGate() {
  const [state, setState] = useState<Record<string, boolean>>({ ...ALL_ON });
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [pulled, setPulled] = useState(false);

  function flip(id: string) {
    setState((s) => ({ ...s, [id]: !s[id] }));
    setVerdict(null);
    setPulled(false);
  }
  function pull() {
    if (pulled) return;
    setPulled(true);
    window.setTimeout(() => setVerdict(derive(state)), 460);
  }
  function reset() {
    setState({ ...ALL_ON });
    setVerdict(null);
    setPulled(false);
  }

  return (
    <div className="mx-auto w-full max-w-[1240px] px-5 sm:px-8">
      <Reveal>
        <p className="kicker" style={{ color: "var(--accent)" }}>02 / the gate</p>
        <h2 className="pg-h2">Play the lying agent. Watch the gate refuse.</h2>
        <p className="pg-intro">
          This is garden’s one non-negotiable, made drivable. Break any piece of the
          evidence, pull the lever — the gate re-derives the claim instead of taking
          your word for it.
        </p>
      </Reveal>

      <Reveal delay={0.06}>
        <div className="pg-shell">
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

          {/* the machine */}
          <div className="pg-machine">
            <div className="pg-machine-head">
              <span>evidence conditions</span>
              <span>{verdict ? "gate: re-derived" : "gate: armed"}</span>
            </div>

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

            <button type="button" className="pg-reset" onClick={reset}>reset the bench</button>
          </div>
        </div>
      </Reveal>
    </div>
  );
}
