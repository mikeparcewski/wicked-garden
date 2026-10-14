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
