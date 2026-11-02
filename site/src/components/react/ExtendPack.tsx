import { useEffect, useRef, useState } from "react";
import Reveal from "./Reveal";
import CopyChip from "./CopyChip";
import { PACKS } from "../../data/garden";

/* ============================================================================
   BUILD ON IT — the extension pitch. Garden is a catalog with an open naming
   contract: ship your own domain pack and it sits beside the built-ins, under the
   same evidence discipline. Pick a pack (fintech-risk, games-QA, compliance) and
   the skills/ scaffold retypes its three rows; each rule lights as its row lands.
   Grounded claims:
   - naming contract: kebab-case, one user-invocable router per domain,
     {vendor}-{domain}-{role} fork workers with `context: fork` — exactly how
     the in-repo domains (qe, mem, product, …) are built.
   - evidence via vault: `prove compile <repo>` stamps a self-contained,
     vault-backed evidence gate into ANY repo — it runs with no wicked-garden
     installed (README "Try it").
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
    d: "Specialists are fork skills (context: fork) — isolated subagent contexts with their own tool boundaries.",
  },
  {
    n: "03",
    t: "evidence via vault",
    d: "Your pack’s “done” goes through the same gate: claims are re-derived against wicked-vault, never asserted.",
  },
];

const ROW_MS = 420;

export default function ExtendPack() {
  const [pack, setPack] = useState(0);
  const [landed, setLanded] = useState(3);
  const first = useRef(true);

  // retype the rows one by one after a pick (instant under reduced motion)
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setLanded(3); return; }
    setLanded(0);
    const ts = [1, 2, 3].map((k) => window.setTimeout(() => setLanded(k), k * ROW_MS));
    return () => ts.forEach((t) => window.clearTimeout(t));
  }, [pack]);

  const p = PACKS[pack];

  return (
    <div className="sx sx--extend">
      <Reveal className="sx-title">
        <p className="kicker sx-kicker"><span className="sx-num">08</span>build on it</p>
        <h2 className="sx-h2">Your domain. Your pack. Same gates.</h2>
      </Reveal>
      <Reveal className="sx-lead" delay={0.04}>
        <p>
          The catalog is open — the built-in domains follow a naming contract anyone can follow. Ship a
          pack with <span className="cx-em">your unique take</span> — a fintech-risk domain, a games-QA
          fleet, a compliance cast — and it sits beside the built-ins, under the same evidence discipline.
        </p>
      </Reveal>

      <div className="sx-stage xp-grid">
        <div className="xp-scaffold">
          <div className="xp-scaffold-bar">
            <span className="xp-scaffold-path">skills/</span>
            <span className="xp-picks" role="radiogroup" aria-label="example pack">
              {PACKS.map((x, n) => (
                <button key={x.id} type="button" role="radio" aria-checked={n === pack}
                  className={`xp-pick${n === pack ? " is-on" : ""}`} onClick={() => setPack(n)}>
                  {x.label}
                </button>
              ))}
            </span>
          </div>
          <div className="xp-scaffold-body" aria-label={`Example domain-pack scaffold: ${p.label}`}>
            {p.rows.map((row, k) => (
              <div key={`${p.id}-${row.dir}`} className={`xp-row${k < landed ? " is-landed" : ""}`}>
                <span className="xp-dir">{row.dir}</span>
                <span className="xp-note">{row.note}</span>
              </div>
            ))}
          </div>
          <div className="xp-scaffold-foot">
            kebab-case · ≤64 chars · SKILL.md frontmatter — that’s the whole contract
          </div>
        </div>

        <div className="xp-rules">
          {RULES.map((r, k) => (
            <div key={r.n} className={`xp-rule${k < landed ? " is-lit" : ""}`}>
              <span className="xp-rule-num" aria-hidden>{r.n}</span>
              <div className="xp-rule-body">
                <span className="xp-rule-t">{r.t}</span>
                <p className="xp-rule-d">{r.d}</p>
              </div>
            </div>
          ))}
          <div className="xp-cta">
            <span className="xp-cta-label">stamp the evidence gate into any repo — no garden required</span>
            <CopyChip text="wicked-garden-prove compile ~/path/to/repo --trigger ci" label="copy" />
          </div>
        </div>
      </div>
    </div>
  );
}
