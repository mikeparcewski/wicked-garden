import { useEffect, useRef, useState } from "react";
import CopyChip from "./CopyChip";
import Reveal from "./Reveal";
import { TOOLS, HUE_VAR, type Tool } from "../../data/garden";

/* ============================================================================
   The Toolbox — garden's OWN tools, each one DEMONSTRATING itself.
   Distinct technique: not a click-to-reveal-text pegboard — a stage where the
   selected tool plays a tiny live proof of what it does. Auto-advances; click
   a tool to pin + replay. Show, don't tell.
============================================================================ */

/* Each demo re-mounts (via key) when its tool is selected, so CSS keyframes
   replay from the top. Kept lightweight + deterministic. */

function ProveDemo() {
  return (
    <div className="dm dm-prove">
      <div className="dm-prove-claim">“all tests pass”</div>
      <div className="dm-prove-arrow" aria-hidden>re-derive ↓</div>
      <div className="dm-prove-stamp">REJECTED</div>
      <div className="dm-prove-note">the verifier never ran</div>
    </div>
  );
}

function SearchDemo() {
  return (
    <div className="dm dm-search">
      <svg viewBox="0 0 260 150" className="dm-search-svg" aria-hidden>
        {/* nodes */}
        <g className="dm-node"><circle cx="40" cy="40" r="16" /><text x="40" y="44">emit</text></g>
        <g className="dm-node"><circle cx="150" cy="30" r="16" /><text x="150" y="34">api</text></g>
        <g className="dm-node"><circle cx="120" cy="118" r="16" /><text x="120" y="122">db</text></g>
        <g className="dm-node dm-node-hidden"><circle cx="225" cy="105" r="16" /><text x="225" y="109">sub</text></g>
        {/* visible (grep-able) edges */}
        <path className="dm-edge" d="M56 40 L134 32" />
        <path className="dm-edge" d="M148 46 L126 102" />
        {/* injected edge grep can't see — draws + lights up */}
        <path className="dm-edge dm-edge-injected" d="M52 52 Q140 150 210 112" />
      </svg>
      <div className="dm-search-tags">
        <span className="dm-tag dm-tag-grep">grep: 2 refs</span>
        <span className="dm-tag dm-tag-inject">+ injected edge · event→consumer</span>
      </div>
    </div>
  );
}

function PatchDemo() {
  return (
    <div className="dm dm-patch">
      {["auth.ts", "route.ts", "user.ts"].map((f, n) => (
        <div className="dm-file" key={f} style={{ ["--d" as string]: `${n * 0.12}s` }}>
          <span className="dm-file-name">{f}</span>
          <span className="dm-file-line">
            import <span className="dm-rename"><s>getUsr</s><b>getUser</b></span>
          </span>
        </div>
      ))}
      <div className="dm-patch-note">one graph operation · 3 files</div>
    </div>
  );
}

function CouncilDemo() {
  const models = [
    { m: "antigravity", v: "ship", ok: true },
    { m: "codex", v: "ship", ok: true },
    { m: "claude", v: "blocks: race", ok: false },
  ];
  return (
    <div className="dm dm-council">
      {models.map((x, n) => (
        <div className={`dm-model${x.ok ? "" : " dissent"}`} key={x.m} style={{ ["--d" as string]: `${n * 0.18}s` }}>
          <span className="dm-model-name">{x.m}</span>
          <span className="dm-model-v">{x.v}</span>
        </div>
      ))}
      <div className="dm-council-note">independent panel · 1 dissent surfaced</div>
    </div>
  );
}

function ArchetypesDemo() {
  return (
    <div className="dm dm-arche">
      <div className="dm-arche-prompt">“migrate the users table to the new schema”</div>
      <div className="dm-arche-chips">
        {["triage", "build", "migrate", "review"].map((a) => (
          <span key={a} className={`dm-arche-chip${a === "migrate" ? " hit" : ""}`}>{a}</span>
        ))}
      </div>
      <div className="dm-arche-meter"><span className="dm-arche-fill" /></div>
      <div className="dm-arche-note">hard gate · rollback proof · independent attestation</div>
    </div>
  );
}

function DeliberateDemo() {
  return (
    <div className="dm dm-delib">
      <div className="dm-delib-ask">“add a retry to the flaky API call”</div>
      <div className="dm-delib-lenses">
        {["assumptions", "root cause", "alternatives", "risk", "reframe"].map((l, n) => (
          <span key={l} className="dm-delib-lens" style={{ ["--d" as string]: `${0.4 + n * 0.14}s` }}>{l}</span>
        ))}
      </div>
      <div className="dm-delib-out">
        <span className="dm-delib-out-tag">reframed</span>
        it isn’t flaky — the timeout is 500ms. Fix the timeout, not the symptom.
      </div>
    </div>
  );
}

