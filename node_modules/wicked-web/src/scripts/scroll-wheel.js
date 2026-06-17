/* ──────────────────────────────────────────────────────────────
   wickedagile — wheel streamliner. With scroll-snap:mandatory and the tall
   pinned sections (the IDE track, the article track, the about chapters), a
   mouse WHEEL pixel-scrolls slowly and feels endless. This converts a
   discrete wheel notch into a jump to the NEXT snap point — one section /
   package / article / chapter per notch. Trackpad and momentum scrolling
   (small, dense deltas) are left to the native snap so they still feel good.
   Disabled under prefers-reduced-motion.
   ────────────────────────────────────────────────────────────── */
(function(){
  if(window.matchMedia && window.matchMedia('(prefers-reduced-motion:reduce)').matches) return;
  var COOLDOWN = 480, last = 0, animating = false;
  var SEL = '.snap-section,.ide-step,.art-step,.chapter.chapter-shell,.footer';

  function snapTops(){
    var els = Array.prototype.slice.call(document.querySelectorAll(SEL));
    var tops = els.map(function(el){
      var sm = parseInt(getComputedStyle(el).scrollMarginTop, 10) || 0;
      return Math.round(el.getBoundingClientRect().top + window.scrollY - sm);
    });
    return tops.filter(function(v, i, a){ return a.indexOf(v) === i; }).sort(function(a, b){ return a - b; });
  }

  function go(dir){
    var tops = snapTops(), y = window.scrollY, target = null, i;
    if(dir > 0){ for(i = 0; i < tops.length; i++){ if(tops[i] > y + 6){ target = tops[i]; break; } } }
    else { for(i = tops.length - 1; i >= 0; i--){ if(tops[i] < y - 6){ target = tops[i]; break; } } }
    if(target == null) target = dir > 0 ? document.body.scrollHeight : 0;
    animating = true;
    window.scrollTo({ top: target, behavior: 'smooth' });
    window.setTimeout(function(){ animating = false; }, COOLDOWN);
  }

  window.addEventListener('wheel', function(e){
    /* mouse wheel = line/page deltaMode, or a large discrete pixel delta */
    var isWheel = e.deltaMode !== 0 || Math.abs(e.deltaY) >= 50;
    if(!isWheel) return;                                  /* trackpad → native snap */
    if(Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return; /* horizontal intent */
    e.preventDefault();
    var now = Date.now();
    if(animating || now - last < COOLDOWN) return;
    last = now;
    go(e.deltaY > 0 ? 1 : -1);
  }, { passive: false });
})();
