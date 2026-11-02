import { useEffect, useMemo, useRef, useState } from "react";
import Reveal from "./Reveal";
import CopyChip from "./CopyChip";
import PlayToggle from "./PlayToggle";
import { useAutoplay } from "./useAutoplay";
import { DOMAINS, PEERS, HUE_VAR, G, type Domain } from "../../data/garden";

/* ============================================================================
   The catalog explorer — the skill families as master-detail. No hover trays: the
   selected family fills a fixed-height detail panel inside the frame (its blurb,
   its skills and the skill call to try it). The families are a tab list (roving
   tabindex, arrow keys); "type a task" highlights the families whose blurb or
   skills match. It tours itself: it types each example task into the filter and
   opens the first family that matches, until the visitor types, picks a family or
   presses pause (it also pauses on hover, on focus and off-screen, and never
   starts under reduced motion). qe is selected first and links to the wall;
   work-shapes plays the archetype demo. Phones: the families scroll sideways in
   their own row, and the row scrolls to the first match.
============================================================================ */

const TASKS = ["rename a function", "audit a deploy", "test a11y"];
const PLACEHOLDER = "rename a function, audit a deploy, test a11y…";
const TYPE_MS = 70;
const HOLD_MS = 2400;

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
/** how many of the task's words match at the start of a word in the family's name, blurb or skills
    ("files" ~ "file", never "profile"); 0 = no match */
function score(d: Domain, ws: string[]) {
  const hay = `${d.name} ${d.blurb} ${d.cmds.join(" ")}`.toLowerCase();
  return ws.filter((w) => {
    const stem = w.length > 4 ? w.replace(/(ing|ed|es|s)$/, "") : w;
    return new RegExp(`(^|[^a-z0-9])${stem.replace(/[^a-z0-9]/g, "")}`).test(hay);
  }).length;
}

