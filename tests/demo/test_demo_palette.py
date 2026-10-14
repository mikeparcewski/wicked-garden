"""The demo stage takes the studio skin's colours by default (operator, 2026-10-14), not a fixed grey-and-red palette:
two skins give two different stages, no skin gives the neutral palette, a storyline's brand accent overrides only the
accent, and crew's palette is read from WICKED_CREW_URL with a fallback on any failure."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")
LIGHT = {"canvas": "#e8edf1", "surface": "#ffffff", "ink": "#0b0f14", "ink2": "#1e262e", "muted": "#38434e", "line": "#dbe3e9", "accent": "#224a5e", "font": "Archivo", "scheme": "light"}
DARK = {"canvas": "#0d1117", "surface": "#1b222e", "ink": "#e6edf3", "ink2": "#cdd6df", "muted": "#aeb9c4", "line": "#2a3442", "accent": "#8fc7e6", "font": "Archivo", "scheme": "dark"}

pytestmark = pytest.mark.skipif(NODE is None, reason="needs node")


def node(js: str) -> str:
    done = subprocess.run([NODE, "--input-type=module", "-e", js], capture_output=True, text=True, cwd=REPO, timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout


def stage(palette, accent=None) -> str:
    pal = "undefined" if palette is None else json.dumps(palette)
    return node(f"import {{ stageHtml }} from './scripts/demo/stage.mjs';"
                f"process.stdout.write(stageHtml({{ name: 'Demo', logoSvg: '', accent: {json.dumps(accent)} }}, 'http://x/', {pal}));")


def test_two_skins_give_two_stages_in_their_own_colours():
    light, dark = stage(LIGHT), stage(DARK)
    assert "--bg:#e8edf1" in light and "--ink:#0b0f14" in light and "--brand:rgb(34,74,94)" in light
    assert "--bg:#0d1117" in dark and "--ink:#e6edf3" in dark and "--brand:rgb(143,199,230)" in dark
    assert 'font-family:"Archivo"' in light and "family=Archivo" in light


def test_no_skin_is_neutral_and_never_the_old_red():
    neutral = stage(None)
    assert "--bg:#f3f3f5" in neutral and "--brand:rgb(63,74,90)" in neutral
    for html in (neutral, stage(LIGHT), stage(DARK)):
        assert "238,0,0" not in html and "#ee0000" not in html.lower()


def test_a_storyline_accent_overrides_only_the_accent():
    html = stage(DARK, accent="#e4002b")
    assert "--brand:rgb(228,0,43)" in html and "--bg:#0d1117" in html


def test_the_palette_is_read_from_crew_with_a_fallback():
    out = node("""import { fetchVideoPalette } from './scripts/demo/palette.mjs';
const ok = async () => ({ ok: true, json: async () => ({ source: 'studio-skin', palette: %s }) });
const seen = [];
const a = await fetchVideoPalette({ env: { WICKED_CREW_URL: 'http://127.0.0.1:9/' }, fetchImpl: async (u) => { seen.push(u); return ok(); } });
const b = await fetchVideoPalette({ env: {} });
const c = await fetchVideoPalette({ env: { WICKED_CREW_URL: 'http://x' }, fetchImpl: async () => ({ ok: true, json: async () => ({ palette: { canvas: 'red' } }) }) });
const d = await fetchVideoPalette({ env: { WICKED_CREW_URL: 'http://x' }, fetchImpl: async () => { throw new Error('down'); } });
process.stdout.write(JSON.stringify({ seen, a: a.source, ac: a.palette.canvas, b: b.source, c: c.source, d: d.source }));""" % json.dumps(DARK))
    got = json.loads(out)
    assert got == {"seen": ["http://127.0.0.1:9/api/v1/appearance/video-palette"], "a": "studio-skin", "ac": "#0d1117", "b": "fallback", "c": "fallback", "d": "fallback"}


def _contrast(a: str, b: str) -> float:
    def lum(h: str) -> float:
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


@pytest.mark.parametrize("palette", [LIGHT, DARK, None])
def test_the_speed_badge_reads_on_every_skin(palette):
    html = stage(palette)
    assert "#speed .x{color:var(--bg)" in html and 'style="fill:var(--bg)"' in html and "brand-light" not in html
    p = palette or {"canvas": "#f3f3f5", "ink": "#0b0b0c"}
    assert _contrast(p["ink"], p["canvas"]) >= 7  # badge = an ink pill, ground-coloured text and icon


def test_hostile_palette_values_never_reach_the_stage():
    out = node("""import { checkedPalette } from './scripts/demo/palette.mjs';
const good = { canvas: '#ffffff', surface: '#ffffff', ink: '#000000', ink2: '#111111', muted: '#222222', line: '#333333', accent: '#444444' };
process.stdout.write(JSON.stringify([
  checkedPalette({ ...good, canvas: 'red;}</style><script>x()</script>' }),
  checkedPalette({ ...good, accent: 'url(http://x)' }),
  checkedPalette({ ...good, font: "Inter'); } body{display:none" }).font,
  checkedPalette({ ...good, font: 'Archivo' }).font,
  checkedPalette(null),
]));""")
    assert json.loads(out) == [None, None, "Inter", "Archivo", None]


def test_a_slow_or_failing_crew_falls_back():
    out = node("""import { fetchVideoPalette } from './scripts/demo/palette.mjs';
const r = await fetchVideoPalette({ env: { WICKED_CREW_URL: 'http://x' }, timeoutMs: 20,
  fetchImpl: (_u, { signal }) => new Promise((_, rej) => signal.addEventListener('abort', () => rej(new Error('aborted')))) });
const h = await fetchVideoPalette({ env: { WICKED_CREW_URL: 'http://x' }, fetchImpl: async () => ({ ok: false, json: async () => ({}) }) });
process.stdout.write(JSON.stringify([r.source, h.source]));""")
    assert json.loads(out) == ["fallback", "fallback"]
