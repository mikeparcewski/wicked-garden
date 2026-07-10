import { useState } from "react";
import CopyChip from "./CopyChip";
import Reveal from "./Reveal";
import { PEERS, HUE_VAR, type Peer } from "../../data/garden";

/* ============================================================================
   The Shelf — the wider wicked-* family one install puts within reach.
   HONEST: wicked-vault is the ONE required peer; the rest are opt-in layers.
   The gate/resolve engine ships in-package — not a peer you install.
   Interaction: crates on a shelf; open one to see what garden gives you
   through it + how it relates.
============================================================================ */

function Crate({ peer, open, onToggle }: { peer: Peer; open: boolean; onToggle: () => void }) {
  const hue = `var(${HUE_VAR[peer.hue]})`;
  return (
    <div
      className={`sh-crate${open ? " is-open" : ""}${peer.tier === "required" ? " is-required" : ""}`}
      style={{ ["--hue" as string]: hue }}
    >
      <button type="button" className="sh-crate-top" aria-expanded={open} onClick={onToggle}>
        <span className="sh-crate-tier">{peer.tier === "required" ? "required floor" : "opt-in layer"}</span>
        <span className="sh-crate-name">{peer.name}</span>
        <span className="sh-crate-plus" aria-hidden>{open ? "–" : "+"}</span>
      </button>
      {open && (
        <div className="sh-crate-open">
          <p className="sh-crate-gives">{peer.gives}</p>
          <div className="sh-crate-cmdlabel">{peer.cmdLabel}</div>
          <CopyChip text={peer.cmd} />
        </div>
      )}
    </div>
  );
}

export default function Shelf() {
  const [openId, setOpenId] = useState<string | null>("vault");

  return (
    <div className="mx-auto w-full max-w-[1240px] px-5 sm:px-8">
      <Reveal>
        <p className="kicker">03 / the shelf</p>
        <h2 className="sh-h2">One install. The whole family within reach.</h2>
        <p className="sh-intro">
          The gate stands on one required floor — <span className="sh-em">wicked-vault</span>,
          the backend it re-derives against. Everything else is an opt-in layer you adopt when
          you want it; the kit works without the rest. The gate/resolve engine ships in-package —
          nothing extra to install.
        </p>
      </Reveal>

      <Reveal delay={0.06}>
        <div className="sh-grid">
          {PEERS.map((p) => (
            <Crate
              key={p.id}
              peer={p}
              open={openId === p.id}
              onToggle={() => setOpenId((cur) => (cur === p.id ? null : p.id))}
            />
          ))}
        </div>
        <div className="sh-plank" aria-hidden />
      </Reveal>
    </div>
  );
}
