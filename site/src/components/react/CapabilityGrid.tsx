import Reveal from "./Reveal";
import { DOMAINS, PEERS, HUE_VAR, type Domain } from "../../data/garden";

/* ============================================================================
   The Grid — the breadth the six signature tools only sample.
   Every chip shown is a real skill or routed action in the repo (skills/<dir>/).
   Honest counts: 94 skills folded into 12 domains (routers + fork workers),
   34 of which are fork/worker skills (a subset, not additional); 10 work-shapes
   — all verified against skills/**.
   Folds in the "one install bundles the wicked-* family" point (was the Shelf)
   as a compact strip at the foot — every peer is an opt-in layer; the kit works
   without any of them.
============================================================================ */

function DomainCard({ d }: { d: Domain }) {
  return (
    <div className="cg-card" style={{ ["--hue" as string]: `var(${HUE_VAR[d.hue]})` }}>
      <div className="cg-card-head">
        <span className="cg-card-name">{d.name}</span>
        <span className="cg-card-count">{d.count} skills</span>
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
          surface — <span className="cg-em">94 skills</span> across{" "}
          <span className="cg-em">12 domains</span>,{" "}
          <span className="cg-em">34 of them fork/worker skills</span> that run in
          isolated subagent contexts — all reading the same evidence-first discipline.
          Everything below is real and in the repo today.
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
            <span className="cg-family-em">One install bundles the family.</span> Every peer
            is an opt-in layer you adopt when you want it — the kit works without any of them.
            The evidence backend the gate re-derives against rides inside <b>wicked-testing</b>,
            not a separate install.
          </p>
          <div className="cg-family-strip">
            {PEERS.map((p) => (
              <span
                key={p.id}
                className="cg-peer"
                style={{ ["--hue" as string]: `var(${HUE_VAR[p.hue]})` }}
              >
                <span className="cg-peer-name">{p.name}</span>
                <span className="cg-peer-tier">opt-in layer</span>
              </span>
            ))}
          </div>
        </div>
      </Reveal>
    </div>
  );
}
