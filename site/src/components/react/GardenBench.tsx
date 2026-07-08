import Reveal from "./Reveal";
import CopyChip from "./CopyChip";
import Marker from "./Marker";

/* Primary path — the whole-family installer (npx wicked-installer, npm v0.2.0).
   Interactive: picks products across CLIs and ships the `wicked` CLI. */
const INSTALLER = {
  cmd: "npx wicked-installer",
  label: "the family installer · recommended",
  note: "interactive · picks your products across CLIs · ships the wicked CLI",
} as const;

/* Secondary path — install just wicked-garden directly as a Claude Code plugin. */
const DIRECT = [
  {
    id: "marketplace",
    cmd: "claude plugins marketplace add mikeparcewski/wicked-garden",
    label: "add from marketplace",
  },
  {
    id: "install",
    cmd: "claude plugins install wicked-garden",
    label: "install the plugin",
  },
] as const;

export default function GardenBench() {
  return (
    <div className="relative mx-auto max-w-[1240px] px-5 pt-4 pb-6 sm:px-8">
      <Reveal>
        <p className="kicker">03 / the potting bench</p>
        <h2 className="mt-7 font-display text-[clamp(1.5rem,6.2vw,3.6rem)] font-extrabold leading-[1.02] tracking-tight">
          one command.{" "}
          <Marker color="var(--accent-bright)">your garden, planted.</Marker>
        </h2>
        <p className="mt-8 max-w-xl text-lg leading-relaxed text-muted">
          The family installer is the fastest way in — one interactive command that
          picks your products across every CLI and installs the shared{" "}
          <span className="font-mono text-ink">wicked</span> CLI. Prefer just this
          plugin? The direct path is right below.
        </p>
      </Reveal>

      <Reveal delay={0.08}>
        {/* Primary — the family installer */}
        <div
          className="mt-8 rounded-2xl px-4 py-4"
          style={{
            border: "1px solid var(--accent)",
            background: "color-mix(in oklab, var(--accent) 8%, transparent)",
          }}
        >
          <div className="mb-2 flex items-baseline gap-3">
            <span
              className="shrink-0 font-mono text-[0.58rem] font-bold uppercase tracking-[0.2em] text-muted"
              aria-hidden
            >
              01
            </span>
            <span
              className="font-mono text-[0.55rem] uppercase tracking-[0.16em]"
              style={{ color: "var(--accent)" }}
            >
              {INSTALLER.label}
            </span>
          </div>
          <CopyChip text={INSTALLER.cmd} />
          <p className="mt-1.5 font-mono text-[0.6rem] text-muted">{INSTALLER.note}</p>
        </div>
      </Reveal>

      <Reveal delay={0.14}>
        {/* Secondary — or install just this directly */}
        <p className="mt-8 font-mono text-[0.62rem] uppercase tracking-[0.16em] text-muted">
          or install just wicked-garden directly
        </p>
        <div className="mt-3 flex flex-col gap-3">
          {DIRECT.map((step, i) => (
            <div
              key={step.id}
              className="card-surface overflow-hidden rounded-2xl px-4 py-3"
            >
              <div className="mb-2 flex items-baseline gap-3">
                <span
                  className="shrink-0 font-mono text-[0.58rem] font-bold uppercase tracking-[0.2em] text-muted"
                  aria-hidden
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span
                  className="font-mono text-[0.55rem] uppercase tracking-[0.16em]"
                  style={{ color: "var(--c-floor)" }}
                >
                  {step.label}
                </span>
              </div>
              <CopyChip text={step.cmd} />
            </div>
          ))}
        </div>
      </Reveal>
    </div>
  );
}
