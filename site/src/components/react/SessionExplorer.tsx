import { useState, useEffect, useLayoutEffect, useRef } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { PROJECTS, ROLES, TOUR, type Project, type TourStop } from "../../data/projects";
import CopyChip from "./CopyChip";
import Marker from "./Marker";
import Reveal from "./Reveal";

const ease = [0.16, 1, 0.3, 1] as const;

/* Site screenshots for the packages that have a deployed GitHub-Pages site.
   Used in the mobile / reduced-motion list so a tool with a real site shows it. */
const BASE = (import.meta.env.BASE_URL || "/").replace(/\/+$/, "");
const SITE_SHOTS: Record<string, { shot: string; url: string }> = {
  "wicked-garden": { shot: `${BASE}/screenshots/wicked-garden.png`, url: "wg.wickedagile.com" },
  "wicked-interactive": { shot: `${BASE}/screenshots/wicked-interactive.png`, url: "wi.wickedagile.com" },
  "wicked-estate": { shot: `${BASE}/screenshots/wicked-estate.png`, url: "we.wickedagile.com" },
};

/* On phones the scroll-jacked 700vh stage is collapsed to the clean list. */
function useIsNarrow(query = "(max-width: 767px)") {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const update = () => setNarrow(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, [query]);
  return narrow;
}

/* ── Session log definition ─────────────────────────────────────────────── */

interface LogLine {
  id: string;
  toolId: string | null;
  label: string;
  color: string | null;
  text: string;
  isResult?: boolean;
}

const LOG: LogLine[] = [
  {
    id: "prompt",
    toolId: null,
    label: "prompt",
    color: null,
    text: '"refactor auth middleware — session tokens leaking into logs"',
  },
  {
    id: "garden",
    toolId: "wicked-garden",
    label: "garden",
    color: "var(--accent)",
    text: "BUILD archetype · 4 phases · evidence-gated",
  },
  {
    id: "brain",
    toolId: "wicked-brain",
    label: "brain",
    color: "var(--c-workflow)",
    text: "3 memories surfaced · auth PR · INC-42 · session.ts types",
  },
  {
    id: "understanding",
    toolId: "wicked-understanding",
    label: "understanding",
    color: "var(--c-workflow)",
    text: "playbook loaded · auth pattern · 2 gotchas flagged",
  },
  {
    id: "loom",
    toolId: "wicked-loom",
    label: "loom",
    color: "var(--c-foundation)",
    text: "gate open · evidence required before phase 2 unlocks",
  },
  {
    id: "vault",
    toolId: "wicked-vault",
    label: "vault",
    color: "var(--c-foundation)",
    text: "recording · run-id: 4f2a · hash: a3f7b2c1",
  },
  {
    id: "testing",
    toolId: "wicked-testing",
    label: "testing",
    color: "var(--c-creation)",
    text: "3 verdicts · PASS · evaluator ≠ implementer · re-derived",
  },
  {
    id: "bus",
    toolId: "wicked-bus",
    label: "bus",
    color: "var(--c-layer)",
    text: "7 events published · phase.start · evidence.record · gate.check",
  },
  {
    id: "gate-passed",
    toolId: null,
    label: "loom",
    color: "var(--accent)",
    text: "GATE PASSED · proven, not self-reported ✓",
    isResult: true,
  },
];

const TOOL_LINES = LOG.filter((l) => l.toolId !== null && !l.isResult);

/* ── Helpers ────────────────────────────────────────────────────────────── */

const byId: Record<string, Project> = Object.fromEntries(
  PROJECTS.map((p) => [p.id, p])
);

function colorOf(p: Project): string {
  return ROLES.find((r) => r.id === p.role)?.colorVar ?? "--accent";
}

function stopFor(toolId: string): TourStop | undefined {
  return TOUR.find((s) => s.tools.includes(toolId));
}

/* ── Main component ─────────────────────────────────────────────────────── */

