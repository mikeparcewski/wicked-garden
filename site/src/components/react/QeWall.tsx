import { useEffect, useRef, useState } from "react";
import Reveal from "./Reveal";
import CopyChip from "./CopyChip";
import PlayToggle from "./PlayToggle";
import { useAutoplay } from "./useAutoplay";
import {
  ACCEPTANCE_ROLES,
  WALL_CROSSES,
  WALL_BLOCKED,
  type AcceptanceRole,
} from "../../data/garden";

/* ============================================================================
   THE WALL — the qe domain's one idea: the agent that runs the tests is never the
   one that grades them.
   1. the report card: the retry change's self-graded PASS, sent to an independent
      reviewer, comes back contradicted (FAIL: a race in retry).
   2. the acceptance wall: light Writer / Executor / Reviewer to read its isolation
      copy (both copies share one reserved cell, so lighting never resizes a card).
      Evidence crosses the wall in its own lane and lands in the reviewer's inbox;
      reasoning bounces off the wall in a second lane. The lanes are their own grid
      row (a column on phones), so a moving chip never covers card text. A visible
      button pauses it; it also pauses on hover, focus and off-screen, and starts
      paused under reduced motion.
   Grounded in skills/qe/SKILL.md §accept: the writer plans, the executor captures,
   the reviewer judges from evidence paths only, as a separate worker, and no
   separate worker = FAIL inconclusive; evidence in .wicked-qe/evidence/<run-id>/.
   (The skills' own read-only lines are advisory text, so no tool boundary is
   claimed here.)
============================================================================ */

function ReportCard() {
  const [revealed, setRevealed] = useState(false);
  return (
    <div className="qw-fig" data-revealed={revealed}>
      <div className="qw-fig-h">
        <span>report card · same change</span>
        <span>self-grade vs the wall</span>
      </div>
      <div className="qw-grades">
        <div className="qw-cell qw-cell--self">
          <span className="qw-tag">author grades itself</span>
          <div className="qw-mark">PASS</div>
          <div className="qw-sub">always</div>
          <span className="qw-stamp">self-reported</span>
        </div>
        <div className="qw-cell qw-cell--rev">
          <span className="qw-tag">independent reviewer</span>
          <div className="qw-mark qw-mark--rev">{revealed ? "FAIL" : "PASS"}</div>
          <div className="qw-sub qw-sub--rev">
            <span className={`qw-sub-t${revealed ? "" : " is-on"}`} aria-hidden={revealed}>awaiting review…</span>
            <span className={`qw-sub-t${revealed ? " is-on" : ""}`} aria-hidden={!revealed}>caught a race in retry</span>
          </div>
          <span className="qw-stamp">contradicted</span>
        </div>
      </div>
      <button
        type="button"
        className="qw-btn"
        aria-pressed={revealed}
        onClick={() => setRevealed((r) => !r)}
      >
        {revealed ? "↺ Reset" : "Send it to an independent reviewer →"}
      </button>
      <p className="qw-note">illustrative: the same change, graded twice</p>
    </div>
  );
}

function Role({
  role,
  lit,
  onLight,
  children,
}: {
  role: AcceptanceRole;
  lit: boolean;
  onLight: () => void;
  children?: React.ReactNode;
}) {
  return (
    <div className={`qw-role qw-role--${role.id}${lit ? " is-lit" : ""}`} data-role={role.id}>
      <button type="button" className="qw-role-btn" aria-pressed={lit} onClick={onLight}>
        <span className="qw-role-n">{role.step}</span>
        <span className="qw-role-name">{role.name}</span>
        <span className="qw-role-tools">
          <span className="qw-role-tool"><span className="qw-role-tool-k">gets:</span> {role.gets}</span>
        </span>
        <span className="qw-role-copy">
          <span className="qw-role-line" aria-hidden={lit}>{role.line}</span>
          <span className="qw-role-lit" aria-hidden={!lit}>{role.lit}</span>
        </span>
      </button>
      {children}
    </div>
  );
}

const TICK_MS = 2600;
const CYCLE = WALL_CROSSES.length + 1; // four chips in flight, then a full inbox

