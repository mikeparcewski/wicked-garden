import { useState } from "react";
import Reveal from "./Reveal";

/* ── The evidence conditions the gate re-derives ─────────────────────────────
   The visitor plays the lying agent: flip a condition off and pull PROVE. The
   gate re-derives and refuses to be fooled. This is garden's one differentiator
   made drivable — done is re-derived, never asserted. */
interface Condition {
  id: string;
  label: string;
  on: string;   // wording when the evidence holds
  off: string;  // wording when the visitor breaks it
}

const CONDITIONS: Condition[] = [
  { id: "verifier",  label: "verifier actually ran",      on: "the test command executed", off: "no run — nothing to re-derive" },
  { id: "hash",      label: "evidence hash matches",       on: "recording is unaltered",    off: "hash ≠ recording — edited after the fact" },
  { id: "vault",     label: "vault backend present",       on: "wicked-vault resolvable",   off: "vault pulled — gate can't re-check" },
  { id: "attest",    label: "independent attestation",     on: "evaluator ≠ author",        off: "evaluator = author — self-grading" },
];

type Status = "proved" | "rejected" | "unavailable";

interface Verdict {
  status: Status;
  word: string;
  sub: string;
  tag: string;
  cls: string;
}

/* The gate logic — order matters: a missing vault fails CLOSED before any
   pass/reject can be considered (never a vacuous pass). */
function derive(s: Record<string, boolean>): Verdict {
  if (!s.vault) {
    return {
      status: "unavailable",
      word: "FAILS CLOSED",
      sub: "gate: unavailable — the vault it re-derives against is gone.",
      tag: "a missing backend is never a vacuous pass.",
      cls: "is-unavail",
    };
  }
  if (!s.verifier) {
    return {
      status: "rejected", word: "REJECTED",
      sub: "the verifier never ran — there is nothing to re-derive.",
      tag: "you claimed done; the evidence disagrees.", cls: "is-rejected",
    };
  }
  if (!s.hash) {
    return {
      status: "rejected", word: "REJECTED",
      sub: "evidence hash ≠ the recording — the claim was edited after the run.",
      tag: "you claimed done; the evidence disagrees.", cls: "is-rejected",
    };
  }
  if (!s.attest) {
    return {
      status: "rejected", word: "REJECTED",
      sub: "no independent attestation — the evaluator is the author (self-grading).",
      tag: "you claimed done; the evidence disagrees.", cls: "is-rejected",
    };
  }
  return {
    status: "proved", word: "PROVED",
    sub: "the gate re-ran the verifier and re-hashed the recording. Every condition holds.",
    tag: "done is re-derived, not asserted.", cls: "is-proved",
  };
}

export default function ProveBench() {
  const [state, setState] = useState<Record<string, boolean>>({
    verifier: true, hash: true, vault: true, attest: true,
  });
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [pulled, setPulled] = useState(false);

  function flip(id: string) {
    setState((s) => ({ ...s, [id]: !s[id] }));
    setVerdict(null);        // any change re-arms the gate
    setPulled(false);
  }

  function pull() {
    if (pulled) return;
    setPulled(true);
    // the lever throws, then the gate re-derives and slams the stamp down
    window.setTimeout(() => setVerdict(derive(state)), 480);
  }

  function reset() {
    setState({ verifier: true, hash: true, vault: true, attest: true });
    setVerdict(null);
    setPulled(false);
  }

  return (
    <div className="relative mx-auto w-full max-w-[1240px] px-5 sm:px-8">
      <Reveal>
        <p className="kicker">02 / the prove bench</p>
        <h2 className="pb-title mt-4 w-full font-display text-[clamp(2.1rem,6vw,4rem)] font-extrabold leading-[1.0] tracking-[-0.02em]">
          Play the lying agent. Watch the gate refuse.
        </h2>
      </Reveal>

      <Reveal delay={0.06}>
        <div className="pb-shell mt-8">

          {/* ── left column: the intro + the claim handed to the visitor ── */}
          <div className="pb-left">
            <p className="pb-intro">
              Here is the one differentiator, made drivable. Flip the evidence, pull the
              lever — the gate re-derives the claim instead of taking your word.
            </p>

            {/* ── the claim handed to the visitor ── */}
            <div className="pb-claim-card">
            <span className="pb-claim-tape" aria-hidden />
            <div className="pb-claim-kind">claim card · archetype: build</div>
            <div className="pb-claim-text">
              <b>build:</b> all acceptance tests pass
            </div>
            <p className="pb-claim-note">
              The agent stamped this “done.” The gate doesn’t trust the stamp — it
              re-runs the verifier, re-hashes the recording, and checks the vault is
              even there. Break any condition below and prove it can’t be fooled.
            </p>
            </div>
          </div>

          {/* ── the machine ── */}
          <div className="pb-machine">
            <div className="pb-machine-head">
              <span>evidence conditions</span>
              <span>{verdict ? "gate: re-derived" : "gate: armed"}</span>
            </div>

            <div className="pb-switches">
              {CONDITIONS.map((c) => {
                const on = state[c.id];
                return (
                  <button
                    key={c.id}
                    type="button"
                    role="switch"
                    aria-checked={on}
                    className="pb-switch"
                    onClick={() => flip(c.id)}
                  >
                    <span className="pb-toggle" aria-hidden />
                    <span className="pb-switch-body">
                      <span className="pb-switch-label">{c.label}</span>
                      <span className="pb-switch-cond">{on ? c.on : c.off}</span>
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="pb-action">
              <button
                type="button"
                className="pb-lever"
                data-pulled={pulled}
                disabled={pulled}
                onClick={pull}
                aria-label="Pull the PROVE lever"
              >
                <span className="pb-lever-slot" aria-hidden>
                  <span className="pb-lever-knob" />
                </span>
                <span className="pb-lever-word">prove</span>
              </button>

              <div className="pb-stamp" aria-live="polite">
                {verdict ? (
                  <div className={`pb-mark ${verdict.cls}`} key={verdict.word + verdict.sub}>
                    <span className="pb-mark-word">{verdict.word}</span>
                    <span className="pb-mark-sub">{verdict.sub}</span>
                    <span className="pb-mark-tag">{verdict.tag}</span>
                  </div>
                ) : (
                  <span className="pb-stamp-idle">
                    {pulled ? "re-deriving…" : "pull the lever — the gate stamps a verdict"}
                  </span>
                )}
              </div>
            </div>

            <button type="button" className="pb-reset" onClick={reset}>
              reset the bench
            </button>
          </div>
        </div>
      </Reveal>
    </div>
  );
}
