import { PROJECTS, ROLES, TOUR, type Project, type TourStop } from "../../data/projects";
import CopyChip from "./CopyChip";
import Marker from "./Marker";
import Reveal from "./Reveal";

const byId: Record<string, Project> = Object.fromEntries(PROJECTS.map((p) => [p.id, p]));

function colorOf(p: Project): string {
  return ROLES.find((r) => r.id === p.role)?.colorVar ?? "--accent";
}

export default function GardenTour() {
  return (
    <div className="relative mx-auto max-w-[1240px] px-5 py-28 sm:px-8 sm:py-32">
      <Reveal>
        <p className="kicker">02 / the garden tour</p>
        <h2 className="mt-5 font-display text-[clamp(2rem,4.6vw,3.6rem)] font-extrabold leading-[1.02] tracking-tight">
          Walk the garden. <Marker color="var(--accent-bright)">Meet every bed.</Marker>
        </h2>
        <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted">
          Eight stops, eight tools. The first three are the foundation — the gate and the
          floor the whole garden stands on; the rest you take or leave. Every install is
          one line, right where you need it.
        </p>
      </Reveal>

      <div className="mt-8">
        {TOUR.map((stop, i) => (
          <Stop key={stop.stop} stop={stop} index={i} />
        ))}
      </div>
    </div>
  );
}

function Stop({ stop, index }: { stop: TourStop; index: number }) {
  const tools = stop.tools.map((id) => byId[id]);
  const lead = tools[0];
  const cvar = colorOf(lead);
  const tvar = cvar.replace("--c-", "--ct-");
  const last = stop.stop === TOUR.length;

  return (
    <section id={`tour-stop-${stop.stop}`} className="border-t border-line py-14 first:border-t-0 sm:py-16">
      <Reveal delay={0.04 * Math.min(index, 3)}>
        <p className="kicker" style={{ color: `var(${tvar})` }}>
          {stop.kicker}
        </p>
        <h3 className="mt-4 font-display text-[clamp(1.9rem,4.8vw,3.8rem)] font-extrabold leading-[1.0] tracking-tight">
          {stop.headline.pre} <Marker color={`var(${cvar})`}>{stop.headline.mark}</Marker>
        </h3>

        <div className="mt-6 grid grid-cols-1 gap-x-12 gap-y-8 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <p className="text-base leading-relaxed text-muted sm:text-lg">{stop.body}</p>
            <div className="mt-6 max-w-md">
              <CopyChip text={lead.install} />
            </div>
            <div className="mt-6">
              {last ? (
                <a
                  href="#bench"
                  className="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-3 font-mono text-[0.74rem] font-semibold uppercase tracking-[0.12em] text-on-accent transition-transform duration-300 hover:-translate-y-0.5"
                  style={{ boxShadow: "0 10px 32px -12px var(--accent)" }}
                >
                  build your garden →
                </a>
              ) : (
                <a
                  href={`#tour-stop-${stop.stop + 1}`}
                  className="inline-flex items-center gap-2 rounded-full border border-line-strong px-5 py-3 font-mono text-[0.74rem] uppercase tracking-[0.12em] text-ink transition-colors hover:border-accent hover:text-accent"
                >
                  next stop →
                </a>
              )}
            </div>
          </div>
          <div className="flex flex-col gap-8 lg:col-span-6">
            {tools.map((p) => (
              <ToolPanel key={p.id} p={p} cvar={cvar} tvar={tvar} />
            ))}
          </div>
        </div>
      </Reveal>
    </section>
  );
}

/** Stylized capabilities + use-cases list for one tool — the right rail of a stop. */
function ToolPanel({ p, cvar, tvar }: { p: Project; cvar: string; tvar: string }) {
  return (
    <div className="border-l-2 pl-5 sm:pl-6" style={{ borderColor: `var(${cvar})` }}>
      <p className="font-display text-xl font-extrabold tracking-tight">
        <span className="text-muted">wicked-</span>
        <span style={{ color: `var(${cvar})` }}>{p.short}</span>
      </p>
      <p className="mt-1 font-mono text-[0.66rem] uppercase tracking-[0.16em]" style={{ color: `var(${tvar})` }}>
        {p.kicker}
      </p>

      <p className="mt-4 font-mono text-[0.62rem] uppercase tracking-[0.24em] text-muted">capabilities</p>
      <ul className="mt-2 space-y-1.5">
        {p.points.map((pt) => (
          <li key={pt} className="flex gap-2.5 text-[0.86rem] leading-snug text-ink/80 dark:text-ink/85">
            <span aria-hidden className="mt-[0.06em] shrink-0 select-none" style={{ color: `var(${cvar})` }}>
              ❋
            </span>
            <span>{pt}</span>
          </li>
        ))}
      </ul>

      <p className="mt-4 font-mono text-[0.62rem] uppercase tracking-[0.24em] text-muted">use it for</p>
      <ul className="mt-2 space-y-1.5">
        {p.uses.map((u) => (
          <li key={u} className="flex gap-2.5 text-[0.86rem] italic leading-snug text-muted">
            <span aria-hidden className="mt-[0.06em] shrink-0 select-none not-italic" style={{ color: `var(${tvar})` }}>
              →
            </span>
            <span>{u}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
