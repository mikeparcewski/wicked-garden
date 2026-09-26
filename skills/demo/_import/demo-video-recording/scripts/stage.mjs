// Recording stage for captioned product demo videos (part of the demo-video-recording skill).
//
// The app runs inside a 1600x900 browser-window frame on a 1920x1080 stage page; the lower-third caption band,
// cursor, callouts and title cards are stage DOM, so captions never cover the product UI and everything is
// rendered with real fonts and CSS transitions. Frames come from the Chrome DevTools screencast (JPEG q95,
// wall-clock timestamps) instead of Playwright's built-in recorder, whose fixed ~1 Mbps VP8 blurs text at
// 1080p. postprocess.mjs turns the frames into an H.264 MP4, time-lapsing the marked waits and embedding
// chapter markers.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

// Served from the app's own origin (route interception), so the app iframe is same-origin with the stage.
const STAGE_PATH = "/__demo_stage__";
const W = 1920, H = 1080;
export const FRAME = { x: 160, y: 20, w: 1600, h: 900, bar: 38 };

function hexToRgb(hex) {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || "");
  return m ? m.slice(1).map((h) => parseInt(h, 16)) : [238, 0, 0];
}

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

function stageHtml({ name, logoSvg, accent }, appUrl) {
  const logo = (logoSvg || "").replace(/<\?xml[^>]*>/, "");
  const [r, g, b] = hexToRgb(accent);
  const lk = logo ? `${logo}<span class="nm">${esc(name)}</span>` : `<span class="nm solo">${esc(name)}</span>`;
  return `<!doctype html><html><head><meta charset="utf-8"><title>${esc(name)} demo</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--ink:#0b0b0c;--ink2:#2b2b30;--muted:#62626b;--line:#e4e4e8;--bg:#f3f3f5;--brand:rgb(${r},${g},${b});--brand-soft:rgba(${r},${g},${b},.14);--brand-glow:rgba(${r},${g},${b},.45);
 --brand-light:rgb(${Math.min(255, r + 60)},${Math.min(255, g + 90)},${Math.min(255, b + 90)})}
*{box-sizing:border-box}html,body{margin:0;width:${W}px;height:${H}px;overflow:hidden;background:var(--bg);
 font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--ink);-webkit-font-smoothing:antialiased}
body{background:radial-gradient(1200px 700px at 50% 0%,#fafafa 0%,var(--bg) 60%,#ececef 100%)}
#win{position:absolute;left:${FRAME.x}px;top:${FRAME.y}px;width:${FRAME.w}px;height:${FRAME.h}px;border-radius:14px;overflow:hidden;background:#fff;
 border:1px solid #dcdce1;box-shadow:0 1px 2px rgba(16,16,20,.05),0 18px 50px -12px rgba(16,16,20,.18)}
#bar{height:${FRAME.bar}px;display:flex;align-items:center;gap:14px;padding:0 16px;background:#f7f7f8;border-bottom:1px solid var(--line)}
.dots{display:flex;gap:7px}.dots i{width:11px;height:11px;border-radius:50%;background:#dadadf;display:block}
#url{flex:0 1 560px;margin:0 auto;height:24px;border-radius:7px;background:#fff;border:1px solid var(--line);display:flex;align-items:center;justify-content:center;
 gap:8px;font-size:12.5px;color:var(--muted);letter-spacing:.01em}
#url b{color:var(--ink2);font-weight:600;flex:none}
#url #path{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#app{display:block;width:${FRAME.w}px;height:${FRAME.h - FRAME.bar}px;border:0;background:#fff}
#band{position:absolute;left:${FRAME.x}px;width:${FRAME.w}px;top:${FRAME.y + FRAME.h + 22}px;height:${H - FRAME.y - FRAME.h - 40}px;display:flex;gap:40px;align-items:flex-start}
#cap{flex:1;min-width:0;position:relative}
.cap{position:absolute;inset:0;transition:opacity .45s ease,transform .45s cubic-bezier(.2,.7,.2,1)}
.cap.out{opacity:0;transform:translateY(10px)}
.kicker{display:flex;align-items:center;gap:10px;font-size:13px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--brand)}
.kicker i{width:22px;height:3px;border-radius:2px;background:var(--brand);display:block}
.title{margin-top:7px;font-size:27px;line-height:1.2;font-weight:650;letter-spacing:-.012em;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.body{margin-top:6px;font-size:17.5px;line-height:1.45;color:var(--muted);max-width:1180px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.body em{font-style:normal;color:var(--ink2);font-weight:600}
#brand{width:300px;flex:none;display:flex;flex-direction:column;align-items:flex-end;gap:12px;padding-top:2px}
#brand .lk{display:flex;align-items:center;gap:12px}#brand svg{height:21px;width:auto}
#brand .nm{font-size:15px;font-weight:650;color:var(--ink);padding-left:12px;border-left:1px solid #cfcfd6}
.nm.solo{padding-left:0!important;border-left:0!important}
#prog{display:flex;gap:5px}#prog i{width:22px;height:4px;border-radius:2px;background:#d9d9de;display:block;transition:background .4s}
#prog i.done{background:#8d8d96}#prog i.on{background:var(--brand)}
#chap{font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums}
#speed{position:absolute;right:${W - FRAME.x - FRAME.w + 12}px;top:${FRAME.y + 5}px;height:28px;display:flex;align-items:center;gap:9px;padding:0 12px;border-radius:999px;
 background:rgba(11,11,12,.9);color:#fff;font-size:13px;font-weight:600;box-shadow:0 6px 18px -8px rgba(0,0,0,.45);opacity:0;transform:translateY(-4px);transition:all .35s;z-index:30;
 pointer-events:none}
#speed.on{opacity:1;transform:none}#speed .x{color:var(--brand-light);font-variant-numeric:tabular-nums}#speed .t{font-weight:500;color:#cfcfd6;font-variant-numeric:tabular-nums}
#speed svg{width:15px;height:15px}
#hl{position:absolute;border-radius:12px;border:3px solid var(--brand);box-shadow:0 0 0 7px var(--brand-soft),0 10px 30px -10px var(--brand-glow);opacity:0;
 transition:opacity .35s,left .45s,top .45s,width .45s,height .45s;pointer-events:none;z-index:20}
#hl.on{opacity:1}
#hl span{position:absolute;left:-3px;bottom:calc(100% + 9px);white-space:nowrap;background:var(--ink);color:#fff;font-size:13.5px;font-weight:600;padding:6px 11px;border-radius:8px;
 box-shadow:0 6px 18px -6px rgba(0,0,0,.35)}
#hl.below span{bottom:auto;top:calc(100% + 9px)}
#cur{position:absolute;left:0;top:0;width:26px;height:26px;z-index:40;pointer-events:none;transition:transform .7s cubic-bezier(.25,.8,.25,1),opacity .3s;opacity:0}
#cur.on{opacity:1}#cur svg{filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}
.rip{position:absolute;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;border:2.5px solid var(--brand);background:var(--brand-soft);z-index:39;
 pointer-events:none;animation:rip .6s ease-out forwards}
@keyframes rip{from{transform:scale(.3);opacity:1}to{transform:scale(1.35);opacity:0}}
#card{position:absolute;inset:0;z-index:60;display:flex;align-items:center;justify-content:center;background:radial-gradient(1200px 700px at 50% 30%,#fff 0%,#f4f4f6 70%,#ececef 100%);
 opacity:0;pointer-events:none;transition:opacity .7s ease}
#card.on{opacity:1}
#card .in{width:1180px;transform:translateY(12px);transition:transform .9s cubic-bezier(.2,.7,.2,1)}#card.on .in{transform:none}
#card .lk{display:flex;align-items:center;gap:18px}#card .lk svg{height:38px;width:auto}#card .lk .nm{font-size:26px;font-weight:650;padding-left:18px;border-left:1.5px solid #cfcfd6}
#card h1{margin:46px 0 0;font-size:66px;line-height:1.05;font-weight:700;letter-spacing:-.025em}
#card h1 span{color:var(--brand)}
#card p{margin:22px 0 0;font-size:24px;line-height:1.5;color:var(--muted);max-width:1000px}
#card .meta{margin-top:44px;display:flex;gap:12px;flex-wrap:wrap}
#card .meta b{font-size:15px;font-weight:600;color:var(--ink2);background:#fff;border:1px solid var(--line);border-radius:999px;padding:8px 15px}
#card ol{margin:34px 0 0;padding:0;list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:12px 48px}
#card .seg{display:flex;gap:64px;align-items:flex-start}
#card .seg .num{font-size:150px;line-height:.82;font-weight:700;letter-spacing:-.05em;color:var(--brand);font-variant-numeric:tabular-nums}
#card .seg .of{font-size:15px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
#card .seg h1{margin-top:14px;font-size:58px}
#card .seg p{margin-top:18px;font-size:23px;max-width:880px}
#card .seg .meta{margin-top:34px}
#card li{font-size:21px;color:var(--ink2);display:flex;gap:14px;align-items:baseline}#card li b{color:var(--brand);font-variant-numeric:tabular-nums;font-size:16px}
</style></head><body>
<div id="win"><div id="bar"><div class="dots"><i></i><i></i><i></i></div><div id="url"><b>${esc(name)}</b><span id="path">/</span></div><div style="width:47px"></div></div>
<iframe id="app" src="${appUrl}"></iframe></div>
<div id="band"><div id="cap"></div><div id="brand"><div class="lk">${lk}</div><div id="prog"></div><div id="chap"></div></div></div>
<div id="speed"><svg viewBox="0 0 24 24" fill="var(--brand-light)"><path d="M4 5v14l8-7zM12 5v14l8-7z"/></svg><span class="x"></span><span class="lbl"></span><span class="t"></span></div>
<div id="hl"><span></span></div>
<div id="cur"><svg viewBox="0 0 26 26" width="26" height="26"><path d="M5 3l15.5 9.2-6.9 1.5 3.9 7.3-3 1.6-3.9-7.4-5.1 4.6z" fill="#0b0b0c" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg></div>
<div id="card"><div class="in"></div></div>
<script>
const $=s=>document.querySelector(s);
window.__stage={
  caption(c){const host=$('#cap');const olds=[...host.querySelectorAll('.cap')];olds.forEach(o=>{o.style.transitionDuration='.28s';o.classList.add('out');setTimeout(()=>o.remove(),300)});
    const el=document.createElement('div');el.className='cap out';
    el.innerHTML='<div class="kicker"><i></i>'+c.kicker+'</div><div class="title">'+c.title+'</div>'+(c.body?'<div class="body">'+c.body+'</div>':'');
    setTimeout(()=>{host.appendChild(el);requestAnimationFrame(()=>requestAnimationFrame(()=>el.classList.remove('out')))},olds.length?300:0);},
  progress(n,i,label){$('#prog').innerHTML=Array.from({length:n},(_,k)=>'<i class="'+(k<i?'done':k===i?'on':'')+'"></i>').join('');$('#chap').textContent=label||''},
  path(p){$('#path').textContent=p},
  speed(on,x,lbl){const s=$('#speed');if(on){s.querySelector('.x').textContent=x+'\\u00d7';s.querySelector('.lbl').textContent=lbl||'';s.classList.add('on');
      const t0=performance.now();clearInterval(window.__spd);window.__spd=setInterval(()=>{const sec=Math.round((performance.now()-t0)/1000);
      s.querySelector('.t').textContent=Math.floor(sec/60)+':'+String(sec%60).padStart(2,'0')+' real time'},250)}
    else{s.classList.remove('on');clearInterval(window.__spd)}},
  highlight(b,label,below){const h=$('#hl');if(!b){h.classList.remove('on');return}const p=8;const fresh=!h.classList.contains('on');
    if(fresh)h.style.transition='opacity .35s';
    Object.assign(h.style,{left:(b.x-p)+'px',top:(b.y-p)+'px',width:(b.width+2*p)+'px',height:(b.height+2*p)+'px'});
    if(fresh){void h.offsetWidth;setTimeout(()=>{h.style.transition=''},400)}
    const s=h.querySelector('span');s.textContent=label||'';s.style.display=label?'':'none';h.classList.toggle('below',!!below);h.classList.add('on')},
  cursor(x,y,show){const c=$('#cur');c.style.transform='translate('+(x-5)+'px,'+(y-3)+'px)';c.classList.toggle('on',show!==false)},
  ripple(x,y){const r=document.createElement('div');r.className='rip';r.style.left=x+'px';r.style.top=y+'px';document.body.appendChild(r);setTimeout(()=>r.remove(),700)},
  card(html){const c=$('#card');if(html===null){c.classList.remove('on');return}c.querySelector('.in').innerHTML=html;c.querySelectorAll('[data-logo]').forEach(e=>{e.className='lk';e.innerHTML=document.querySelector('#brand .lk').innerHTML});c.classList.add('on')},
};
</script></body></html>`;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export class Stage {
  /**
   * @param {object} o
   * @param {string} o.baseUrl       app origin, e.g. http://localhost:3000
   * @param {string} o.outDir        where frames/ and timeline.json go
   * @param {string[]} o.chapters    chapter titles (progress indicator)
   * @param {{name: string, logoSvg?: string, accent?: string}} o.brand
   * @param {number} [o.stickyOffset=88]  px to leave above a tall element when scrolling it into view (app header)
   * @param {boolean} [o.headful=false]   show the browser window while recording
   */
  constructor({ baseUrl, outDir, chapters, brand, stickyOffset = 88, headful = false, locale = "en-US", timezoneId }) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.outDir = outDir;
    this.brand = { name: brand?.name ?? "Demo", logoSvg: brand?.logoSvg ?? "", accent: brand?.accent ?? "#ee0000" };
    this.chapterNames = chapters;
    this.stickyOffset = stickyOffset;
    this.headful = headful;
    this.locale = locale;
    this.timezoneId = timezoneId;
    this.marks = { chapters: [], speed: [], captions: [] };
    this.frameCount = 0;
    this.chapterIndex = -1;
  }

  async open(firstPath = "/") {
    fs.mkdirSync(path.join(this.outDir, "frames"), { recursive: true });
    for (const f of fs.readdirSync(path.join(this.outDir, "frames"))) fs.unlinkSync(path.join(this.outDir, "frames", f));
    this.frames = [];
    this.browser = await chromium.launch({ headless: !this.headful, args: ["--force-color-profile=srgb", "--hide-scrollbars"] });
    this.context = await this.browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, locale: this.locale, ...(this.timezoneId ? { timezoneId: this.timezoneId } : {}) });
    this.page = await this.context.newPage();
    const html = stageHtml(this.brand, this.baseUrl + firstPath);
    await this.page.route(this.baseUrl + STAGE_PATH, (route) => route.fulfill({ status: 200, contentType: "text/html", body: html }));
    this.page.on("framenavigated", (f) => {
      if (f !== this.page.mainFrame() && f.url().startsWith(this.baseUrl)) {
        const u = new URL(f.url());
        // Path only: query strings (search terms, section ids) would crowd the address bar.
        this.page.evaluate((p) => window.__stage?.path(p), u.pathname).catch(() => {});
      }
    });
    await this.page.goto(this.baseUrl + STAGE_PATH, { waitUntil: "load" });
    await this.page.evaluate(() => document.fonts.ready).catch(() => {}); // offline: falls back to system fonts
    this.app = this.page.frameLocator("#app");
    this.appFrame = await (await this.page.$("#app")).contentFrame();
    await this.appFrame.waitForLoadState("networkidle").catch(() => {});
    // Screencast: every changed frame with its wall-clock timestamp (seconds).
    this.cdp = await this.context.newCDPSession(this.page);
    this.cdp.on("Page.screencastFrame", async (ev) => {
      const name = `f${String(this.frameCount++).padStart(6, "0")}.jpg`;
      fs.writeFileSync(path.join(this.outDir, "frames", name), Buffer.from(ev.data, "base64"));
      this.frames.push({ file: name, t: ev.metadata.timestamp });
      await this.cdp.send("Page.screencastFrameAck", { sessionId: ev.sessionId }).catch(() => {});
    });
    await this.cdp.send("Page.startScreencast", { format: "jpeg", quality: 95, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
    this.t0 = Date.now() / 1000;
    this.cursorAt = { x: FRAME.x + FRAME.w / 2, y: FRAME.y + FRAME.h / 2 };
    await this.stage((s, c) => s.cursor(c.x, c.y, false), this.cursorAt);
  }

  now() { return Date.now() / 1000; }
  stage(fn, arg) { return this.page.evaluate(`(${fn.toString()})(window.__stage, ${JSON.stringify(arg ?? null)})`); }
  hold(ms) { return sleep(ms); }

  async card(html, ms) {
    await this.stage((s, h) => s.card(h), html);
    await sleep(ms);
  }
  async uncard() { await this.stage((s) => s.card(null)); await sleep(800); }

  async chapter(i) {
    this.chapterIndex = i;
    this.marks.chapters.push({ t: this.now(), title: this.chapterNames[i] });
    await this.stage((s, a) => s.progress(a.n, a.i, a.label), { n: this.chapterNames.length, i, label: `Chapter ${i + 1} of ${this.chapterNames.length} · ${this.chapterNames[i]}` });
  }

  /** Lower-third caption. body may contain <em>. readMs is how long the viewer needs it (scaled by length when omitted). */
  async caption(kicker, title, body = "", readMs) {
    this.marks.captions.push({ t: this.now(), kicker, title, body });
    await this.stage((s, c) => s.caption(c), { kicker, title, body });
    await sleep(readMs ?? Math.min(9000, 2200 + (title.length + body.length) * 38));
  }

  async go(p) {
    await this.appFrame.goto(this.baseUrl + p, { waitUntil: "domcontentloaded" });
    await this.appFrame.waitForLoadState("networkidle").catch(() => {});
    await sleep(700);
  }

  /** Box of a locator in stage coordinates (Playwright reports main-frame viewport coordinates). */
  async box(locator) {
    await locator.first().waitFor({ state: "visible", timeout: 60_000 });
    return locator.first().boundingBox();
  }

  async reveal(locator) {
    // Centre it, unless it is taller than most of the viewport: then bring its top just under the sticky app header.
    // Scrolls the element's nearest scrollable ancestor, falling back to the window.
    await locator.first().evaluate((el, offset) => {
      const r = el.getBoundingClientRect(), vh = window.innerHeight;
      const by = r.height > vh * 0.7 ? r.top - offset : r.top + r.height / 2 - vh / 2;
      let p = el.parentElement;
      while (p && !(p.scrollHeight > p.clientHeight && /(auto|scroll)/.test(getComputedStyle(p).overflowY))) p = p.parentElement;
      (p && p !== document.body && p !== document.documentElement ? p : window).scrollBy({ top: by, behavior: "smooth" });
    }, this.stickyOffset).catch(() => {});
    await sleep(900);
  }

  async point(locator, label, { below = false, hold = 0, reveal = true } = {}) {
    if (reveal) await this.reveal(locator);
    const raw = await this.box(locator);
    // Clip to the visible app viewport (inside the window frame) so a tall section never spills over the stage.
    const top = FRAME.y + FRAME.bar + 12, bottom = FRAME.y + FRAME.h - 12, left = FRAME.x + 12, right = FRAME.x + FRAME.w - 12;
    const x = Math.max(raw.x, left), y = Math.max(raw.y, top);
    const b = { x, y, width: Math.max(40, Math.min(raw.x + raw.width, right) - x), height: Math.max(30, Math.min(raw.y + raw.height, bottom) - y) };
    if (b.y - top < 44) below = true; // no room for the label above
    if (below && bottom - (b.y + b.height) < 44) below = false;
    await this.stage((s, a) => s.highlight(a.b, a.label, a.below), { b, label, below });
    if (hold) await sleep(hold);
    return b;
  }
  async unpoint() { await this.stage((s) => s.highlight(null)); await sleep(350); }

  async moveTo(locator) {
    const b = await this.box(locator);
    const x = b.x + Math.min(b.width / 2, 60), y = b.y + b.height / 2;
    await this.stage((s, c) => s.cursor(c.x, c.y, true), { x, y });
    this.cursorAt = { x, y };
    await sleep(800);
    return { x, y };
  }

  async click(locator, { reveal = true, after = 900 } = {}) {
    if (reveal) await this.reveal(locator);
    const { x, y } = await this.moveTo(locator);
    await this.stage((s, c) => s.ripple(c.x, c.y), { x, y });
    await locator.first().click();
    await sleep(after);
  }

  async type(locator, text, { delay = 28 } = {}) {
    await this.click(locator, { after: 300 });
    await locator.first().pressSequentially(text, { delay });
    await sleep(500);
  }

  hideCursor() { return this.stage((s, c) => s.cursor(c.x, c.y, false), this.cursorAt); }

  /** Time-lapse a wait: the badge shows on screen and postprocess speeds the span up by `factor`. */
  async fast(label, factor, fn) {
    await this.stage((s, a) => s.speed(true, a.x, a.l), { x: factor, l: label });
    await sleep(600);
    const t = this.now();
    try { return await fn(); } finally {
      this.marks.speed.push({ start: t, end: this.now(), factor, label });
      await sleep(400);
      await this.stage((s) => s.speed(false));
      await sleep(400);
    }
  }

  async close() {
    await sleep(600);
    await this.cdp.send("Page.stopScreencast").catch(() => {});
    await sleep(300);
    const meta = { t0: this.t0, tEnd: this.now(), frames: this.frames, marks: this.marks, size: { w: W, h: H } };
    fs.writeFileSync(path.join(this.outDir, "timeline.json"), JSON.stringify(meta, null, 1));
    await this.context.close();
    await this.browser.close();
    return meta;
  }
}
