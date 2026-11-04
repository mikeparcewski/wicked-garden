import { useEffect, useRef, useState } from "react";
import Reveal from "./Reveal";
import CopyChip from "./CopyChip";
import PlayToggle from "./PlayToggle";
import { useAutoplay } from "./useAutoplay";
import { focusFromKey } from "./focusFromKey";
import { PACKS } from "../../data/garden";

/* ============================================================================
   BUILD ON IT — the extension pitch. Garden is a catalog with an open naming
   contract: ship your own domain pack and it sits beside the built-ins, under the
   same evidence discipline. The bench cycles three example packs (fintech-risk,
   games-QA, compliance) by itself; each pick retypes the pack's four rows and each
   rule lights as its row lands. Picking one takes over; it pauses on hover, on
   focus and off-screen, and starts paused under reduced motion.
   Grounded claims (README "Build on it", docs/extending.md, scripts/pack/check.py):
   - a wicked-pack.json manifest; one user-invocable {vendor}-{domain} router;
     {vendor}-{domain}-{role} workers that declare metadata.role: worker;
     kebab-case SKILL.md names, ≤64 chars;
   - `npx wicked-garden pack check <dir>` is the shipped conformance gate;
   - a pack can call the same proof gate, which fails closed when it cannot run.
   The pack names are examples.
============================================================================ */

const RULES = [
  {
    n: "01",
    t: "one router per domain",
    d: "A single user-invocable skill fronts the domain and routes its actions — the same shape as qe, mem, and product.",
  },
  {
    n: "02",
    t: "{vendor}-{domain}-{role} workers",
    d: "Each specialist is its own skill that declares metadata.role: worker, routed by your domain’s router: the same shape as the 40 qe-* specialists.",
  },
  {
    n: "03",
    t: "evidence via vault",
    d: "Your pack can call the same proof gate: its claims are re-derived against wicked-vault, and the gate fails closed when it cannot run.",
  },
];

/** the row count at which each rule lights (the router row, the first worker, the last row) */
const LIGHT_AT = [2, 3, 4];
const ROW_MS = 380;
const CYCLE_MS = 4200;

export default function ExtendPack() {
  const root = useRef<HTMLDivElement>(null);
  const ap = useAutoplay(root, 0.4);
  const [pack, setPack] = useState(0);
  const [manual, setManual] = useState(false);
  const ROWS = PACKS[pack].rows.length;
  const [landed, setLanded] = useState(ROWS);
  const shown = useRef(pack);

  // retype the rows one by one after a pick. Off screen, under the visitor's Pause or under reduced motion (even
  // switched on mid-way) the rows land at once: nothing types on, and coming back does not type them again.
  useEffect(() => {
    if (!ap.live || ap.reduced || ap.paused || window.matchMedia("(prefers-reduced-motion: reduce)").matches) { shown.current = pack; setLanded(ROWS); return; }
    if (shown.current === pack) return;
    shown.current = pack;
    setLanded(0);
    const ts = Array.from({ length: ROWS }, (_, k) => window.setTimeout(() => setLanded(k + 1), (k + 1) * ROW_MS));
    return () => ts.forEach((t) => window.clearTimeout(t));
  }, [pack, ROWS, ap.live, ap.reduced, ap.paused]);

  // the idle cycle: the next example pack every few seconds, until the visitor picks one
  useEffect(() => {
    if (manual || !ap.active) return;
    const t = window.setTimeout(() => setPack((n) => (n + 1) % PACKS.length), CYCLE_MS);
    return () => window.clearTimeout(t);
  }, [pack, manual, ap.active]);

  const p = PACKS[pack];

  function pick(n: number) {
    setManual(true);
    setPack(n);
  }
  function resume() {
    setManual(false);
    ap.play();
  }

  function onRadioKey(e: React.KeyboardEvent) {
    const L = PACKS.length;
    const n = e.key === "ArrowDown" || e.key === "ArrowRight" ? (pack + 1) % L
      : e.key === "ArrowUp" || e.key === "ArrowLeft" ? (pack - 1 + L) % L
      : e.key === "Home" ? 0 : e.key === "End" ? L - 1 : -1;
    if (n < 0) return;
    e.preventDefault();
    pick(n);
    focusFromKey((e.currentTarget as HTMLElement).querySelector<HTMLButtonElement>(`[data-pack="${n}"]`));
  }

  return (
    <div className="sx sx--extend">
      <Reveal className="sx-title">
        <p className="kicker sx-kicker"><span className="sx-num">08</span>build on it</p>
        <h2 className="sx-h2">Your domain. Your pack. <span className="sx-key">Same gates.</span></h2>
      </Reveal>
      <Reveal className="sx-lead" delay={0.12}>
        <p>
          The catalog is open — the built-in domains follow a naming contract anyone can follow. Ship a
          pack with <span className="cx-em">your unique take</span> — a fintech-risk domain, a games-QA
          fleet, a compliance cast — and it sits beside the built-ins, under the same evidence discipline.
        </p>
      </Reveal>

      <div className="sx-stage xp-grid" ref={root} {...ap.bind}>
        <div className="xp-scaffold">
          <div className="xp-scaffold-bar">
            <span className="xp-scaffold-path">{p.dir}/</span>
            <span className="xp-picks" role="radiogroup" aria-label="example pack" onKeyDown={onRadioKey}>
              {PACKS.map((x, n) => (
                <button key={x.id} type="button" role="radio" aria-checked={n === pack} tabIndex={n === pack ? 0 : -1} data-pack={n}
                  className={`xp-pick${n === pack ? " is-on" : ""}`} onClick={() => pick(n)}>
                  {x.label}
                </button>
              ))}
            </span>
          </div>
          <div className="xp-scaffold-body" aria-label={`Example domain-pack layout: ${p.label}`}>
            {p.rows.map((row, k) => (
              <div key={`${p.id}-${row.dir}`} className={`xp-row${k < landed ? " is-landed" : ""}`}>
                <span className="xp-dir">{row.dir}</span>
                <span className="xp-note">{row.note}</span>
              </div>
            ))}
          </div>
          <div className="xp-scaffold-foot">
            <span className="xp-foot-text">a wicked-pack.json manifest + kebab-case SKILL.md names (≤64 chars)</span>
            <span className="xp-foot-ctl">
              {manual ? (
                <button type="button" className="pg-afford-btn" onClick={resume}>▶ resume</button>
              ) : (
                <PlayToggle paused={ap.paused} onToggle={ap.toggle} label="the pack cycle" />
              )}
            </span>
          </div>
        </div>

        <div className="xp-rules">
          {RULES.map((r, k) => (
            <div key={r.n} className={`xp-rule${landed >= LIGHT_AT[k] ? " is-lit" : ""}`}>
              <span className="xp-rule-num" aria-hidden>{r.n}</span>
              <div className="xp-rule-body">
                <span className="xp-rule-t">{r.t}</span>
                <p className="xp-rule-d">{r.d}</p>
              </div>
            </div>
          ))}
          <div className="xp-cta">
            <span className="xp-cta-label">in your pack’s directory, check it against the contract</span>
            <CopyChip text="npx wicked-garden pack check ." label="copy" />
          </div>
        </div>
      </div>
    </div>
  );
}