export default function CatalogExplorer() {
  const [sel, setSel] = useState("qe");
  const [q, setQ] = useState("");
  const tabs = useRef<HTMLDivElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const ap = useAutoplay(stage, 0.35);
  const [manual, setManual] = useState(false);
  const [tour, setTour] = useState({ t: 0, n: 0 });
  const [typing, setTyping] = useState(false);

  useEffect(() => {
    const fromHash = () => {
      const m = location.hash.match(/^#dom-(.+)$/);
      if (m && DOMAINS.some((d) => d.id === m[1])) { setManual(true); setSel(m[1]); }
    };
    // a link to a domain selects it every time it is followed, even when the hash already names it
    // (navigating to the current hash fires no hashchange)
    const onLink = (e: MouseEvent) => {
      const a = (e.target as Element | null)?.closest?.('a[href^="#dom-"]');
      const id = a?.getAttribute("href")?.slice(5);
      if (id && DOMAINS.some((d) => d.id === id)) { setManual(true); setSel(id); }
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    document.addEventListener("click", onLink);
    return () => {
      window.removeEventListener("hashchange", fromHash);
      document.removeEventListener("click", onLink);
    };
  }, []);

  // the tour: type a task a letter at a time, hold it with its matches lit, then the next task
  const task = TASKS[tour.t];
  const typed = tour.n >= task.length;
  useEffect(() => {
    if (manual || !ap.active) return;
    const t = window.setTimeout(
      () => setTour((x) => (x.n >= TASKS[x.t].length ? { t: (x.t + 1) % TASKS.length, n: 0 } : { t: x.t, n: x.n + 1 })),
      typed ? HOLD_MS : TYPE_MS,
    );
    return () => window.clearTimeout(t);
  }, [tour, typed, manual, ap.active]);

  const demo = manual || ap.reduced || (ap.paused && tour.n === 0) ? "" : task.slice(0, tour.n);
  const query = manual ? q : demo;
  const ws = useMemo(() => words(query), [query]);
  const scores = useMemo(() => new Map(DOMAINS.map((d) => [d.id, ws.length ? score(d, ws) : 0])), [ws]);
  const hits = useMemo(() => new Set(DOMAINS.filter((d) => (scores.get(d.id) ?? 0) > 0).map((d) => d.id)), [scores]);
  // the best match: the most of the task's words (the first in the list on a tie)
  const firstHit = useMemo(() => {
    let best: string | undefined, top = 0;
    for (const d of DOMAINS) { const n = scores.get(d.id) ?? 0; if (n > top) { top = n; best = d.id; } }
    return best;
  }, [scores]);

  // the tour opens the first match once its task is typed; on a phone, so does a task the visitor types
  useEffect(() => {
    if (!manual && typed && firstHit && !ap.reduced) setSel(firstHit);
  }, [manual, typed, firstHit, tour.t, ap.reduced]);
  useEffect(() => {
    if (manual && firstHit && window.matchMedia("(max-width: 640px)").matches) setSel(firstHit);
  }, [manual, firstHit]);

  // on a phone the row scrolls sideways (only the row, never the page) so the first match shows
  useEffect(() => {
    const row = tabs.current;
    if (!row || !firstHit || row.scrollWidth <= row.clientWidth + 1) return;
    const hit = row.querySelector<HTMLElement>(`#dom-${firstHit}`);
    if (!hit) return;
    const left = row.scrollLeft + hit.getBoundingClientRect().left - row.getBoundingClientRect().left - 16;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    row.scrollTo({ left: Math.max(0, left), behavior: reduced ? "auto" : "smooth" });
  }, [firstHit]);

  function take() {
    if (!manual) setManual(true);
  }
  function resume() {
    setManual(false);
    setQ("");
    setTour({ t: 0, n: 0 });
    ap.play();
  }

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
    take();
    setSel(order[n]);
    tabs.current?.querySelector<HTMLButtonElement>(`#dom-${order[n]}`)?.focus();
  }


  return (
    <div className="sx sx--catalog">
      <Reveal className="sx-title">
        <p className="kicker sx-kicker"><span className="sx-num">07</span>the whole catalog</p>
        <h2 className="sx-h2">{G.skills} skills, <span className="sx-key">by what they do.</span></h2>
      </Reveal>
      <Reveal className="sx-lead" delay={0.12}>
        <p>
          The full surface, including the <span className="cx-em">{G.qeSpecialists}-specialist QE fleet</span>,
          all reading the same evidence-first discipline. Everything here is real and in the repo today.
          Pick a family, or type a task.
        </p>
      </Reveal>

      <div className="sx-stage cx-stage" ref={stage} {...ap.bind}>
        <div className="cx-find">
          <label className="cx-find-l" htmlFor="cx-q">type a task</label>
          <input
            id="cx-q"
            className={`cx-find-in${!manual && demo && !typing ? " is-touring" : ""}`}
            type="search"
            autoComplete="off"
            placeholder={!manual && demo && !typing ? `${demo}▍` : PLACEHOLDER}
            value={q}
            onFocus={() => setTyping(true)}
            onBlur={() => setTyping(false)}
            onChange={(e) => { take(); setQ(e.target.value); }}
          />
          <span className="cx-find-n" aria-live={manual ? "polite" : "off"}>
            {ws.length ? `${hits.size} ${hits.size === 1 ? "family matches" : "families match"}` : "type to match the families"}
          </span>
          <span className="cx-find-ctl">
            {manual ? (
              <button type="button" className="pg-afford-btn" onClick={resume}>▶ resume tour</button>
            ) : (
              <PlayToggle paused={ap.paused} onToggle={ap.toggle} label="the catalog tour" />
            )}
          </span>
        </div>

        <div className="cx-tabs" role="tablist" aria-label="the skill families" ref={tabs} onKeyDown={onKey}>
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
                onClick={() => { take(); setSel(x.id); }}
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
                  <CopyChip text={`/${x.try}`} label="in your agent" kind="agent" />
                </div>
              </div>
            );
          })}
        </div>

        <div className="cx-family">
          <p className="cx-family-lead">
            <b>One install brings what garden needs.</b> The proof gate needs wicked-vault: the family
            installer adds it with garden, and without it the gate fails closed. wicked-estate adds the
            code graph and memory; wicked-bus and wicked-interactive are optional.
          </p>
          <div className="cx-family-strip">
            {PEERS.map((p) => (
              <span key={p.id} className={`cx-peer${p.tier === "required" ? " is-required" : ""}`} style={{ ["--hue" as string]: `var(${HUE_VAR[p.hue]})` }}>
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
