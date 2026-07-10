import Reveal from "./Reveal";
import CopyChip from "./CopyChip";

/* ============================================================================
   The Bench — install. Primary: the family installer (npx wicked-installer).
   Secondary: install wicked-garden directly as a Claude Code plugin.
============================================================================ */

const DIRECT = [
  { id: "marketplace", cmd: "claude plugins marketplace add mikeparcewski/wicked-garden", label: "add from marketplace" },
  { id: "install", cmd: "claude plugins install wicked-garden", label: "install the plugin" },
] as const;

export default function InstallBench() {
  return (
    <div className="mx-auto w-full max-w-[1240px] px-5 sm:px-8">
      <Reveal>
        <p className="kicker">04 / the bench</p>
        <h2 className="ib-h2">One command. The whole loadout.</h2>
        <p className="ib-intro">
          The family installer is the fastest way in — one interactive command that picks
          your products across every CLI and installs the shared{" "}
          <span className="font-mono text-ink">wicked</span> CLI. Prefer just this plugin?
          The direct path is right below.
        </p>
      </Reveal>

      <Reveal delay={0.08}>
        <div className="ib-primary">
          <div className="ib-primary-head">
            <span className="ib-primary-num" aria-hidden>01</span>
            <span className="ib-primary-label">the family installer · recommended</span>
          </div>
          <CopyChip text="npx wicked-installer" label="copy" />
          <p className="ib-primary-note">interactive · picks your products across CLIs · ships the wicked CLI</p>
        </div>
      </Reveal>

      <Reveal delay={0.14}>
        <p className="ib-or">or install just wicked-garden directly</p>
        <div className="ib-direct">
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
        <p className="ib-foot">MIT · open-source · v12.27.0 · local-first — nothing leaves your machine.</p>
      </Reveal>
    </div>
  );
}
