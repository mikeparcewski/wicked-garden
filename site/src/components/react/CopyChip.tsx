import { useEffect, useRef, useState } from "react";

interface CopyChipProps {
  text: string;
  /** the action label at rest ("copy", "in your agent") */
  label?: string;
  /** "shell": a terminal command (prompt glyph ›). "agent": a skill call you paste into your coding agent */
  kind?: "shell" | "agent";
}

const COPIED = "copied ✓";

/**
 * A command with click-to-copy. The label's width is reserved for the longer of its two strings (the rest
 * label and "copied ✓", via a hidden ::after sizer in site.css), so copying never moves the command; and a
 * command that does not fit its box wraps at a break point instead of being cut with an ellipsis.
 */
export default function CopyChip({ text, label = "copy", kind = "shell" }: CopyChipProps) {
  const [copied, setCopied] = useState(false);
  const timer = useRef(0);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard unavailable — no-op */
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      title={text}
      aria-label={`Copy ${kind === "agent" ? "skill call" : "command"}: ${text}`}
      className="cc group/copy flex w-full items-baseline gap-2.5 rounded-lg border border-line px-3 py-2.5 text-left font-mono text-[length:var(--text-code)] transition-colors hover:border-accent"
      data-kind={kind}
    >
      {kind === "shell" ? <span aria-hidden className="select-none text-accent">›</span> : null}
      <span className="cc-cmd min-w-0 flex-1 text-ink">{text}</span>
      <span
        className={`cc-label shrink-0 text-right font-sans text-xs transition-colors ${
          copied ? "text-accent" : "text-muted group-hover/copy:text-accent"
        }`}
        data-alt={copied ? label : COPIED}
      >
        <span className="cc-label-t">{copied ? COPIED : label}</span>
      </span>
    </button>
  );
}
