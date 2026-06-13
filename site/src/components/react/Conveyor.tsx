import { useState, useEffect, useRef, type ReactNode } from "react";
import { useReducedMotion } from "motion/react";

export interface StationDef {
  num: string;
  label: string;
  hint?: string;
}

interface ConveyorProps {
  stations: StationDef[];
  /** CSS top values for the crawling tick at each station */
  tickAnchors?: string[];
  /** Small eyebrow label above the station list */
  sectionLabel?: string;
  /** Content rendered in the right column — receives the 1-based active station */
  children: (activeStation: number) => ReactNode;
  /** Shown when prefers-reduced-motion or viewport is narrow */
  reducedFallback?: ReactNode;
  className?: string;
}

/**
 * Scroll-pinned conveyor: a 100vh-per-station sticky stage with a left ledger
 * rail + crawling yellow tick. Driven by IntersectionObserver on invisible
 * 100vh sentinels. CSS handles all transitions via data-station.
 */
export default function Conveyor({
  stations,
  tickAnchors,
  sectionLabel,
  children,
  reducedFallback,
  className = "",
}: ConveyorProps) {
  const reduce = useReducedMotion();
  const [active, setActive] = useState(1);
  const wrapRef = useRef<HTMLDivElement>(null);

  const n = stations.length;
  const anchors =
    tickAnchors ??
    stations.map((_, i) => `${Math.round(4 + ((i + 0.5) / n) * 80)}%`);

  useEffect(() => {
    if (reduce) return;
    const wrap = wrapRef.current;
    if (!wrap) return;

    const sentinels = wrap.querySelectorAll<HTMLElement>(".conv-sentinel");
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            const s = Number(e.target.getAttribute("data-s"));
            if (s >= 1) setActive(s);
          }
        }
      },
      { threshold: 0.5 }
    );
    sentinels.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [reduce]);

  if (reduce) {
    return reducedFallback ? <>{reducedFallback}</> : null;
  }

  return (
    <div
      ref={wrapRef}
      className={`conv-wrap ${className}`}
      style={{ height: `${n * 100}vh` }}
    >
      {/* invisible 100vh sentinels drive station changes */}
      <div className="conv-sentinels" aria-hidden="true">
        {stations.map((_, i) => (
          <div key={i} className="conv-sentinel" data-s={i + 1} />
        ))}
      </div>

      {/* the ONE sticky stage */}
      <div
        className="conv-stage"
        style={
          { "--conv-tick-y": anchors[active - 1] } as React.CSSProperties
        }
      >
        <div className="conv-inner">
          {/* left ledger rail */}
          <aside className="conv-ledger">
            {sectionLabel && (
              <div className="conv-belt-label">{sectionLabel}</div>
            )}
            <div className="conv-track">
              <span className="conv-tick" aria-hidden="true" />
              {stations.map((s, i) => (
                <div
                  key={s.num}
                  className={`conv-station${
                    i + 1 === active
                      ? " is-active"
                      : i + 1 < active
                      ? " is-past"
                      : ""
                  }`}
                >
                  <div className="conv-s-num">{s.num}</div>
                  <div className="conv-s-label">{s.label}</div>
                  {s.hint && <div className="conv-s-hint">{s.hint}</div>}
                </div>
              ))}
            </div>
          </aside>

          {/* right content */}
          <div className="conv-content">{children(active)}</div>
        </div>

        {/* bottom progress strip */}
        <div className="conv-progress-row">
          <div className="conv-progress-bar">
            <div
              className="conv-progress-fill"
              style={{ width: `${(active / n) * 100}%` }}
            />
          </div>
          <div className="conv-chapters">
            {stations.map((s, i) => (
              <span
                key={s.num}
                className={
                  i + 1 === active
                    ? "conv-ch is-active"
                    : i + 1 < active
                    ? "conv-ch is-past"
                    : "conv-ch"
                }
              >
                {s.label}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
