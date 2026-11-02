import { useEffect, useMemo, useRef, useState } from "react";
import Reveal from "./Reveal";
import CopyChip from "./CopyChip";
import { DOMAINS, PEERS, HUE_VAR, G, type Domain } from "../../data/garden";

/* ============================================================================
   The catalog explorer — the 14 domains as master-detail. No hover trays: the
   selected domain fills a fixed-height detail panel inside the frame (its blurb,
   its skills and the skill you invoke to try it). The domains are a tab list
   (roving tabindex, arrow keys); "type a task" highlights the domains whose
   blurb or skills match. qe is selected first and links to the wall; work-shapes
   plays the archetype demo. Phones: the domains scroll sideways in their own row.
============================================================================ */

function ArchetypesDemo() {
  return (
    <div className="cx-arche" aria-hidden>
      <div className="cx-arche-prompt">“migrate the users table to the new schema”</div>
      <div className="cx-arche-chips">
        {["triage", "build", "migrate", "review"].map((a) => (
          <span key={a} className={`cx-arche-chip${a === "migrate" ? " hit" : ""}`}>{a}</span>
        ))}
      </div>
      <div className="cx-arche-meter"><span className="cx-arche-fill" /></div>
      <div className="cx-arche-note">hard gate · rollback proof · independent attestation</div>
    </div>
  );
}

const STOP = new Set(["the", "and", "for", "with", "from", "into", "that", "this", "your", "my", "our", "how", "what", "can", "its"]);
function words(q: string) {
  return q.toLowerCase().split(/[^a-z0-9]+/).filter((w) => w.length >= 3 && !STOP.has(w));
}
/** a word matches at the start of a word in the domain's name, blurb or skills ("files" ~ "file", never "profile") */
function matches(d: Domain, ws: string[]) {
  if (!ws.length) return false;
  const hay = `${d.name} ${d.blurb} ${d.cmds.join(" ")}`.toLowerCase();
  return ws.some((w) => {
    const stem = w.length > 4 ? w.replace(/(ing|ed|es|s)$/, "") : w;
    return new RegExp(`(^|[^a-z0-9])${stem.replace(/[^a-z0-9]/g, "")}`).test(hay);
  });
}

export default function CatalogExplorer() {
  const [sel, setSel] = useState("qe");
  const [q, setQ] = useState("");
  const tabs = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fromHash = () => {
      const m = location.hash.match(/^#dom-(.+)$/);
      if (m && DOMAINS.some((d) => d.id === m[1])) setSel(m[1]);
    };
    // a link to a domain selects it every time it is followed, even when the hash already names it
    // (navigating to the current hash fires no hashchange)
    const onLink = (e: MouseEvent) => {
      const a = (e.target as Element | null)?.closest?.('a[href^="#dom-"]');
      const id = a?.getAttribute("href")?.slice(5);
      if (id && DOMAINS.some((d) => d.id === id)) setSel(id);
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    document.addEventListener("click", onLink);
    return () => {
      window.removeEventListener("hashchange", fromHash);
      document.removeEventListener("click", onLink);
    };
  }, []);

  const ws = useMemo(() => words(q), [q]);
  const hits = useMemo(() => new Set(DOMAINS.filter((d) => matches(d, ws)).map((d) => d.id)), [ws]);

  function onKey(e: React.KeyboardEvent) {
    const order = DOMAINS.map((d) => d.id);
    const i = order.indexOf(sel);
    let n = i;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") n = (i + 1) % order.length;
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") n = (i - 1 + order.length) % order.length;
    else if (e.key === "Home") n = 0;
    else if (e.key === "End") n = order.length - 1;
    else return;
    e.preventDefault();
    setSel(order[n]);
    tabs.current?.querySelector<HTMLButtonElement>(`#dom-${order[n]}`)?.focus();
  }


  return (
    <div className="sx sx--catalog">
      <Reveal className="sx-title">
        <p className="kicker sx-kicker"><span className="sx-num">07</span>the whole catalog</p>
        <h2 className="sx-h2">{G.skills} skills across {G.domains} domains.</h2>
      </Reveal>
      <Reveal className="sx-lead" delay={0.04}>
        <p>
          The full surface, including the <span className="cx-em">{G.qeSpecialists}-specialist QE fleet</span>,
          all reading the same evidence-first discipline. Everything here is real and in the repo today.
          Pick a domain, or type a task.
        </p>
      </Reveal>

      <div className="sx-stage cx-stage">
        <div className="cx-find">
          <label className="cx-find-l" htmlFor="cx-q">type a task</label>
          <input
            id="cx-q"
            className="cx-find-in"
            type="search"
            autoComplete="off"
            placeholder="rename a function, audit a deploy, test a11y…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <span className="cx-find-n" aria-live="polite">
            {ws.length ? `${hits.size} ${hits.size === 1 ? "domain matches" : "domains match"}` : ""}
          </span>
        </div>

        <div className="cx-tabs" role="tablist" aria-label="the 14 domains" ref={tabs} onKeyDown={onKey}>
          {DOMAINS.map((x) => {
            const on = x.id === sel;
            return (
              <button
                key={x.id}
                id={`dom-${x.id}`}
                type="button"
                role="tab"
                aria-selected={on}
                aria-controls={`cx-panel-${x.id}`}
                tabIndex={on ? 0 : -1}
                className={`cx-tab${on ? " is-on" : ""}${ws.length ? (hits.has(x.id) ? " is-hit" : " is-miss") : ""}`}
                style={{ ["--hue" as string]: `var(${HUE_VAR[x.hue]})` }}
                onClick={() => setSel(x.id)}
              >
                <span className="cx-tab-dot" aria-hidden />
                <span className="cx-tab-name">{x.name}</span>
              </button>
            );
          })}
        </div>

        <div className="cx-details">
          {DOMAINS.map((x) => {
            const on = x.id === sel;
            return (
              <div
                key={x.id}
                className={`cx-detail${on ? " is-on" : " is-off"}`}
                id={`cx-panel-${x.id}`}
                role="tabpanel"
                aria-labelledby={`dom-${x.id}`}
                aria-hidden={!on}
                inert={!on}
                style={{ ["--hue" as string]: `var(${HUE_VAR[x.hue]})` }}
              >
                <div className="cx-detail-main">
                  <div className="cx-detail-h">
                    <span className="cx-detail-name">{x.name}</span>
                    {x.id === "qe" && <a className="cx-jump" href="#qe">the wall ↑</a>}
                  </div>
                  <p className="cx-detail-blurb">{x.blurb}</p>
                  <div className="cx-chips">
                    {x.cmds.map((c) => (
                      <span key={c} className={`cx-chip${ws.length && ws.some((w) => c.includes(w)) ? " is-hit" : ""}`}>{c}</span>
                    ))}
                  </div>
                </div>
                <div className="cx-detail-side">
                  {x.id === "work-shapes" ? <ArchetypesDemo /> : null}
                  <span className="cx-try-l">try it</span>
                  <CopyChip text={x.try} label="copy" />
                </div>
              </div>
            );
          })}
        </div>

        <div className="cx-family">
          <p className="cx-family-lead">
            <b>One install bundles the family.</b> Every peer is an opt-in layer — the kit works without
            any of them.
          </p>
          <div className="cx-family-strip">
            {PEERS.map((p) => (
              <span key={p.id} className="cx-peer" style={{ ["--hue" as string]: `var(${HUE_VAR[p.hue]})` }}>
                <span className="cx-peer-name">{p.name}</span>
                <span className="cx-peer-tier">{p.cmdLabel}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
