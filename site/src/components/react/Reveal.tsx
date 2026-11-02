import { useEffect, useRef, useState, type ReactNode } from "react";

interface RevealProps {
  children: ReactNode;
  delay?: number;
  y?: number;
  className?: string;
}

/**
 * Fade + slide a block in the first time it scrolls into view.
 * Self-contained IntersectionObserver with a hard fallback timer — content is
 * NEVER left invisible even if the observer misses (programmatic scroll, anchor
 * jumps, hydration races). Honors prefers-reduced-motion.
 *
 * will-change is set only for the entrance and cleared once it has played: a shown
 * block must create no stacking context, or a later sibling Reveal paints over any
 * raised state inside an earlier one (the catalog trays slid under the family strip).
 */
export default function Reveal({ children, delay = 0, y = 26, className }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  const [settled, setSettled] = useState(false);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(true);
      setSettled(true);
      return;
    }
    const el = ref.current;
    if (!el) {
      setShown(true);
      setSettled(true);
      return;
    }
    const reveal = () => setShown(true);
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          reveal();
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -6% 0px", threshold: 0.01 },
    );
    io.observe(el);
    // Fallback: guarantee visibility regardless of observer behaviour.
    const t = window.setTimeout(reveal, 1300);
    return () => {
      io.disconnect();
      window.clearTimeout(t);
    };
  }, []);

  useEffect(() => {
    if (!shown || settled) return;
    const t = window.setTimeout(() => setSettled(true), (delay + 0.75) * 1000);
    return () => window.clearTimeout(t);
  }, [shown, settled, delay]);

  return (
    <div
      ref={ref}
      className={className}
      style={
        settled
          ? undefined
          : {
              opacity: shown ? 1 : 0,
              transform: shown ? "none" : `translateY(${y}px)`,
              transition: `opacity 0.7s cubic-bezier(0.16,1,0.3,1) ${delay}s, transform 0.7s cubic-bezier(0.16,1,0.3,1) ${delay}s`,
              willChange: "opacity, transform",
            }
      }
      data-reveal={settled ? "shown" : shown ? "entering" : "waiting"}
    >
      {children}
    </div>
  );
}
