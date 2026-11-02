import { useRef, useState } from "react";
import Reveal from "./Reveal";
import CopyChip from "./CopyChip";

/* ============================================================================
   The Bench — install, as two tabs so it fits one frame: the family installer
   (recommended: npx wicked-installer) or just this plugin (the two Claude Code
   plugin steps). Both panels share one reserved cell, so switching never moves
   the page.
============================================================================ */

const DIRECT = [
  { id: "marketplace", cmd: "claude plugins marketplace add mikeparcewski/wicked-garden", label: "add from marketplace" },
  { id: "install", cmd: "claude plugins install wicked-garden", label: "install the plugin" },
] as const;

const TABS = [
  { id: "family", label: "family installer (recommended)" },
  { id: "plugin", label: "just this plugin" },
] as const;

export default function InstallBench() {
  const [tab, setTab] = useState<"family" | "plugin">("family");
  const list = useRef<HTMLDivElement>(null);

  function onKey(e: React.KeyboardEvent) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
    e.preventDefault();
    const next = tab === "family" ? "plugin" : "family";
    setTab(next);
    list.current?.querySelector<HTMLButtonElement>(`#ib-tab-${next}`)?.focus();
  }

  return (
    <div className="sx sx--install">
      <Reveal className="sx-title">
        <p className="kicker sx-kicker"><span className="sx-num">09</span>the bench</p>
        <h2 className="sx-h2">One command. The whole loadout.</h2>
      </Reveal>
      <Reveal className="sx-lead" delay={0.04}>
        <p>
          The family installer is the fastest way in — one interactive command that picks your products
          across every CLI and installs the shared <code>wicked</code> CLI. Prefer just this plugin? It is
          the second tab.
        </p>
      </Reveal>

      <div className="sx-stage ib-stage">
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
        <div className="ib-panels">
          <div id="ib-panel-family" role="tabpanel" aria-labelledby="ib-tab-family" className={`ib-panel${tab === "family" ? "" : " is-off"}`} aria-hidden={tab !== "family"} inert={tab !== "family"}>
            <div className="ib-step">
              <div className="ib-step-head">
                <span className="ib-step-num" aria-hidden>01</span>
                <span className="ib-step-label">the family installer · recommended</span>
              </div>
              <CopyChip text="npx wicked-installer" label="copy" />
              <p className="ib-note">interactive · picks your products across CLIs · ships the wicked CLI</p>
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
        <p className="ib-foot">MIT · open-source · v{__WICKED_GARDEN_VERSION__} · local-first — nothing leaves your machine.</p>
      </div>
    </div>
  );
}
