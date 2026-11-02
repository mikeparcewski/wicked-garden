import { useState } from "react";

interface CopyChipProps {
  text: string;
  label?: string;
}

/** A one-line command with click-to-copy. */
export default function CopyChip({ text, label }: CopyChipProps) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard unavailable — no-op */
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      title={text}
      aria-label={`Copy command: ${text}`}
      className="group/copy flex w-full items-center gap-2.5 rounded-lg border border-line bg-canvas-2/60 px-3 py-2.5 text-left font-mono text-[length:var(--text-code)] transition-colors hover:border-accent"
    >
      <span aria-hidden className="select-none text-accent">›</span>
      <span className="min-w-0 flex-1 truncate text-ink">{text}</span>
      <span
        className={`shrink-0 font-sans text-xs transition-colors ${
          copied ? "text-accent" : "text-muted group-hover/copy:text-accent"
        }`}
      >
        {copied ? "copied ✓" : (label ?? "copy")}
      </span>
    </button>
  );
}