export default function QeWall() {
  const stage = useRef<HTMLDivElement>(null);
  const ap = useAutoplay(stage, 0.35);
  const [litRole, setLitRole] = useState<string>("reviewer");
  const [t, setT] = useState(0);

  useEffect(() => {
    if (ap.reduced) setT(CYCLE - 1);
  }, [ap.reduced]);

  useEffect(() => {
    if (!ap.active) return;
    const id = window.setTimeout(() => setT((x) => (x + 1) % CYCLE), TICK_MS);
    return () => window.clearTimeout(id);
  }, [t, ap.active]);

  const inFlight = t < WALL_CROSSES.length;
  const received = WALL_CROSSES.slice(0, inFlight ? t : WALL_CROSSES.length);
  const playing = ap.active;

  return (
    <div className="sx sx--qe">
      <Reveal className="sx-title">
        <p className="kicker sx-kicker qw-kicker"><span className="sx-num">03</span>the qe domain · absorbed wicked-testing</p>{/* historical */}
        <h2 className="sx-h2">In acceptance, <span className="sx-key">no agent grades its own homework.</span></h2>
      </Reveal>
      <Reveal className="sx-lead" delay={0.12}>
        <p>
          Its acceptance pipeline never runs the reviewer inline with the test writer or the executor;
          those two also run as separate workers where the host can start them. The reviewer reads{" "}
          <span className="qw-em">cold evidence files only</span>: never the executor’s conversation or
          reasoning; command output reaches it only as recorded evidence.
        </p>
      </Reveal>

      <div className="sx-stage qw-layout">
        <ReportCard />

        <div
          ref={stage}
          className={`qw-stage${playing ? " is-playing" : ""}`}
          role="group"
          aria-label="Live evidence handoff across the reviewer wall — light a role to read its boundary"
          {...ap.bind}
        >
          {ACCEPTANCE_ROLES.slice(0, 2).map((r) => (
            <Role key={r.id} role={r} lit={litRole === r.id} onLight={() => setLitRole(r.id)} />
          ))}

          <div className="qw-wall" aria-hidden="true">
            <span className="qw-wall-tag">cold evidence only</span>
          </div>

          <Role role={ACCEPTANCE_ROLES[2]} lit={litRole === "reviewer"} onLight={() => setLitRole("reviewer")}>
            <div className="qw-inbox" aria-label="the reviewer's inbox">
              <span className="qw-inbox-h">inbox · reads only these</span>
              {/* all four slots are always laid out (unreceived ones invisible), so filling the inbox never resizes it */}
              <span className="qw-inbox-items">
                {WALL_CROSSES.map((f) => (
                  <code key={f} className={`qw-inbox-item${received.includes(f) ? " is-in" : ""}`} aria-hidden={!received.includes(f)}>{f}</code>
                ))}
              </span>
            </div>
          </Role>

          {/* the live channel: its own row, so chips never cross card text */}
          <div className="qw-track" aria-hidden="true">
            <div className="qw-lane qw-lane--pass">
              {inFlight && (
                <span className="qw-chip qw-chip--pass" key={`p-${t}`}>{WALL_CROSSES[t]}</span>
              )}
            </div>
            <div className="qw-lane qw-lane--block">
              {inFlight && (
                <span className="qw-chip qw-chip--block" key={`b-${t}`}>{WALL_BLOCKED[t]}</span>
              )}
            </div>
          </div>

          <div className="qw-stage-foot">
            <span className="qw-legend">
              <span className="qw-leg-dot qw-leg-dot--pass" aria-hidden />
              <span>crosses: evidence files</span>
              <span className="qw-leg-dot qw-leg-dot--block" aria-hidden />
              <span>bounced: {WALL_BLOCKED.join(" · ")}</span>
            </span>
            <PlayToggle paused={ap.paused} onToggle={ap.toggle} label="the evidence handoff" />
          </div>
        </div>
      </div>

      <div className="sx-foot qw-foot">
        <p>
          Evidence lands in <code>.wicked-qe/evidence/&lt;run-id&gt;/</code>. The reviewer is a separate worker
          whose brief carries only evidence paths; if none can run, the verdict is{" "}
          <code>FAIL inconclusive</code>, never an inline self-review.
        </p>
        <div className="qw-foot-cmd">
          <CopyChip text="/wicked-garden-qe accept" label="in your agent" kind="agent" />
        </div>
      </div>
    </div>
  );
}
