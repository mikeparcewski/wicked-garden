// Regenerates tests/fixtures/editor/crew_guard_vectors.json from a wicked-crew checkout (garden#1384).
//   node gen_vectors.mjs <wicked-crew checkout> <garden checkout> > crew_guard_vectors.json
// Needs a Node that runs .ts files directly (22.18+ / 23.6+). The fuzz inputs come from a fixed seed, so a re-run on
// the same crew commit writes the same file. garden's tests read the inputs and crew's answers from the JSON only.
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const [crew, garden] = process.argv.slice(2);
if (!crew || !garden) { console.error('usage: node gen_vectors.mjs <wicked-crew checkout> <garden checkout>'); process.exit(2); }
const guardMod = await import(join(crew, 'packages/crew/src/editors/webrtc-guard.ts'));
const cspMod = await import(join(crew, 'packages/crew/src/editors/csp.ts'));
const { guardBundle, withPrelude, WEBRTC_PRELUDE, MAX_INLINE_SCRIPTS } = guardMod;
const { bundleHeaders } = cspMod;
const commit = execFileSync('git', ['-C', crew, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
const sha = (b) => createHash('sha256').update(b).digest('hex');

// Hand-picked inputs: every shape crew's own tests (packages/crew/tests/editor-webrtc-guard.test.ts) pin.
const html = [
  '<!doctype html><html><head><script>a()</script></head><body><script type="module">b()</script></body></html>',
  '<!DOCTYPE html>\n<meta charset=utf-8><title>t</title><script>x</script>',
  '<script src="x.js"></script><script type="application/json">{"a":1}</script><script type="importmap">{}</script><script type="text/x-template"><b>t</b></script><script language="vbscript">x</script><script type="text/javascript; charset=utf-8">y</script>',
  '<script type="">a</script><script type=" Text/JavaScript ">b</script><script type=MODULE>c</script><script language="javascript">d</script><script language="">e</script><script type=" module">f</script>',
  '<script type="  ">x</script>',
  '<script>var a="<script>"+"x";var b=\'<scr\'+\'ipt>\';</script><p>after</p>',
  '<script>s="<!--<script>";t="</script>";u="-->";v=1</script><p>x</p>',
  '<script>a="<!--";</script><b>',
  '<script>a="<!-->";</script><b>',
  '<script>a="</scripts>"</SCRIPT ><i>',
  '<script>a</script',
  '<!-- <script>a</script> --><!x <script>b</script> ><div title="<script>c</script>" data-x=\'<script>\'></div><style>/*<script>d</script>*/</style><textarea><script>e</script></textarea><title><script>f</script></title><noscript><script>g</script></noscript><script>h</script>',
  '<script/>a</script>',
  '<script data-x="a>b" type=\'module\'>m</script>',
  '<p>a\r\nb\rc</p><script>x=1;\r\ny=2\u0000</script>',
  '<script>"use strict";x</script>',
  '<script type="&Tab;text/javascript&NewLine;">c</script>',
  '<script type="&Tab;module&NewLine;">m</script>',
  '<script type="text&#47;javascript">a</script><script type="&#x6d;odule">b</script>',
  '<svg data-path=/a/><style><script>b</script></style><script src=x>c</script><script href=y>d</script></svg><script src=z>e</script>',
  '<svg><script language="other">s()</script></svg>',
  '<svg><title><script>a</script></title><style><script>b</script></style><script/></svg><style><script>c</script></style><script>d</script>',
  '<svg><title/><style/></svg><script>e</script>',
  '<!doctype html><p>static</p>',
  '<script>a</script><svg><script>b&amp;c</script></svg><script type=module><!--<script></script>--></script><script>',
  '<script>' + '<'.repeat(2000) + '</script>',
  '<script>' + 'x'.repeat(10) + '</script>'.repeat(3),
  '<script>a</script>'.repeat(MAX_INLINE_SCRIPTS),
  '<script>a</script>'.repeat(MAX_INLINE_SCRIPTS + 1),
];
// Script texts for the prelude's place (crew's withPrelude cases), each wrapped as one inline script.
const texts = [
  '"use strict";x()', "#!/usr/bin/env node\n'use strict'; /* c */ \"b\";\ny()", '#!/usr/bin/env node\ny()',
  '"use strict"\nb()', '"use strict"\n(b)', '"use strict"\nin b', '"a" b', '"use strict"\n!function(){}()',
  '"use strict"\n++i', '"a"\n!= b', '"a"\n+ b', '"use strict"\n.5;x()', '"use strict"\n\\u0074op()', '"a"\n.length',
  '"use strict"\nin\\u0078 = 1', '"a"\nin x', '"a"\nin x', "'use strict';\n'x'+y", '//"a";\nx()',
  '/* */ x(); /* */ "a";', '"a" // c\n;b()', '/* never closed', '<!-- old\n"use strict";x()',
  '\n--> old\n"use strict";x()', '"a" --> 0', '"a"\n<!--window[rtc()]\n;', '"a"\n<!--window[rtc()] +\n"b";',
  '"use strict" <!-- same line\nx()', '/*\n*/ --> c\n"use strict";y()', '"use strict"\n<!-- legacy\nwindow.x=1;',
  "'a'\r\n'b'\rc()", '"a\\"b";c()', '"unterminated\nx()', '﻿"use strict";x()',
];
for (const t of texts) html.push(`<script>${t}</script>`);
// The editor bundles garden ships, and the scaffold's template output if present.
for (const rel of ['packs/garden-mcp-inspector/editors/garden-mcp-inspector/index.html', 'tests/fixtures/packs/acme-terms/editors/acme-terms/index.html']) {
  try { html.push(readFileSync(join(garden, rel), 'utf8')); } catch { /* not in this checkout */ }
}
// Fuzz: a fixed-seed mix of the tokens the scanner and the prologue reader decide on.
let seed = 0x1384;
const rnd = () => { seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const tokens = ['<script>', '</script>', '<script type="module">', '<script type=text/plain>', '<script src=a>', '<SCRIPT >', '</SCRIPT>',
  '<!--', '-->', '--!>', '<!x>', '<?p>', '</ x>', '</>', '<svg>', '</svg>', '<math>', '</math>', '<style>', '</style>', '<textarea>', '</textarea>',
  '<title>', '</title>', '<script/>', '<plaintext>', '"use strict"', "'use strict'", ';', '\n', '\r\n', '\r', ' ', '\t', '/*', '*/', '//',
  '#!x', 'a()', '(b)', 'in', '!', '++', '.5', '\\u0074', '"', "'", '=', '>', '<', 'x', '\u0000', ' ', '&amp;', '&#x6d;', 'title="<script>"'];
for (let i = 0; i < 400; i++) {
  const n = 2 + Math.floor(rnd() * 24);
  let s = '';
  for (let j = 0; j < n; j++) s += tokens[Math.floor(rnd() * tokens.length)];
  html.push(s);
}

const handPicked = html.length - 400;
const vectors = html.map((h, i) => {
  const g = guardBundle(Buffer.from(h, 'utf8'), MAX_INLINE_SCRIPTS);
  const v = { html: h };
  if (g.tooMany !== undefined) return { ...v, too_many: g.tooMany };
  return {
    ...v,
    body_sha256: sha(g.body),
    // The text itself only for the hand-picked shapes (readable failures); the fuzz cases keep the digest.
    ...(i < handPicked && g.body.length <= 2048 ? { body: g.body.toString('utf8') } : {}),
    script_hashes: g.scriptHashes,
    ...(i < handPicked ? { csp: bundleHeaders({ manifest: { permissions: [] }, firstParty: false }, g.scriptHashes)['Content-Security-Policy'] } : {}),
  };
});
const headers = bundleHeaders({ manifest: { permissions: [] }, firstParty: false }, []);
process.stdout.write(JSON.stringify({
  source: 'wicked-crew packages/crew/src/editors/webrtc-guard.ts + csp.ts (third-party bundleHeaders)',
  crew_commit: commit,
  prelude: WEBRTC_PRELUDE,
  max_inline_scripts: MAX_INLINE_SCRIPTS,
  headers_without_scripts: headers,
  vectors,
}, null, 0) + '\n');
