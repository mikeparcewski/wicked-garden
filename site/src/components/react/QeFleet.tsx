import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Reveal from "./Reveal";
import PlayToggle from "./PlayToggle";
import { useAutoplay } from "./useAutoplay";
import { QE_SPECIALISTS, QE_SURFACES, type Surface } from "../../data/garden";

/* ============================================================================
   THE FLEET — the 40 qe-* specialist skills, by the qe router action they are
   grouped under (plan, author, execute, review, insight). Each action has its own
   dot colour, on its tab and on its tiles. The filter auto-cycles until the
   visitor picks one; the chosen action's specialists regroup to the front and
   fade in where they land (a fade, not a slide: a tile passing over another is an
   animated overlap), the rest dim. The grid always holds all 40, at every size, so
   its height never changes. Hovering or focusing a tile writes its full name into
   a fixed caption line under the grid: no overlays. Arrow keys move between tiles.
   Every name is a real skills/qe-* dir.
============================================================================ */

const ORDER: Surface[] = ["plan", "author", "execute", "review", "insight"];
const CYCLE_MS = 2600;

export default function QeFleet() {
  const root = useRef<HTMLDivElement>(null);
  const grid = useRef<HTMLDivElement>(null);
  const ap = useAutoplay(root, 0.35);
  const [surf, setSurf] = useState<Surface | "all">("all");
  const [manual, setManual] = useState(false);
  const [hot, setHot] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const first = useRef(true);

  const eff = surf;

  useEffect(() => {
    if (manual || !ap.active) return;
    const id = window.setTimeout(() => {
      const i = eff === "all" ? -1 : ORDER.indexOf(eff);
      const n = i + 1 >= ORDER.length ? "all" : ORDER[i + 1];
      setSurf(n);
    }, CYCLE_MS);
    return () => window.clearTimeout(id);
  }, [eff, manual, ap.active]);

  // regroup: the tiles fade in where they land, the chosen surface first (no tile crosses another)
  useLayoutEffect(() => {
    if (first.current) { first.current = false; return; }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    // below a desktop the grid is taller than the screen: a staggered fade there blanks the rows being read
    if (window.innerWidth < 1024) return;
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
  const filter = useRef<HTMLDivElement>(null);
  const TABS: (Surface | "all")[] = ["all", ...QE_SURFACES.map((x) => x.key)];
  // one tab stop for the filter (the selected tab); arrow keys, Home and End move the selection
  function onFilterKey(e: React.KeyboardEvent) {
    const keys = ["ArrowRight", "ArrowLeft", "Home", "End"];
    if (!keys.includes(e.key)) return;
    e.preventDefault();
    const i = TABS.indexOf(eff);
    const n = e.key === "Home" ? 0 : e.key === "End" ? TABS.length - 1
      : (i + (e.key === "ArrowRight" ? 1 : -1) + TABS.length) % TABS.length;
    pick(TABS[n]);
    filter.current?.querySelector<HTMLButtonElement>(`[data-surf="${TABS[n]}"]`)?.focus();
  }
  function resume() {
    setManual(false);
    ap.play();
  }

  const list = eff === "all"
    ? QE_SPECIALISTS
    : [...QE_SPECIALISTS.filter((a) => a.s === eff), ...QE_SPECIALISTS.filter((a) => a.s !== eff)];
  const count = (k: Surface) => QE_SPECIALISTS.filter((a) => a.s === k).length;
  const surfLine = eff === "all" ? "All 40, grouped by the router action they report to." : QE_SURFACES.find((x) => x.key === eff)?.line;
  const hotAgent = hot ? QE_SPECIALISTS.find((a) => a.n === hot) : null;

  // the roving tab stop is always one of the tiles
  const shownNames = list.map((a) => a.n);
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
        <h2 className="sx-h2"><span className="sx-key">Forty specialists,</span> five actions, one router.</h2>
      </Reveal>
      <Reveal className="sx-lead" delay={0.12}>
        <p>
          <span className="qw-em">40 qe-* specialist skills</span>, grouped under five actions of the{" "}
          <code>wicked-garden-qe</code> router. Pick an action to see who reports to it.
        </p>
      </Reveal>

      <div className="sx-stage" ref={root} {...ap.bind}>
        <div className="qf-bar">
          <div className="qf-filter" role="tablist" aria-label="Filter specialists by router action" ref={filter} onKeyDown={onFilterKey}>
            <button
              type="button"
              role="tab"
              className={`qf-btn qf-btn--all${eff === "all" ? " is-on" : ""}`}
              data-surf="all"
              aria-selected={eff === "all"}
              tabIndex={eff === "all" ? 0 : -1}
              onClick={() => pick("all")}
            >
              all{" "}<span className="qf-n">{QE_SPECIALISTS.length}</span>
            </button>
            {QE_SURFACES.map((x) => (
              <button
                key={x.key}
                type="button"
                role="tab"
                className={`qf-btn${eff === x.key ? " is-on" : ""}`}
                data-surf={x.key}
                aria-selected={eff === x.key}
                tabIndex={eff === x.key ? 0 : -1}
                onClick={() => pick(x.key)}
              >
                <span className="qf-btn-dot" aria-hidden />{x.key}{" "}<span className="qf-n">{count(x.key)}</span>
              </button>
            ))}
          </div>
          <div className="qf-afford" data-pinned={manual}>
            <span className="qf-afford-text">{manual ? "you’re driving" : ap.paused ? "paused" : "auto-cycling"}</span>
            {manual ? (
              <button type="button" className="pg-afford-btn" onClick={resume}>▶ resume</button>
            ) : (
              <PlayToggle paused={ap.paused} onToggle={ap.toggle} label="the action cycle" />
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
            <><code className="qf-cap-name">{hotAgent.n}</code><span className="qf-cap-surf">qe {hotAgent.s}</span></>
          ) : (
            <><b className="qf-cap-k">{eff === "all" ? "all five actions" : `qe ${eff}`}</b>{" "}{surfLine}</>
          )}
        </p>
      </div>
    </div>
  );
}
