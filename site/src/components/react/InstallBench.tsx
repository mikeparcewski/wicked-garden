import { useEffect, useRef, useState } from "react";
import Reveal from "./Reveal";
import CopyChip from "./CopyChip";
import PlayToggle from "./PlayToggle";
import { useAutoplay } from "./useAutoplay";

/* ============================================================================
   The Bench — install, as two tabs so it fits one frame: the family installer
   (recommended: npx wicked-installer) or just this plugin (the two Claude Code
   plugin steps). Both panels share one reserved cell, so switching never moves
   the page. Under the installer command the bench plays what the installer does,
   step by step (wicked-installer README: it detects the coding-agent CLIs you
   have, you pick a bundle or single products, install resolves required
   dependencies — garden pulls in wicked-vault — then a readiness check). It
   pauses on hover, on focus and off-screen, and starts paused, fully shown,
   under reduced motion. Beside it, the recap: the skill calls the frames above showed, each a link back
   to its frame.
============================================================================ */

const DIRECT = [
  { id: "marketplace", cmd: "claude plugins marketplace add mikeparcewski/wicked-garden", label: "add from marketplace" },
  { id: "install", cmd: "claude plugins install wicked-garden", label: "install the plugin" },
] as const;

const TABS = [
  { id: "family", label: "family installer (recommended)" },
  { id: "plugin", label: "just this plugin" },
] as const;

const RUN = [
  "detects the coding-agent CLIs you have",
  "you pick a bundle, or single products",
  "installs them; garden pulls in wicked-vault",
  "a readiness check shows what is ready",
];
/* After the install, the page's story in your own agent: the five skill calls the frames above showed, each a
   link back to its frame (the full calls, with their arguments, are on those frames). */
const RECAP = [
  { href: "#gate", n: "01", t: "the gate", c: "/wicked-garden-prove" },
  { href: "#graph", n: "02", t: "the graph", c: "/wicked-garden-search blast-radius" },
  { href: "#qe", n: "03", t: "acceptance", c: "/wicked-garden-qe accept" },
  { href: "#panel", n: "05", t: "a second opinion", c: "/wicked-garden-jam council" },
  { href: "#memory", n: "06", t: "memory", c: "/wicked-garden-mem recall" },
];

const STEP_MS = 1100;
const HOLD_MS = 2600;

export default function InstallBench() {
  const [tab, setTab] = useState<"family" | "plugin">("family");
  const list = useRef<HTMLDivElement>(null);
  const bench = useRef<HTMLDivElement>(null);
  const ap = useAutoplay(bench, 0.4);
  const [n, setN] = useState(0);

  useEffect(() => {
    if (ap.reduced) setN(RUN.length);
  }, [ap.reduced]);

  useEffect(() => {
    if (!ap.active || tab !== "family") return;
    const t = window.setTimeout(() => setN((x) => (x >= RUN.length ? 0 : x + 1)), n >= RUN.length ? HOLD_MS : STEP_MS);
    return () => window.clearTimeout(t);
  }, [n, ap.active, tab]);

  function onKey(e: React.KeyboardEvent) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
    e.preventDefault();
    const next = e.key === "Home" ? "family" : e.key === "End" ? "plugin" : tab === "family" ? "plugin" : "family";
    setTab(next);
    list.current?.querySelector<HTMLButtonElement>(`#ib-tab-${next}`)?.focus();
  }

  return (
    <div className="sx sx--install">
      <Reveal className="sx-title">
        <p className="kicker sx-kicker"><span className="sx-num">09</span>the bench</p>
        <h2 className="sx-h2"><span className="sx-key">One command.</span> The whole loadout.</h2>
      </Reveal>
      <Reveal className="sx-lead" delay={0.12}>
        <p>
          The family installer is the fastest way in: one interactive command that detects your
          coding-agent CLIs and installs the products you pick (garden brings wicked-vault with it).
          Prefer just this plugin? It is the second tab.
        </p>
      </Reveal>

      <div className="sx-stage ib-stage" ref={bench} {...ap.bind}>
        <div className="ib-bar">
          <div className="ib-tabs" role="tablist" aria-label="how to install" ref={list} onKeyDown={onKey}>
            {TABS.map((t) => (
              <button
                key={t.id}
                id={`ib-tab-${t.id}`}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                aria-controls={`ib-panel-${t.id}`}
                tabIndex={tab === t.id ? 0 : -1}
                className={`ib-tab${tab === t.id ? " is-on" : ""}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <PlayToggle paused={ap.paused} onToggle={ap.toggle} label="the installer steps" />
        </div>
        <div className="ib-panels">
          <div id="ib-panel-family" role="tabpanel" aria-labelledby="ib-tab-family" className={`ib-panel${tab === "family" ? "" : " is-off"}`} aria-hidden={tab !== "family"} inert={tab !== "family"}>
            <div className="ib-step">
              <div className="ib-step-head">
                <span className="ib-step-num" aria-hidden>01</span>
                <span className="ib-step-label">the family installer · recommended</span>
              </div>
              <CopyChip text="npx wicked-installer" label="copy" />
              <ol className="ib-run" aria-label="what the installer does">
                {RUN.map((x, k) => (
                  <li key={x} className={`ib-run-step${k < n ? " is-done" : k === n ? " is-now" : ""}`}>
                    <span className="ib-run-mark" aria-hidden>{k < n ? "✓" : k === n ? "›" : "·"}</span>
                    <span className="ib-run-t">{x}</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
          <div id="ib-panel-plugin" role="tabpanel" aria-labelledby="ib-tab-plugin" className={`ib-panel${tab === "plugin" ? "" : " is-off"}`} aria-hidden={tab !== "plugin"} inert={tab !== "plugin"}>
            {DIRECT.map((step, i) => (
              <div key={step.id} className="ib-step">
                <div className="ib-step-head">
                  <span className="ib-step-num" aria-hidden>{String(i + 1).padStart(2, "0")}</span>
                  <span className="ib-step-label">{step.label}</span>
                </div>
                <CopyChip text={step.cmd} />
              </div>
            ))}
          </div>
        </div>
        {/* Version stamp injected at build time from .claude-plugin/plugin.json
            via astro.config.mjs (vite define) — never hardcode it here. (DT-7) */}
        <p className="ib-foot">MIT · open-source · v{__WICKED_GARDEN_VERSION__} · local-first: memory, evidence and the code graph stay in local files, with no server to run.</p>
      </div>

      <nav className="ib-recap" aria-labelledby="ib-recap-h">
        <p className="ib-recap-h" id="ib-recap-h"><b>Then, in your agent:</b> the retry change, checked the ways above.</p>
        <ol className="ib-recap-list">
          {RECAP.map((r, k) => (
            <li key={r.href} style={{ "--k": k } as React.CSSProperties}>
              <a className="ib-rc" href={r.href}>
                <span className="ib-rc-n" aria-hidden>{r.n}</span>
                <span className="ib-rc-t">{r.t}</span>
                <code className="ib-rc-c">{r.c}</code>
              </a>
            </li>
          ))}
        </ol>
      </nav>
    </div>
  );
}
