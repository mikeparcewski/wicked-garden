import { useEffect, useState } from "react";
import Reveal from "./Reveal";
import CopyChip from "./CopyChip";
import {
  ACCEPTANCE_ROLES,
  WALL_CROSSES,
  WALL_BLOCKED,
  type AcceptanceRole,
} from "../../data/garden";

/* ============================================================================
   THE WALL — the qe domain's one idea, absorbed from the retired wicked-testing // historical
   site: the agent that runs the tests is never the one that grades them.
   Two mechanics carried over:
   1. the reveal-reviewer flip — a self-graded PASS sent to an independent
      reviewer comes back contradicted (FAIL), and
   2. the acceptance-wall role-lighting — click Writer / Executor / Reviewer to
      light a role and read its isolation copy; evidence chips cross the dashed
      wall while reasoning bounces off it. Click the stage to play/pause.
   All claims grounded in skills/qe-acceptance-test-*: per-role `allowed-tools`
   frontmatter, `context: fork`, evidence in .wicked-qe/evidence/<run-id>/.
============================================================================ */

function ReportCard() {
  const [revealed, setRevealed] = useState(false);
  return (
    <div className="qw-fig" data-revealed={revealed}>
      <div className="qw-fig-h">
        <span>report card · same feature</span>
        <span>self-grade vs the wall</span>
      </div>
      <div className="qw-grades">
        <div className="qw-cell qw-cell--self">
          <span className="qw-tag">author grades itself</span>
          <div className="qw-mark">PASS</div>
          <div className="qw-sub">100% · every time</div>
          <span className="qw-stamp">self-reported</span>
        </div>
        <div className="qw-cell qw-cell--rev">
          <span className="qw-tag">independent reviewer</span>
          <div className="qw-mark qw-mark--rev">{revealed ? "FAIL" : "PASS"}</div>
          <div className="qw-sub">{revealed ? "caught a real bug" : "awaiting review…"}</div>
          <span className="qw-stamp">contradicted</span>
        </div>
      </div>
      <div className="qw-delta">
        <b>80%+</b> of self-graded PASSes don’t survive an independent read.
      </div>
      <button
        type="button"
        className="qw-btn"
        aria-pressed={revealed}
        onClick={() => setRevealed((r) => !r)}
      >
        {revealed ? "↺ Reset" : "Send it to an independent reviewer →"}
      </button>
      <p className="qw-note">Illustrative of the measured self-grading gap.</p>
    </div>
  );
}

function Role({
  role,
  lit,
  onLight,
}: {
  role: AcceptanceRole;
  lit: boolean;
  onLight: () => void;
}) {
  return (
    <button
      type="button"
      className={`qw-role${role.id === "reviewer" ? " qw-role--reviewer" : ""}${lit ? " is-lit" : ""}`}
      data-role={role.id}
      aria-pressed={lit}
      onClick={onLight}
    >
      <span className="qw-role-n">{role.step}</span>
      <span className="qw-role-name">{role.name}</span>
      <span className="qw-role-tools">
        {role.tools.map((t) => (
          <span key={t} className="qw-role-tool">{t}</span>
        ))}
      </span>
      <p>{lit ? role.lit : role.line}</p>
    </button>
  );
}

