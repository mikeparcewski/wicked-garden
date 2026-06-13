import { useReducedMotion } from "motion/react";
import {
  PROJECTS,
  ROLES,
  TOUR,
  type Project,
  type TourStop,
} from "../../data/projects";
import CopyChip from "./CopyChip";
import Marker from "./Marker";
import Reveal from "./Reveal";
import Conveyor, { type StationDef } from "./Conveyor";

const byId: Record<string, Project> = Object.fromEntries(
  PROJECTS.map((p) => [p.id, p])
);

function colorOf(p: Project): string {
  return ROLES.find((r) => r.id === p.role)?.colorVar ?? "--accent";
}

const STATIONS: StationDef[] = TOUR.map((stop) => ({
  num: String(stop.stop).padStart(2, "0"),
  label: stop.headline.mark,
  hint: stop.kicker,
}));

const TICK_ANCHORS = TOUR.map((_, i) =>
  `${Math.round(4 + (i / (TOUR.length - 1)) * 86)}%`
);

export default function GardenTour() {
  const reduce = useReducedMotion();

  return (
    <div id="tour">
      <div className="mx-auto max-w-[1240px] px-5 pb-8 pt-28 sm:px-8 sm:pt-32">
        <Reveal>
          <p className="kicker">02 / the garden tour</p>
          <h2 className="mt-5 font-display text-[clamp(2rem,4.6vw,3.6rem)] font-extrabold leading-[1.02] tracking-tight">
            Walk the garden.{" "}
            <Marker color="var(--accent-bright)">Meet every bed.</Marker>
          </h2>
          <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted">
            Eight stops, eight tools. The first three are the foundation — the
            gate and the floor the whole garden stands on; the rest you take or
            leave. Every install is one line, right where you need it.
          </p>
        </Reveal>
      </div>

      <Conveyor
        stations={STATIONS}
        sectionLabel="Garden stops"
        tickAnchors={TICK_ANCHORS}
        reducedFallback={<TourFallback />}
      >
        {(active) => {
          const stop = TOUR[active - 1];
          return <StopContent stop={stop} isLast={stop.stop === TOUR.length} />;
        }}
      </Conveyor>
    </div>
  );
}

/* ── Stop content — shown in the conveyor's right panel ─────────────────────── */

function StopContent({ stop, isLast }: { stop: TourStop; isLast: boolean }) {
  const lead = byId[stop.tools[0]];
  const cvar = colorOf(lead);
  const tvar = cvar.replace("--c-", "--ct-");

  return (
    <div className="tour-stop-panel">
      <p className="tour-stop-kicker" style={{ color: `var(${tvar})` }}>
        {stop.kicker}
      </p>

      <h3 className="tour-stop-headline font-display">
        {stop.headline.pre}{" "}
        <span style={{ color: `var(${cvar})` }}>{stop.headline.mark}</span>
      </h3>

      <p className="tour-stop-body">{stop.body}</p>

      <div className="tour-stop-install">
        <CopyChip text={lead.install} />
      </div>

      <ul className="tour-stop-caps" aria-label="Key capabilities">
        {lead.points.slice(0, 3).map((pt) => (
          <li key={pt} className="tour-stop-cap">
            <span aria-hidden style={{ color: `var(${cvar})` }}>❋</span>
            <span>{pt}</span>
          </li>
        ))}
      </ul>

      <div className="tour-stop-action">
        {isLast ? (
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
  );
}

/* ── Reduced-motion fallback — plain list ───────────────────────────────────── */

function TourFallback() {
  return (
    <div className="mx-auto max-w-[1240px] px-5 pb-24 sm:px-8">
      {TOUR.map((stop) => {
        const lead = byId[stop.tools[0]];
        const cvar = colorOf(lead);
        const tvar = cvar.replace("--c-", "--ct-");
        return (
          <div
            key={stop.stop}
            id={`tour-stop-${stop.stop}`}
            className="border-t border-line py-12 first:border-t-0"
          >
            <p
              className="font-mono text-[0.64rem] uppercase tracking-[0.22em]"
              style={{ color: `var(${tvar})` }}
            >
              {stop.kicker}
            </p>
            <h3 className="mt-3 font-display text-[clamp(1.8rem,4vw,3rem)] font-extrabold leading-[1.02] tracking-tight">
              {stop.headline.pre}{" "}
              <span style={{ color: `var(${cvar})` }}>{stop.headline.mark}</span>
            </h3>
            <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted">
              {stop.body}
            </p>
            <div className="mt-5 max-w-md">
              <CopyChip text={lead.install} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
