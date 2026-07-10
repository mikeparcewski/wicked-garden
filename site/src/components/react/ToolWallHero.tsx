import CopyChip from "./CopyChip";

/* A few hero tools hung on the wall — the full loadout lives in the Tool Wall. */
const HERO_TOOLS = [
  { id: "prove",   name: "prove",   color: "var(--c-floor)",
    icon: <path d="M12 3l2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 15.9 7.2 18l.9-5.4L4.2 8.7l5.4-.8zM9.4 12.2l1.9 1.9 3.4-3.6" /> },
  { id: "search",  name: "search",  color: "var(--c-layer)",
    icon: <><circle cx="7" cy="7" r="2.2" /><circle cx="17" cy="8" r="2.2" /><circle cx="12" cy="17" r="2.2" /><path d="M8.9 8.2l6.2.9M8.4 8.9l2.9 6.3M15.3 9.9l-2.6 5.4M18.5 9.6l3 3" /></> },
  { id: "patch",   name: "patch",   color: "var(--c-workflow)",
    icon: <><rect x="4" y="3.5" width="9" height="12" rx="1.6" /><rect x="11" y="8.5" width="9" height="12" rx="1.6" /><path d="M13.5 12.5h4M13.5 15.5h4" /></> },
  { id: "council", name: "council", color: "var(--c-solo)",
    icon: <><circle cx="7" cy="8" r="2.2" /><circle cx="17" cy="8" r="2.2" /><circle cx="12" cy="6.5" r="2.2" /><path d="M3.5 19c0-2.3 1.7-3.8 3.5-3.8M20.5 19c0-2.3-1.7-3.8-3.5-3.8M8.2 20c0-2.6 1.7-4.3 3.8-4.3S15.8 17.4 15.8 20" /></> },
] as const;

export default function ToolWallHero() {
  return (
    <section
      id="top"
      className="relative flex items-center overflow-hidden px-5 pb-16 pt-28 sm:px-8"
    >
      <div className="mx-auto w-full max-w-[1240px]">
        <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1fr)_340px]">

          {/* ── Left: the pitch ── */}
          <div>
            <p className="rise kicker" style={{ animationDelay: "0.05s" }}>
              the garden · open-source · MIT · v12.27.0
            </p>

            <h1 className="mt-6 font-display text-[clamp(2rem,5.2vw,3.9rem)] font-extrabold leading-[0.98] tracking-[-0.02em]">
              <span className="rise block" style={{ animationDelay: "0.12s" }}>
                Your agent plans and ships.
              </span>
              <span className="rise mt-2 block text-muted" style={{ animationDelay: "0.2s" }}>
                Here’s the wall of tools it can’t build alone.
              </span>
            </h1>

            <div className="rise mt-9 max-w-md" style={{ animationDelay: "0.34s" }}>
              <p className="mb-2 font-mono text-[0.6rem] uppercase tracking-[0.18em] text-muted">
                load out the whole set — one command
              </p>
              <CopyChip text="npx wicked-installer" label="copy" />
              <p className="mt-2 font-mono text-[0.62rem] text-muted">
                interactive · picks your products across CLIs · direct install below
              </p>
            </div>
          </div>

          {/* ── Right: a corner of the wall ── */}
          <div className="hidden min-w-0 lg:block">
            <div className="pegboard w-full p-5">
              <div className="grid grid-cols-2 gap-4">
                {HERO_TOOLS.map((t, i) => (
                  <div
                    key={t.id}
                    className="rise flex flex-col items-center"
                    style={{ animationDelay: `${0.24 + i * 0.08}s` }}
                  >
                    <span className="tw-peg" aria-hidden />
                    <span className="tw-hook" aria-hidden />
                    <span
                      className="tw-body"
                      style={{ ["--tool-c" as string]: t.color, maxWidth: "84px" }}
                    >
                      <svg
                        viewBox="0 0 24 24" fill="none" stroke="currentColor"
                        strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
                        aria-hidden
                      >
                        {t.icon}
                      </svg>
                    </span>
                    <span className="tw-tag">{t.name}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="bench-lip w-full" aria-hidden />
            <p className="mt-3 w-full text-center font-mono text-[0.6rem] uppercase tracking-[0.16em] text-muted">
              6 own tools · 6 bundled peers ↓
            </p>
          </div>

        </div>
      </div>
    </section>
  );
}
