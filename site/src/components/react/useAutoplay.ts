import { useCallback, useEffect, useRef, useState, type RefObject } from "react";

/* ============================================================================
   One auto-play policy for every self-playing block on the page.
   A block plays only while ALL of these hold:
   - it is on screen (IntersectionObserver: `threshold` of it visible, a third by default; a block
     taller than the window counts the share of the window it fills),
   - the tab is visible (document.hidden),
   - the pointer is not over it and focus is not inside it (the visitor is reading),
   - the visitor has not paused it or taken control.
   Under prefers-reduced-motion it starts paused: the visitor presses Play.
   While it is off screen or the tab is hidden, the block's root carries data-offscreen: its one-shot
   animations and transitions land on their end as it leaves, and site.css pauses every looping CSS
   animation in it, so nothing in it changes while nobody can see it. While its timeline is held on screen
   (the pointer or focus on it, the visitor's Pause, reduced motion) its looping animations pause too, and
   play again with the timeline; one-shot entrances still play, so picked content is never left hidden. A
   pause by the visitor is kept: the block comes back on screen still paused.
============================================================================ */

export interface Autoplay {
  /** true while the timeline may advance */
  active: boolean;
  /** on screen and the tab visible: a run the visitor started plays only while this holds */
  live: boolean;
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
  const [hidden, setHidden] = useState(false);
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
    const onVisibility = () => setHidden(document.hidden);
    onVisibility();
    document.addEventListener("visibilitychange", onVisibility);
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return () => {
        mq.removeEventListener?.("change", onChange);
        document.removeEventListener("visibilitychange", onVisibility);
      };
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          const share = Math.max(e.intersectionRatio, e.intersectionRect.height / Math.max(1, window.innerHeight));
          setVisible(e.isIntersecting && share >= threshold * 0.98);
        }
      },
      // every hundredth: a block taller than the window crosses its share of the window between coarser steps
      { threshold: Array.from({ length: 101 }, (_, i) => i / 100).concat([threshold]) },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      mq.removeEventListener?.("change", onChange);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [ref, threshold]);

  // off screen or in a hidden tab: one-shot animations land on their end, and data-offscreen on the root
  // pauses its CSS loops (site.css)
  const seen = visible && !hidden;
  const wasSeen = useRef(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!seen && wasSeen.current) {
      settle(el);
      // again on the next frame, for a transition the re-render or another observer started on the way out
      requestAnimationFrame(() => { if (el.hasAttribute("data-offscreen")) settle(el); });
    }
    wasSeen.current = seen;
    el.toggleAttribute("data-offscreen", !seen);
  }, [ref, seen]);
  const active = seen && !hover && !focusIn && !paused;
  // held (the visitor's Pause, the pointer or focus on it, reduced motion, off screen): the looping animations
  // pause with the timeline and play again with it. Script pauses them (a script call outranks the CSS play
  // state from then on, so it also keeps them paused off screen until the block plays again); while held on
  // screen it looks again whenever the block's DOM changes, so a loop the held block starts (a re-render's
  // new class, a pick's new chip) pauses too, on the next frame, once its animation exists.
  // One-shot entrances are left to play, so picked content is never left hidden.
  const ours = useRef(new Set<Animation>());
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (seen && active) {
      ours.current.forEach((a) => { try { a.play(); } catch { /* gone */ } });
      ours.current.clear();
      return;
    }
    const hold = () => {
      for (const a of el.getAnimations?.({ subtree: true }) ?? []) {
        if (a.effect?.getComputedTiming().endTime === Infinity && a.playState === "running") { a.pause(); ours.current.add(a); }
      }
    };
    hold();
    if (!seen || typeof MutationObserver === "undefined") return;
    let raf = 0;
    const mo = new MutationObserver(() => { cancelAnimationFrame(raf); raf = requestAnimationFrame(hold); });
    mo.observe(el, { subtree: true, childList: true, attributes: true });
    return () => { mo.disconnect(); cancelAnimationFrame(raf); };
  }, [ref, active, seen]);

  const pause = useCallback(() => setPaused(true), []);
  const play = useCallback(() => {
    setPaused(false);
    // pressing Play is a request to watch: don't hold it for the pointer still resting on the button
    setHover(false);
    setFocusIn(false);
  }, []);
  const toggle = useCallback(() => (paused ? play() : pause()), [paused, play, pause]);

  return {
    active,
    live: seen,
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

/** One-shot animations and transitions under `el` land on their end state now (loops are left to the
    data-offscreen rule), so nothing is left half-faded while nobody can see it. */
function settle(el: HTMLElement) {
  for (const a of el.getAnimations?.({ subtree: true }) ?? []) {
    const end = a.effect?.getComputedTiming().endTime;
    if (end !== undefined && end !== Infinity && a.playState === "running") {
      try { a.finish(); } catch { /* not finishable */ }
    }
  }
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
