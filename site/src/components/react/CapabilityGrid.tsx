import Reveal from "./Reveal";
import { DOMAINS, PEERS, HUE_VAR, G, type Domain } from "../../data/garden";

/* ============================================================================
   The Grid — the breadth the six signature tools only sample.
   Every chip shown is a real skill or routed action in the repo (skills/<dir>/).
   Honest counts: 141 SKILL.md folded into 14 domain groups (routers, routed
   actions, and fork workers), 40 of them the absorbed qe specialist fleet —
   all verified against skills/** at v12.31.0.
   The qe card leads the grid and deep-links to the wall band below (#qe).
   Folds in the "one install bundles the wicked-* family" point as a compact
   strip at the foot — every peer is an opt-in layer; the kit works without
   any of them.
============================================================================ */

function DomainCard({ d }: { d: Domain }) {
  const body = (
    <>
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
    </>
  );
  const style = { ["--hue" as string]: `var(${HUE_VAR[d.hue]})` };
  // the qe domain card is the doorway to the wall band below
  if (d.id === "qe") {
    return (
      <a className="cg-card cg-card--qe" style={style} href="#qe" aria-label="quality engineering — jump to the qe wall">
        {body}
        <span className="cg-card-jump" aria-hidden>the wall ↓</span>
      </a>
    );
  }
  return (
    <div className="cg-card" style={style}>
      {body}
    </div>
  );
}

export default function CapabilityGrid() {
  return (
    <div className="mx-auto w-full max-w-[1240px] px-5 sm:px-8">
      <Reveal>
        <p className="kicker">03 / the whole catalog</p>
        <h2 className="cg-h2">Six tools were the sample. Here’s the catalog.</h2>
        <p className="cg-intro">
          The toolbox shows the signature gap-fillers. Underneath sits the full
          surface — <span className="cg-em">{G.skills} skills</span> across{" "}
          <span className="cg-em">{G.domains} domains</span>, including the{" "}
          <span className="cg-em">{G.qeSpecialists}-specialist QE fleet</span>{" "}
          absorbed from the retired wicked-testing plugin — all reading the same{/* historical */}{" "}
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
            <span className="cg-family-em">One install bundles the family.</span> Every peer
            is an opt-in layer you adopt when you want it — the kit works without any of them.
            The mem / search / patch / domain stack runs on <b>wicked-estate</b>, the system of
            record; the evidence backend the gate re-derives against (<b>wicked-vault</b>)
            installs directly; the QE pipeline ships in-catalog as the <b>qe</b> domain.
          </p>
          <div className="cg-family-strip">
            {PEERS.map((p) => (
              <span
                key={p.id}
                className="cg-peer"
                style={{ ["--hue" as string]: `var(${HUE_VAR[p.hue]})` }}
              >
                <span className="cg-peer-name">{p.name}</span>
                <span className="cg-peer-tier">{p.cmdLabel}</span>
              </span>
            ))}
          </div>
        </div>
      </Reveal>
    </div>
  );
}
