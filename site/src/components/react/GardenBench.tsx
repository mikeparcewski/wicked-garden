import { useEffect, useMemo, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { KIT_ORDER, LOCKED_TOOLS, PROJECTS, ROLES, TOUR, type Project } from "../../data/projects";
import Marker from "./Marker";
import Reveal from "./Reveal";

const ease = [0.16, 1, 0.3, 1] as const;
const STORAGE_KEY = "wicked-kit";
const byId: Record<string, Project> = Object.fromEntries(PROJECTS.map((p) => [p.id, p]));

function colorOf(p: Project): string {
  return ROLES.find((r) => r.id === p.role)?.colorVar ?? "--accent";
}

/** Install script for the current kit — plain shell, no CLI session needed. */
function buildScript(planted: Set<string>): string {
  const lines = [
    "claude plugins marketplace add mikeparcewski/wicked-garden",
    "claude plugins install wicked-garden        # the gate",
    "npx wicked-vault-install                    # required — evidence backend",
    "npm i -g wicked-loom                        # required — gate engine",
  ];
  if (planted.has("wicked-testing")) lines.push("npx wicked-testing install                  # layer — honest QE");
  if (planted.has("wicked-brain")) lines.push("npx wicked-brain                            # layer — memory");
  if (planted.has("wicked-understanding"))
    lines.push("npx skills add mikeparcewski/wicked-understanding --all");
  if (planted.has("wicked-bus"))
    lines.push(
      "claude plugins marketplace add mikeparcewski/wicked-bus",
      "claude plugins install wicked-bus           # layer — audit trail",
    );
  if (planted.has("wicked-interactive"))
    lines.push(
      "claude plugins marketplace add mikeparcewski/wicked-interactive",
      "claude plugins install wicked-interactive   # solo — live HTML builder",
    );
  lines.push("npx wicked-loom doctor                      # verify the set");
  return lines.join("\n");
}

/** Standalone kit builder — pick your beds, the script writes itself. */
export default function GardenBench() {
  const [planted, setPlanted] = useState<Set<string>>(new Set(LOCKED_TOOLS));
  const [live, setLive] = useState("");
  const [copied, setCopied] = useState(false);

  // hydrate from localStorage (locked tools always present)
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const ids = JSON.parse(raw) as string[];
        setPlanted(new Set([...LOCKED_TOOLS, ...ids.filter((i) => KIT_ORDER.includes(i))]));
      }
    } catch {
      /* corrupt storage — keep defaults */
    }
  }, []);

  function persist(next: Set<string>) {
    setPlanted(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...next]));
    } catch {
      /* storage unavailable — state still works in-memory */
    }
  }

  function toggle(id: string) {
    if (LOCKED_TOOLS.includes(id)) return;
    const next = new Set(planted);
    const stop = TOUR.find((s) => s.tools.includes(id));
    if (next.has(id)) {
      next.delete(id);
      setLive(`${id} unplanted`);
    } else {
      next.add(id);
      setLive(`${id} planted — ${stop?.unlock ?? "added to your kit"}`);
    }
    persist(next);
  }

  function reset() {
    persist(new Set(LOCKED_TOOLS));
    setLive("garden re-tilled — back to the gate and the floor");
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(script);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard unavailable */
    }
  }

  const script = useMemo(() => buildScript(planted), [planted]);
  const grown = KIT_ORDER.filter((id) => planted.has(id));

  return (
    <div className="relative mx-auto max-w-[1240px] px-5 py-28 sm:px-8 sm:py-32">
      <span aria-live="polite" className="sr-only">
        {live}
      </span>

      <Reveal>
        <p className="kicker">03 / the potting bench</p>
        <h2 className="mt-5 font-display text-[clamp(2rem,4.6vw,3.6rem)] font-extrabold leading-[1.02] tracking-tight">
          your garden, <Marker color="var(--accent-bright)">planted.</Marker>
        </h2>
        <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted">
          The gate and the floor are already in — they're required. Toggle the rest on or
          off and the install script writes itself.
        </p>
      </Reveal>

      <Reveal delay={0.06}>
        <ul className="mt-10 flex flex-wrap items-center gap-2.5" aria-label="Pick the beds in your kit">
          {KIT_ORDER.map((id) => {
            const p = byId[id];
            const cvar = colorOf(p);
            const tvar = cvar.replace("--c-", "--ct-");
            const locked = LOCKED_TOOLS.includes(id);
            const on = planted.has(id);
            return (
              <li key={id}>
                <button
                  type="button"
                  disabled={locked}
                  aria-pressed={on}
                  onClick={() => toggle(id)}
                  title={locked ? `${p.short} — required` : on ? `unplant ${p.short}` : `plant ${p.short}`}
                  className="flex items-center gap-2 rounded-full border px-4 py-2.5 font-mono text-[0.78rem] lowercase tracking-[0.06em] transition-all duration-200 hover:-translate-y-0.5 disabled:cursor-default disabled:hover:translate-y-0"
                  style={
                    on
                      ? {
                          borderColor: `var(${cvar})`,
                          color: `var(${tvar})`,
                          background: `color-mix(in oklab, var(${cvar}) 14%, transparent)`,
                        }
                      : { borderColor: "var(--hairline)", borderStyle: "dashed", color: "var(--muted)" }
                  }
                >
                  {on ? <Sprout color={`var(${cvar})`} /> : <span aria-hidden>+</span>}
                  {p.short}
                  {locked ? <span aria-hidden>✓</span> : null}
                </button>
              </li>
            );
          })}
        </ul>
        <p className="mt-4 font-mono text-[0.72rem] uppercase tracking-[0.18em] text-muted">
          {grown.length} of {KIT_ORDER.length} beds in your kit
        </p>
      </Reveal>

      <Reveal delay={0.1}>
        <div className="card-surface mt-8 max-w-2xl overflow-hidden rounded-2xl">
          <div className="flex items-center gap-2 border-b border-line px-4 py-3">
            <span className="h-3 w-3 rounded-full" style={{ background: "var(--c-solo)" }} />
            <span className="h-3 w-3 rounded-full" style={{ background: "var(--accent)" }} />
            <span className="h-3 w-3 rounded-full" style={{ background: "var(--c-layer)" }} />
            <span className="ml-3 font-mono text-[0.72rem] text-muted">your-garden.sh</span>
            <button
              type="button"
              onClick={copy}
              className="ml-auto font-mono text-[0.66rem] uppercase tracking-[0.12em] text-muted transition-colors hover:text-accent"
            >
              {copied ? "copied ✓" : "copy ⧉"}
            </button>
          </div>
          <pre className="overflow-x-auto p-5 font-mono text-[0.8rem] leading-relaxed sm:p-6">{script}</pre>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-4">
          <button
            type="button"
            onClick={copy}
            className="inline-flex items-center gap-2 rounded-full bg-accent px-6 py-3.5 font-mono text-[0.8rem] font-semibold uppercase tracking-[0.12em] text-on-accent transition-transform duration-300 hover:-translate-y-0.5"
            style={{ boxShadow: "0 12px 40px -12px var(--accent)" }}
          >
            {copied ? "copied ✓" : "copy the script ⧉"}
          </button>
          <button
            type="button"
            onClick={reset}
            className="rounded-full border border-line-strong px-5 py-2.5 font-mono text-[0.72rem] uppercase tracking-[0.12em] text-ink transition-colors hover:border-accent hover:text-accent"
          >
            ↺ re-till the garden
          </button>
        </div>
      </Reveal>
    </div>
  );
}

/** Tiny line-art sprout that draws itself in when planted. */
function Sprout({ color }: { color: string }) {
  const reduce = useReducedMotion();
  return (
    <svg width="11" height="13" viewBox="0 0 11 13" fill="none" aria-hidden className="shrink-0">
      <motion.path
        d="M 5.5 12.5 L 5.5 5.5"
        stroke={color}
        strokeWidth="1.6"
        strokeLinecap="round"
        initial={reduce ? { pathLength: 1 } : { pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.35, ease }}
      />
      <motion.path
        d="M 5.5 6.5 C 5.5 4 3.5 2.5 1 2.5 C 1 5 3 6.5 5.5 6.5 Z"
        stroke={color}
        strokeWidth="1.3"
        strokeLinejoin="round"
        initial={reduce ? { pathLength: 1 } : { pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.4, delay: 0.25, ease }}
      />
      <motion.path
        d="M 5.5 5.5 C 5.5 3 7.5 1.5 10 1.5 C 10 4 8 5.5 5.5 5.5 Z"
        stroke={color}
        strokeWidth="1.3"
        strokeLinejoin="round"
        initial={reduce ? { pathLength: 1 } : { pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.4, delay: 0.4, ease }}
      />
    </svg>
  );
}
