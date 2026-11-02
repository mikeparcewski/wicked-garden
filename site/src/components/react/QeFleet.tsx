import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Reveal from "./Reveal";
import PlayToggle from "./PlayToggle";
import { useAutoplay } from "./useAutoplay";
import { QE_SPECIALISTS, QE_SURFACES, type Surface } from "../../data/garden";

/* ============================================================================
   THE FLEET — the 40 qe-* specialist fork skills, by orchestrator surface.
   The surface filter auto-cycles until the visitor picks one; the chosen surface's
   specialists regroup to the front and fade in where they land (a fade, not a
   slide, so no tile ever passes over another; the grid keeps all 40, so its height
   never changes). Hovering or focusing a tile writes its full name into
   a fixed caption line under the grid: no overlays. Arrow keys move between tiles.
   Phones: a segmented control and a two-column list of the chosen surface, in a
   box reserved for the largest surface.
   Every name is a real skills/qe-* dir; every specialist ships context: fork.
============================================================================ */

const ORDER: Surface[] = ["plan", "authoring", "execution", "review", "insight"];
const CYCLE_MS = 2600;

export default function QeFleet() {
  const root = useRef<HTMLDivElement>(null);
  const grid = useRef<HTMLDivElement>(null);
  const ap = useAutoplay(root, 0.35);
  const [surf, setSurf] = useState<Surface | "all">("all");
  const [manual, setManual] = useState(false);
  const [compact, setCompact] = useState(false);
  const [hot, setHot] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const first = useRef(true);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 640px)");
    const on = () => setCompact(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  // phones have no "all": the list shows one surface at a time
  const eff: Surface | "all" = compact && surf === "all" ? "plan" : surf;

  useEffect(() => {
    if (manual || !ap.active) return;
    const id = window.setTimeout(() => {
      const i = eff === "all" ? -1 : ORDER.indexOf(eff);
      const n = i + 1 >= ORDER.length ? (compact ? ORDER[0] : "all") : ORDER[i + 1];
      setSurf(n);
    }, CYCLE_MS);
    return () => window.clearTimeout(id);
  }, [eff, manual, ap.active, compact]);

  // regroup: the tiles fade in where they land, the chosen surface first (no tile crosses another)
  useLayoutEffect(() => {
    if (first.current) { first.current = false; return; }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    grid.current?.querySelectorAll<HTMLElement>(".qf-agent").forEach((el, n) => {
      el.getAnimations().forEach((x) => x.cancel());
      el.animate([{ opacity: 0, transform: "scale(0.96)" }, { opacity: 1, transform: "none" }], {
        duration: 300, delay: Math.min(n, 20) * 12, easing: "cubic-bezier(0.16, 1, 0.3, 1)", fill: "backwards",
      });
    });
  }, [eff]);

  function pick(s: Surface | "all") {
    setManual(true);
    setSurf(s);
  }
  function resume() {
    setManual(false);
    ap.play();
  }

  const list = eff === "all"
    ? QE_SPECIALISTS
    : [...QE_SPECIALISTS.filter((a) => a.s === eff), ...QE_SPECIALISTS.filter((a) => a.s !== eff)];
  const count = (k: Surface) => QE_SPECIALISTS.filter((a) => a.s === k).length;
  const surfLine = eff === "all" ? "All 40, grouped by the surface they report to." : QE_SURFACES.find((x) => x.key === eff)?.line;
  const hotAgent = hot ? QE_SPECIALISTS.find((a) => a.n === hot) : null;

  // the tiles a visitor can see (phones show one surface); the roving tab stop is always one of them
  const shownNames = (compact ? list.filter((a) => a.s === eff) : list).map((a) => a.n);
  const stop = cursor && shownNames.includes(cursor) ? cursor : shownNames[0];

  function onGridKey(e: React.KeyboardEvent) {
    const keys = ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"];
    if (!keys.includes(e.key)) return;
    e.preventDefault();
    const tiles = [...(grid.current?.querySelectorAll<HTMLButtonElement>(".qf-agent") ?? [])].filter((t) => t.offsetParent !== null);
    if (!tiles.length) return;
    const cur = tiles.findIndex((t) => t === document.activeElement);
    const cols = Math.max(1, Math.round((grid.current?.clientWidth ?? 1) / (tiles[0].offsetWidth || 1)));
    let n = cur < 0 ? 0 : cur;
    if (e.key === "ArrowRight") n += 1;
    if (e.key === "ArrowLeft") n -= 1;
    if (e.key === "ArrowDown") n += cols;
    if (e.key === "ArrowUp") n -= cols;
    if (e.key === "Home") n = 0;
    if (e.key === "End") n = tiles.length - 1;
    n = Math.max(0, Math.min(tiles.length - 1, n));
    setCursor(tiles[n].dataset.name ?? null);
    tiles[n].focus();
  }

  return (
    <div className="sx sx--fleet">
      <Reveal className="sx-title">
        <p className="kicker sx-kicker qw-kicker"><span className="sx-num">04</span>the fleet</p>
        <h2 className="sx-h2">Forty specialists. Five surfaces. One contract.</h2>
      </Reveal>
      <Reveal className="sx-lead" delay={0.04}>
        <p>
          <span className="qw-em">40 qe-* specialist skills</span> route beneath five orchestrator surfaces
          of the <code>wicked-garden-qe</code> router. Every specialist runs in an{" "}
          <span className="qw-em">isolated forked context</span>. Pick a surface — see who reports to it.
        </p>
      </Reveal>

      <div className="sx-stage" ref={root} {...ap.bind}>
        <div className="qf-bar">
          <div className="qf-filter" role="tablist" aria-label="Filter specialists by orchestrator surface">
            <button
              type="button"
              role="tab"
              className={`qf-btn qf-btn--all${eff === "all" ? " is-on" : ""}`}
              data-surf="all"
              aria-selected={eff === "all"}
              onClick={() => pick("all")}
            >
              all<span className="qf-n">{QE_SPECIALISTS.length}</span>
            </button>
            {QE_SURFACES.map((x) => (
              <button
                key={x.key}
                type="button"
                role="tab"
                className={`qf-btn${eff === x.key ? " is-on" : ""}`}
                data-surf={x.key}
                aria-selected={eff === x.key}
                onClick={() => pick(x.key)}
              >
                /{x.key}<span className="qf-n">{count(x.key)}</span>
              </button>
            ))}
          </div>
          <div className="qf-afford" data-pinned={manual}>
            <span className="qf-afford-text">{manual ? "you’re driving" : ap.paused ? "paused" : "auto-cycling"}</span>
            {manual ? (
              <button type="button" className="pg-afford-btn" onClick={resume}>▶ resume</button>
            ) : (
              <PlayToggle paused={ap.paused} onToggle={ap.toggle} label="the surface cycle" />
            )}
          </div>
        </div>

        <div
          ref={grid}
          className={`qf-grid${eff !== "all" ? " is-filtered" : ""}`}
          data-surf={eff}
          role="group"
          aria-label="the 40 specialists; arrow keys move between them"
          onKeyDown={onGridKey}
          onMouseLeave={() => setHot(null)}
        >
          {list.map((a) => {
            const match = eff !== "all" && a.s === eff;
            const off = eff !== "all" && a.s !== eff;
            return (
              <button
                key={a.n}
                type="button"
                data-name={a.n}
                aria-label={a.n}
                data-surf={a.s}
                className={`qf-agent${match ? " is-match" : ""}${off ? " is-off" : ""}${hot === a.n ? " is-hot" : ""}`}
                tabIndex={a.n === stop ? 0 : -1}
                onMouseEnter={() => setHot(a.n)}
                onFocus={() => { setHot(a.n); setCursor(a.n); }}
                onBlur={() => setHot((h) => (h === a.n ? null : h))}
                onClick={() => setHot(a.n)}
              >
                <span className="qf-agent-dot" aria-hidden />
                <span className="qf-agent-name">{a.n.replace(/^qe-/, "")}</span>
              </button>
            );
          })}
        </div>

        <p className="qf-caption" aria-live="polite">
          {hotAgent ? (
            <><code className="qf-cap-name">{hotAgent.n}</code><span className="qf-cap-surf">/{hotAgent.s}</span><span className="qf-cap-fork">context: fork</span></>
          ) : (
            <><b className="qf-cap-k">{eff === "all" ? "all surfaces" : `/${eff}`}</b>{" "}{surfLine}</>
          )}
        </p>
      </div>
    </div>
  );
}
