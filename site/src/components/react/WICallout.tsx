import Reveal from "./Reveal";

export default function WICallout() {
  return (
    <section id="wi-callout" className="border-t border-line">
      <div className="mx-auto flex h-full max-w-[1240px] flex-col justify-center px-5 pb-6 sm:px-8" style={{ paddingTop: "calc(var(--topbar-h) + 1.25rem)" }}>
        <div className="grid items-center gap-10 md:grid-cols-2 md:gap-14">
          {/* Left: text content */}
          <Reveal>
            <p className="kicker">also from the garden</p>
            <h2 className="mt-5 font-display text-[clamp(1.9rem,4.4vw,3.4rem)] font-extrabold leading-[1.02] tracking-tight">
              It's 11pm. The deck's due tomorrow.
            </h2>
            <p className="mt-6 max-w-md text-lg leading-relaxed text-muted">
              Tell it what you need — board deck, landing page, demo video — and watch it build in your browser. Point at anything that's off and say what to fix. Export clean HTML, PDF, native PowerPoint, or a narrated video. No code. No design tickets. Just you and the deadline.
            </p>
            <div className="mt-9">
              <a
                href="https://wi.wickedagile.com"
                target="_blank"
                rel="noreferrer"
                className="group inline-flex items-center gap-2 rounded-full bg-accent px-6 py-3.5 font-mono text-[0.8rem] font-semibold uppercase tracking-[0.12em] text-on-accent transition-transform duration-300 hover:-translate-y-0.5"
                style={{ boxShadow: "0 12px 40px -12px var(--accent)" }}
              >
                Try it live →
                <span className="transition-transform duration-300 group-hover:translate-x-1" aria-hidden>
                  ↗
                </span>
              </a>
            </div>
          </Reveal>

          {/* Right: browser-chrome screenshot */}
          <Reveal delay={0.12}>
            <div
              className="overflow-hidden rounded-2xl border border-line"
              style={{ background: "var(--canvas-2)" }}
            >
              {/* Browser chrome */}
              <div
                className="flex items-center gap-2 border-b border-line px-4 py-3"
                style={{ background: "var(--surface)" }}
              >
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: "var(--hairline-strong)" }}
                  aria-hidden
                />
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: "var(--hairline-strong)" }}
                  aria-hidden
                />
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: "var(--hairline-strong)" }}
                  aria-hidden
                />
                <span
                  className="ml-2 flex-1 rounded px-3 py-1 font-mono text-[0.65rem] text-muted"
                  style={{ background: "var(--canvas-2)" }}
                >
                  wi.wickedagile.com
                </span>
              </div>
              <img
                src={`${import.meta.env.BASE_URL}wi-screenshot.png`}
                alt="wicked-interactive — in-browser HTML presentation builder"
                className="wi-screenshot"
                loading="lazy"
              />
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