export default function QeWall() {
  const [litRole, setLitRole] = useState<string>("reviewer");
  const [playing, setPlaying] = useState(true);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setPlaying(false);
    }
  }, []);

  return (
    <div className="mx-auto w-full max-w-[1240px] px-5 sm:px-8">
      <Reveal>
        <p className="kicker qw-kicker">04 / the qe domain · absorbed fleet</p>
        <h2 className="qw-h2">No agent grades its own homework.</h2>
        <p className="qw-intro">
          The retired wicked-testing plugin lives on here as the{" "}{/* historical */}
          <span className="qw-em">qe domain</span> — and it brought its wall.
          The 3-agent acceptance pipeline gives each role its own tool boundary;
          the reviewer reads <span className="qw-em">cold evidence files only</span>{" "}
          — never the executor’s context, reasoning, or stdout — so the
          self-grading that inflates AI PASS rates has nowhere to hide.
        </p>
      </Reveal>

      <Reveal delay={0.06}>
        <div className="qw-grid">
          <ReportCard />
          <div className="qw-gap-copy">
            <h3 className="qw-h3">The agent that wrote the code runs the tests — and calls them green.</h3>
            <p>
              Scripted frameworks — Playwright, pytest, k6, axe-core — only run
              what you already thought to test. They don’t tell you <em>what</em>{" "}
              to test, whether the tests are any good, or whether the results
              mean anything.
            </p>
            <p className="qw-kick">
              The qe domain separates authorship from judgment — and enforces it.
            </p>
          </div>
        </div>
      </Reveal>

      <Reveal delay={0.1}>
        <div
          className={`qw-stage${playing ? " is-playing" : ""}`}
          role="group"
          aria-label="Live evidence handoff across the reviewer wall — click a role to light it, click the channel to play or pause"
        >
          {ACCEPTANCE_ROLES.slice(0, 2).map((r) => (
            <Role key={r.id} role={r} lit={litRole === r.id} onLight={() => setLitRole(r.id)} />
          ))}

          <div
            className="qw-wall"
            aria-hidden="true"
            onClick={() => setPlaying((p) => !p)}
          >
            <span className="qw-wall-tag">cold evidence only</span>
          </div>

          <Role
            role={ACCEPTANCE_ROLES[2]}
            lit={litRole === "reviewer"}
            onLight={() => setLitRole("reviewer")}
          />

          {/* the live channel: evidence chips cross, reasoning bounces off */}
          <div className="qw-channel" aria-hidden="true" onClick={() => setPlaying((p) => !p)}>
            <span className="qw-chip qw-chip--pass" style={{ top: "26%", animationDelay: "0s" }}>manifest.json</span>
            <span className="qw-chip qw-chip--pass" style={{ top: "70%", animationDelay: "1.3s" }}>evidence.json</span>
            <span className="qw-chip qw-chip--pass" style={{ top: "44%", animationDelay: "2.6s" }}>step-N.json</span>
            <span className="qw-chip qw-chip--pass" style={{ top: "84%", animationDelay: "3.9s" }}>context.md</span>
            <span className="qw-chip qw-chip--block" style={{ top: "36%", animationDelay: ".6s" }}>executor context</span>
            <span className="qw-chip qw-chip--block" style={{ top: "58%", animationDelay: "1.9s" }}>chain-of-thought</span>
            <span className="qw-chip qw-chip--block" style={{ top: "16%", animationDelay: "3.2s" }}>raw stdout</span>
            <span className="qw-chip qw-chip--block" style={{ top: "78%", animationDelay: "4.5s" }}>prior verdicts</span>
          </div>
        </div>
      </Reveal>

      <Reveal delay={0.12}>
        <div className="qw-legend">
          <div className="qw-leg qw-leg--pass">
            <div className="qw-leg-h"><span className="qw-leg-dot" />Crosses the wall — the reviewer reads</div>
            <div className="qw-leg-items">
              {WALL_CROSSES.map((f) => (
                <span key={f}><code>{f}</code></span>
              ))}
            </div>
          </div>
          <div className="qw-leg qw-leg--block">
            <div className="qw-leg-h"><span className="qw-leg-dot" />Bounced at the wall — never seen</div>
            <div className="qw-leg-items">
              {WALL_BLOCKED.map((f) => (
                <span key={f}>{f}</span>
              ))}
            </div>
          </div>
        </div>

        <div className="qw-foot">
          <p>
            Evidence lands in <code>.wicked-qe/evidence/&lt;run-id&gt;/</code>.
            Isolation is enforced by the reviewer’s <code>context: fork</code>{" "}
            boundary and an <code>allowed-tools: Read</code> frontmatter — the
            verdict is re-derived from the artifacts, never asserted by the agent
            that produced them.
          </p>
          <div className="qw-foot-cmd">
            <span className="qw-foot-cmdlabel">garden skill · accept action</span>
            <CopyChip text="wicked-garden-qe" label="try qe" />
          </div>
        </div>
      </Reveal>
    </div>
  );
}
