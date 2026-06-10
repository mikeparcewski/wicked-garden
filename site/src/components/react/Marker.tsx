import type { ReactNode } from "react";
import { motion, useReducedMotion } from "motion/react";

interface MarkerProps {
  children: ReactNode;
  /** CSS color for the plant */
  color?: string;
  delay?: number;
  className?: string;
}

const ease = [0.16, 1, 0.3, 1] as const;
const viewport = { once: true, margin: "-10% 0px" } as const;

/** Small leaves that sprout along the stem — two lean-variants instead of transforms. */
const LEAVES = [
  { left: "12%", delay: 0.34, d: "M 6 12 C 3 10 1.6 7 2.8 3.6 C 5.6 5 6.8 8.4 6 12 Z" },
  { left: "46%", delay: 0.5, d: "M 6 12 C 9 10 10.4 7 9.2 3.6 C 6.4 5 5.2 8.4 6 12 Z" },
  { left: "76%", delay: 0.66, d: "M 6 12 C 3 10 1.6 7 2.8 3.6 C 5.6 5 6.8 8.4 6 12 Z" },
];

/**
 * A plant that grows from beneath the words: a stem takes root along the
 * baseline, leaves unfurl, and a tendril curls up past the last letter.
 */
export default function Marker({
  children,
  color = "var(--accent-bright)",
  delay = 0,
  className,
}: MarkerProps) {
  const reduce = useReducedMotion();

  return (
    <span className={`relative inline-block whitespace-nowrap ${className ?? ""}`}>
      <span className="relative z-[1]">{children}</span>

      {/* stem — stretches with the word */}
      <svg
        aria-hidden
        viewBox="0 0 100 14"
        preserveAspectRatio="none"
        className="absolute"
        style={{ left: "-0.04em", right: "0.18em", bottom: "-0.36em", height: "0.36em" }}
      >
        <motion.path
          d="M 2 9 Q 18 3.5 34 8 T 66 8 T 98 6.5"
          fill="none"
          stroke={color}
          strokeWidth={2.6}
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          initial={reduce ? { pathLength: 1 } : { pathLength: 0 }}
          whileInView={{ pathLength: 1 }}
          viewport={viewport}
          transition={{ duration: 0.65, delay, ease }}
        />
      </svg>

      {/* leaves along the stem */}
      {LEAVES.map((leaf) => (
        <motion.svg
          key={leaf.left}
          aria-hidden
          viewBox="0 0 12 12"
          className="absolute"
          style={{ left: leaf.left, bottom: "-0.2em", width: "0.46em", height: "0.46em", originY: 1 }}
          initial={reduce ? { scale: 1, opacity: 1 } : { scale: 0, opacity: 0 }}
          whileInView={{ scale: 1, opacity: 1 }}
          viewport={viewport}
          transition={{ duration: 0.32, delay: delay + leaf.delay, ease }}
        >
          <path d={leaf.d} fill={color} />
        </motion.svg>
      ))}

      {/* tendril curling up past the last letter */}
      <svg
        aria-hidden
        viewBox="0 0 14 24"
        className="absolute"
        style={{ right: "-0.42em", bottom: "-0.08em", width: "0.5em", height: "0.85em" }}
      >
        <motion.path
          d="M 3 24 C 5 18 6.5 13 6.5 8.5 C 6.5 4.5 10.5 3 11.8 6 C 12.8 8.4 10 10.4 8 8.6"
          fill="none"
          stroke={color}
          strokeWidth={2.2}
          strokeLinecap="round"
          initial={reduce ? { pathLength: 1 } : { pathLength: 0 }}
          whileInView={{ pathLength: 1 }}
          viewport={viewport}
          transition={{ duration: 0.5, delay: delay + 0.55, ease }}
        />
      </svg>
    </span>
  );
}
