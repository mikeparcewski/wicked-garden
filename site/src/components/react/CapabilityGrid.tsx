import Reveal from "./Reveal";
import { DOMAINS, PEERS, HUE_VAR, type Domain } from "../../data/garden";

/* ============================================================================
   The Grid — the breadth the six signature tools only sample.
   Every command shown is a real slash command in the repo (commands/<domain>/).
   Honest counts: 81 commands across these domains, 10 work-shapes, 23 agents.
   Folds in the "one install bundles the wicked-* family" point (was the Shelf)
   as a compact strip at the foot — vault is the one required floor, the rest
   opt-in layers.
============================================================================ */

function DomainCard({ d }: { d: Domain }) {
  return (
    <div className="cg-card" style={{ ["--hue" as string]: `var(${HUE_VAR[d.hue]})` }}>
      <div className="cg-card-head">
        <span className="cg-card-name">{d.name}</span>
        <span className="cg-card-count">{d.count} {d.count === 1 ? "cmd" : "cmds"}</span>
      </div>
      <p className="cg-card-blurb">{d.blurb}</p>
      <div className="cg-card-cmds">
        {d.cmds.map((c) => (
          <span key={c} className="cg-chip">{c}</span>
        ))}
      </div>
    </div>
  );
}

export default function CapabilityGrid() {
  return (
    <div className="mx-auto w-full max-w-[1240px] px-5 sm:px-8">
      <Reveal>
        <p className="kicker">03 / the whole toolkit</p>
        <h2 className="cg-h2">Six tools were the sample. Here’s the rest.</h2>
        <p className="cg-intro">
          The toolbox shows the signature gap-fillers. Underneath sits the full
          surface — <span className="cg-em">81 slash commands</span> across ten domains and{" "}
          <span className="cg-em">23 specialist agents</span>, all reading the same
          evidence-first discipline. Everything below is real and in the repo today.
        </p>
      </Reveal>

      <Reveal delay={0.06}>
        <div className="cg-grid">
          {DOMAINS.map((d) => (
            <DomainCard key={d.id} d={d} />
          ))}
        </div>
      </Reveal>

      <Reveal delay={0.1}>
        <div className="cg-family">
          <p className="cg-family-lead">
            <span className="cg-family-em">One install bundles the family.</span> The gate
            stands on one required floor — <b>wicked-vault</b>, the backend it re-derives
            against. The rest are opt-in layers you adopt when you want them; the kit works
            without them.
          </p>
          <div className="cg-family-strip">
            {PEERS.map((p) => (
              <span
                key={p.id}
                className={`cg-peer${p.tier === "required" ? " is-required" : ""}`}
                style={{ ["--hue" as string]: `var(${HUE_VAR[p.hue]})` }}
              >
                <span className="cg-peer-name">{p.name}</span>
                <span className="cg-peer-tier">{p.tier === "required" ? "required floor" : "opt-in layer"}</span>
              </span>
            ))}
          </div>
        </div>
      </Reveal>
    </div>
  );
}
