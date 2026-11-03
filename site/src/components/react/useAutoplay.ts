import { useCallback, useEffect, useRef, useState, type RefObject } from "react";

/* ============================================================================
   One auto-play policy for every self-playing block on the page.
   A block plays only while ALL of these hold:
   - it is on screen (IntersectionObserver, a third of it visible),
   - the pointer is not over it and focus is not inside it (the visitor is reading),
   - the visitor has not paused it or taken control.
   Under prefers-reduced-motion it starts paused: the visitor presses Play.
============================================================================ */

export interface Autoplay {
  /** true while the timeline may advance */
  active: boolean;
  /** the visitor paused it (or reduced motion did); false = auto-play is on */
  paused: boolean;
  /** reduced motion was requested */
  reduced: boolean;
  pause: () => void;
  play: () => void;
  toggle: () => void;
  /** spread on the block's root: pause on hover and on focus within */
  bind: {
    onMouseEnter: () => void;
    onMouseLeave: () => void;
    onFocus: () => void;
    onBlur: (e: React.FocusEvent) => void;
  };
}

export function useAutoplay(ref: RefObject<HTMLElement | null>, threshold = 0.33): Autoplay {
  const [visible, setVisible] = useState(false);
  const [hover, setHover] = useState(false);
  const [focusIn, setFocusIn] = useState(false);
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(false);
  const seeded = useRef(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (!seeded.current) {
      seeded.current = true;
      if (mq.matches) {
        setReduced(true);
        setPaused(true);
      }
    }
    // the preference can change on an open page: honour it at once
    const onChange = () => {
      setReduced(mq.matches);
      if (mq.matches) setPaused(true);
    };
    mq.addEventListener?.("change", onChange);
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return () => mq.removeEventListener?.("change", onChange);
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) setVisible(e.isIntersecting && e.intersectionRatio >= threshold * 0.98);
      },
      { threshold: [0, threshold, 0.66, 1] },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      mq.removeEventListener?.("change", onChange);
    };
  }, [ref, threshold]);

  const pause = useCallback(() => setPaused(true), []);
  const play = useCallback(() => {
    setPaused(false);
    // pressing Play is a request to watch: don't hold it for the pointer still resting on the button
    setHover(false);
    setFocusIn(false);
  }, []);
  const toggle = useCallback(() => (paused ? play() : pause()), [paused, play, pause]);

  return {
    active: visible && !hover && !focusIn && !paused,
    paused,
    reduced,
    pause,
    play,
    toggle,
    bind: {
      onMouseEnter: () => setHover(true),
      onMouseLeave: () => setHover(false),
      onFocus: () => setFocusIn(true),
      onBlur: (e: React.FocusEvent) => {
        const next = e.relatedTarget as Node | null;
        if (!next || !(e.currentTarget as HTMLElement).contains(next)) setFocusIn(false);
      },
    },
  };
}

/** Run `step` every `ms` while `active`. */
export function useTick(active: boolean, ms: number, step: () => void) {
  const fn = useRef(step);
  fn.current = step;
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => fn.current(), ms);
    return () => window.clearInterval(id);
  }, [active, ms]);
}
