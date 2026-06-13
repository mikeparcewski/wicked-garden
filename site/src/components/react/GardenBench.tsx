import Reveal from "./Reveal";
import CopyChip from "./CopyChip";
import Marker from "./Marker";

const STEPS = [
  {
    id: "marketplace",
    num: "01",
    cmd: "claude plugins marketplace add mikeparcewski/wicked-garden",
    label: "add from marketplace",
    note: null,
  },
  {
    id: "install",
    num: "02",
    cmd: "claude plugins install wicked-garden",
    label: "install the gate",
    note: null,
  },
  {
    id: "picker",
    num: "03",
    cmd: "/wicked-garden:install",
    label: "pick your tools",
    note: "runs inside Claude Code · choose testing, memory, playbooks, bus, and more",
  },
] as const;

export default function GardenBench() {
  return (
    <div
      className="relative mx-auto max-w-[1240px] px-5 pb-6 sm:px-8"
      style={{ paddingTop: "calc(var(--topbar-h) + 1.25rem)" }}
    >
      <Reveal>
        <p className="kicker">03 / the potting bench</p>
        <h2 className="mt-5 font-display text-[clamp(2rem,4.6vw,3.6rem)] font-extrabold leading-[1.02] tracking-tight">
          three commands.{" "}
          <Marker color="var(--accent-bright)">your garden, planted.</Marker>
        </h2>
        <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted">
          wicked-garden curates the rest. The third command runs inside Claude Code — it asks which optional layers you want and installs your picks at their latest versions.
        </p>
      </Reveal>

      <Reveal delay={0.08}>
        <div className="mt-10 flex flex-col gap-3">
          {STEPS.map((step) => (
            <Step key={step.id} step={step} />
          ))}
        </div>
      </Reveal>
    </div>
  );
}

function Step({ step }: { step: (typeof STEPS)[number] }) {
  const color =
    step.id === "picker" ? "var(--accent)" : "var(--c-floor)";

  return (
    <div className="card-surface flex items-start gap-4 overflow-hidden rounded-2xl px-5 py-4 sm:gap-5">
      <span
        className="mt-0.5 shrink-0 font-mono text-[0.58rem] font-bold uppercase tracking-[0.2em] text-muted"
        aria-hidden
      >
        {step.num}
      </span>

      <div className="min-w-0 flex-1">
        <CopyChip text={step.cmd} />
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
          <span
            className="font-mono text-[0.62rem] uppercase tracking-[0.18em]"
            style={{ color }}
          >
            {step.label}
          </span>
          {step.note && (
            <span className="font-mono text-[0.6rem] text-muted">
              {step.note}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