const DEMOS: Record<string, () => JSX.Element> = {
  prove: ProveDemo,
  search: SearchDemo,
  patch: PatchDemo,
  council: CouncilDemo,
  archetypes: ArchetypesDemo,
  deliberate: DeliberateDemo,
};

const ADVANCE_MS = 4200;

export default function Toolbox() {
  const [active, setActive] = useState(0);
  const [nonce, setNonce] = useState(0);
  const [pinned, setPinned] = useState(false);
  const [hovering, setHovering] = useState(false);

  // Auto-play unless the visitor has taken control (pinned) or is hovering to read.
  const playing = !pinned && !hovering;

  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => {
      setActive((n) => (n + 1) % TOOLS.length);
      setNonce((n) => n + 1);
    }, ADVANCE_MS);
    return () => window.clearInterval(id);
  }, [playing]);

  function pick(n: number) {
    setPinned(true);          // clicking a tool takes control + stops auto-advance
    setActive(n);
    setNonce((x) => x + 1);
  }

  function resume() {
    setPinned(false);
    setHovering(false);
    setNonce((x) => x + 1);
  }

  const tool: Tool = TOOLS[active];
  const Demo = DEMOS[tool.id];
  const hue = `var(${HUE_VAR[tool.hue]})`;

  return (
    <div className="mx-auto w-full max-w-[1240px] px-5 sm:px-8">
      <Reveal>
        <p className="kicker">01 / the toolbox</p>
        <h2 className="tb-h2">Six gaps your agent can’t close alone.</h2>
        <p className="tb-intro">
          Your harness plans, swarms, and ships. These are the six things a
          planner-executor genuinely can’t do on its own — and they’re a sample:{" "}
          the full kit runs to 94 skills across 12 domains. It plays itself; click any tool to pin it.
        </p>
      </Reveal>

      {/* persistent affordance — always visible, tells the visitor it's live + clickable */}
      <div className="tb-afford" data-pinned={pinned}>
        {pinned ? (
          <>
            <span className="tb-afford-state" aria-hidden>❚❚</span>
            <span className="tb-afford-text">
              pinned <b>{tool.name}</b> — you’re driving
            </span>
            <button type="button" className="tb-afford-btn" onClick={resume}>
              ▶ resume auto-play
            </button>
          </>
        ) : (
          <>
            <span className="tb-afford-state tb-afford-live" aria-hidden>▶</span>
            <span className="tb-afford-text">
              auto-playing the demos — <b>click any tool to pin it</b> and take control
            </span>
          </>
        )}
      </div>

      <Reveal delay={0.06}>
        <div
          className="tb-shell"
          style={{ ["--hue" as string]: hue }}
          onMouseEnter={() => setHovering(true)}
          onMouseLeave={() => setHovering(false)}
        >
          {/* left rail — the tools */}
          <div className="tb-rail" role="tablist" aria-label="garden tools">
            {TOOLS.map((t, n) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={n === active}
                className={`tb-rail-item${n === active ? " is-on" : ""}${n === active && pinned ? " is-pinned" : ""}`}
                style={{ ["--hue" as string]: `var(${HUE_VAR[t.hue]})` }}
                onClick={() => pick(n)}
                title="Click to pin this tool"
              >
                <span className="tb-rail-num">{String(n + 1).padStart(2, "0")}</span>
                <span className="tb-rail-body">
                  <span className="tb-rail-name">{t.name}</span>
                  <span className="tb-rail-kind">{t.kind}</span>
                </span>
                <span className="tb-rail-gap">it {t.gap}</span>
                <span className="tb-rail-pin" aria-hidden>{n === active && pinned ? "pinned" : "pin"}</span>
                {/* auto-advance progress — visible proof it's playing + will move on */}
                {n === active && playing && (
                  <span className="tb-rail-bar" key={`bar-${nonce}`} aria-hidden>
                    <span className="tb-rail-bar-fill" style={{ animationDuration: `${ADVANCE_MS}ms` }} />
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* stage — the live proof + spec */}
          <div className="tb-stage">
            <div className="tb-stage-demo" key={`${tool.id}-${nonce}`}>
              <Demo />
            </div>
            <div className="tb-stage-spec">
              <div className="tb-stage-top">
                <span className="tb-stage-name">{tool.name}</span>
                <span className="tb-stage-kind">{tool.kind}</span>
              </div>
              <p className="tb-stage-fill">{tool.fill}</p>
              <div className="tb-stage-cmdlabel">{tool.cmdLabel}</div>
              <CopyChip text={tool.cmd} />
            </div>
          </div>
        </div>
      </Reveal>
    </div>
  );
}