export default function SessionExplorer() {
  const reduce = useReducedMotion();
  const isNarrow = useIsNarrow();
  const [activeIdx, setActiveIdx] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const hiddenRef = useRef<HTMLDivElement>(null);

  // Pre-measure all panel heights at mount so the layout never shifts on tool switches.
  // Log content is static → measure once. Right column → pre-render all detail panels
  // invisibly (position:absolute inside se-right), find the tallest, lock to that × 1.15.
  useLayoutEffect(() => {
    const logEl = logRef.current;
    if (logEl) logEl.style.height = `${logEl.scrollHeight * 1.15}px`;

    const hiddenEl = hiddenRef.current;
    const rightEl = rightRef.current;
    if (!hiddenEl || !rightEl) return;
    let maxH = 0;
    hiddenEl.querySelectorAll<HTMLElement>(".se-detail").forEach((el) => {
      maxH = Math.max(maxH, el.scrollHeight);
    });
    if (maxH > 0) rightEl.style.height = `${maxH * 1.15}px`;
  }, []);

  useEffect(() => {
    if (reduce) return;
    const wrap = wrapRef.current;
    if (!wrap) return;
    const sentinels = wrap.querySelectorAll<HTMLElement>(".se-sentinel");
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            const idx = Number(e.target.getAttribute("data-idx"));
            if (!isNaN(idx)) setActiveIdx(idx);
          }
        }
      },
      { threshold: 0.5 }
    );
    sentinels.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [reduce]);

  const activeLine = TOOL_LINES[activeIdx];
  const activeId = activeLine?.toolId ?? TOOL_LINES[0].toolId!;
  const project = byId[activeId];
  const stop = stopFor(activeId);
  const cvar = project ? colorOf(project) : "--accent";
  const tvar = cvar.replace("--c-", "--ct-");

  if (reduce || isNarrow) {
    return <FallbackList />;
  }

  return (
    <div
      ref={wrapRef}
      className="se-wrap"
      style={{ height: `${TOOL_LINES.length * 100}vh` }}
    >
      {/* invisible sentinels — each 100vh, each a scroll-snap point */}
      <div className="se-sentinels" aria-hidden="true">
        {TOOL_LINES.map((line, i) => (
          <div key={line.id} className="se-sentinel" data-idx={i} />
        ))}
      </div>

      {/* sticky stage — fills one viewport */}
      <div className="se-stage">
        <div className="se-content">
          {/* ── Full-width header: kicker + h2 + intro ── */}
          <div className="se-full">
            <p className="kicker">02 / in practice</p>
            <h2 className="se-stage-h2 font-display">
              One prompt.{" "}
              <Marker color="var(--accent-bright)">Seven tools firing.</Marker>
            </h2>
            <p className="se-stage-intro">
              Scroll through a real refactor session — every garden tool doing its part, triggered by a single prompt. Click any log line to jump to that tool.
            </p>
          </div>

          {/* ── Left col: terminal log ── */}
          <div ref={logRef} className="se-log">
            <div className="se-chrome" aria-hidden="true">● ● ●</div>
            {LOG.map((line, i) => {
              const isActive = line.toolId === activeId && !line.isResult;
              const isClickable = line.toolId !== null && !line.isResult;

              function handleClick() {
                if (!isClickable) return;
                const idx = TOOL_LINES.findIndex((l) => l.toolId === line.toolId);
                if (idx >= 0) setActiveIdx(idx);
              }

              return (
                <div
                  key={line.id}
                  className={`se-line${isActive ? " is-active" : ""}${line.isResult ? " is-result" : ""}`}
                  onClick={isClickable ? handleClick : undefined}
                  style={{ cursor: isClickable ? "pointer" : "default" }}
                  aria-current={isActive ? "true" : undefined}
                >
                  {line.color ? (
                    <span
                      className="se-pill"
                      style={{
                        color: line.color,
                        background: `color-mix(in oklab, ${line.color} 14%, transparent)`,
                      }}
                    >
                      {line.label}
                    </span>
                  ) : (
                    <span className="se-pill se-pill--prompt">{line.label}</span>
                  )}
                  <span
                    className={`se-text${line.isResult ? " se-text--pass" : ""}${line.id === "prompt" ? " se-text--prompt" : ""}`}
                  >
                    {line.text}
                  </span>
                </div>
              );
            })}
          </div>

          {/* ── Right col: tool detail ── */}
          <div ref={rightRef} className="se-right">
            {/* Hidden pre-render of all panels — measures max height at mount, then inert */}
            <div ref={hiddenRef} className="se-hidden-measure" aria-hidden="true">
              {TOOL_LINES.map((line) => {
                if (!line.toolId) return null;
                const proj = byId[line.toolId];
                const stop = stopFor(line.toolId);
                if (!proj || !stop) return null;
                const cv = colorOf(proj);
                const tv = cv.replace("--c-", "--ct-");
                return (
                  <div key={line.toolId} className="se-detail">
                    <p className="se-detail-kicker" style={{ color: `var(${tv})` }}>{stop.kicker}</p>
                    <h3 className="se-detail-headline font-display">
                      {stop.headline.pre}{" "}
                      <span style={{ color: `var(${cv})` }}>{stop.headline.mark}</span>
                    </h3>
                    <p className="se-detail-body">{stop.body}</p>
                    <div className="se-detail-install"><CopyChip text={proj.install} /></div>
                    <ul className="se-detail-caps">
                      {proj.points.slice(0, 3).map((pt) => (
                        <li key={pt} className="se-detail-cap">
                          <span aria-hidden style={{ color: `var(${cv})` }}>❋</span>
                          <span>{pt}</span>
                        </li>
                      ))}
                    </ul>
                    <p className="se-detail-unlock" style={{ color: `var(${cv})` }}>{stop.unlock}</p>
                  </div>
                );
              })}
            </div>

            <AnimatePresence mode="wait">
              {project && stop ? (
                <motion.div
                  key={activeId}
                  className="se-detail"
                  initial={{ opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.32, ease }}
                >
                  <p className="se-detail-kicker" style={{ color: `var(${tvar})` }}>
                    {stop.kicker}
                  </p>
                  <h3 className="se-detail-headline font-display">
                    {stop.headline.pre}{" "}
                    <span style={{ color: `var(${cvar})` }}>{stop.headline.mark}</span>
                  </h3>
                  <p className="se-detail-body">{stop.body}</p>
                  <div className="se-detail-install">
                    <CopyChip text={project.install} />
                  </div>
                  <ul className="se-detail-caps">
                    {project.points.slice(0, 3).map((pt) => (
                      <li key={pt} className="se-detail-cap">
                        <span aria-hidden style={{ color: `var(${cvar})` }}>❋</span>
                        <span>{pt}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="se-detail-unlock" style={{ color: `var(${cvar})` }}>
                    {stop.unlock}
                  </p>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>
        </div>

        {/* scroll progress */}
        <div className="se-progress-row">
          {TOOL_LINES.map((line, i) => (
            <div
              key={line.id}
              className={`se-progress-dot${i === activeIdx ? " is-active" : i < activeIdx ? " is-past" : ""}`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Reduced-motion fallback ─────────────────────────────────────────────── */

function FallbackList() {
  return (
    <div id="session" className="mx-auto max-w-[1240px] px-5 py-12 sm:px-8 sm:py-20">
      <p className="kicker">02 / in practice</p>
      <h2 className="mt-4 font-display text-[clamp(2rem,4.6vw,3.6rem)] font-extrabold leading-[1.02] tracking-tight">
        One prompt. Seven tools firing.
      </h2>
      <div className="mt-12 space-y-10">
        {TOOL_LINES.map((line) => {
          const project = byId[line.toolId!];
          const stop = stopFor(line.toolId!);
          if (!project || !stop) return null;
          const cvar = colorOf(project);
          const tvar = cvar.replace("--c-", "--ct-");
          const site = SITE_SHOTS[project.id];
          return (
            <div key={line.id} className="border-t border-line pt-10 first:border-t-0 first:pt-0">
              <p
                className="font-mono text-[0.65rem] uppercase tracking-[0.2em]"
                style={{ color: `var(${tvar})` }}
              >
                {stop.kicker}
              </p>
              <h3 className="mt-3 font-display text-[clamp(1.6rem,3.5vw,2.6rem)] font-extrabold leading-[1.04]">
                {stop.headline.pre}{" "}
                <span style={{ color: `var(${cvar})` }}>{stop.headline.mark}</span>
              </h3>
              <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted">{stop.body}</p>
              <div className="mt-5 max-w-md">
                <CopyChip text={project.install} />
              </div>
              {site && (
                <a
                  href={`https://${site.url}`}
                  className="mt-6 block max-w-xl overflow-hidden rounded-xl border border-line"
                >
                  <img
                    src={site.shot}
                    alt={`${project.id} — live site`}
                    loading="lazy"
                    className="block w-full"
                    style={{ aspectRatio: "16 / 10", objectFit: "cover", objectPosition: "top center" }}
                  />
                  <span className="block px-3 py-2 font-mono text-[0.62rem] tracking-wide text-muted">
                    {site.url} ↗
                  </span>
                </a>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
