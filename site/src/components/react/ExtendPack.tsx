import Reveal from "./Reveal";
import CopyChip from "./CopyChip";
import { PACK_SCAFFOLD } from "../../data/garden";

/* ============================================================================
   BUILD ON IT — the extension pitch. Garden is a catalog with an open naming
   contract, not a closed product: ship your own domain pack with your unique
   take and it sits beside the built-ins, under the same evidence discipline.
   Grounded claims:
   - naming contract: kebab-case, one user-invocable router per domain,
     {vendor}-{domain}-{role} fork workers with `context: fork` — exactly how
     the in-repo domains (qe, mem, product, …) are built.
   - evidence via vault: `prove compile <repo>` stamps a self-contained,
     vault-backed evidence gate into ANY repo — it runs with no wicked-garden
     installed (README "Try it").
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

export default function ExtendPack() {
  return (
    <div className="mx-auto w-full max-w-[1240px] px-5 sm:px-8">
      <Reveal>
        <p className="kicker qw-kicker">06 / build on it</p>
        <h2 className="xp-h2">Your domain. Your pack. Same gates.</h2>
        <p className="xp-intro">
          The catalog is open — the built-in domains follow a naming contract
          anyone can follow. Ship a pack with{" "}
          <span className="qw-em">your unique take</span> — a fintech-risk
          domain, a games-QA fleet, a compliance cast — and it sits beside the
          built-ins, under the same evidence discipline.
        </p>
      </Reveal>

      <Reveal delay={0.06}>
        <div className="xp-grid">
          <div className="xp-scaffold" aria-label="Example domain-pack scaffold">
            <div className="xp-scaffold-bar"><i></i><i></i><i></i><span>skills/</span></div>
            <div className="xp-scaffold-body">
              {PACK_SCAFFOLD.map((row) => (
                <div key={row.dir} className="xp-row">
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
            {RULES.map((r) => (
              <div key={r.n} className="xp-rule">
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
      </Reveal>
    </div>
  );
}
