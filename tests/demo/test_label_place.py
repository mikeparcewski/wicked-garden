"""Pointer labels avoid the app's visible text (wicked-garden#1514)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="needs node")

BOX = {"x": 513, "y": 182, "width": 64, "height": 32}
LABEL = {"width": 62, "height": 29}
FRAME = {"top": 60, "bottom": 600, "left": 110, "right": 1170}
COUNT = {"x": 508, "y": 140, "width": 24, "height": 38}
BELOW = {"x": 510, "y": 223, "width": 62, "height": 29}
RIGHT = {"x": 586, "y": 183.5, "width": 62, "height": 29}


def place(texts, *, box=BOX, label=LABEL, frame=FRAME, preferred="above"):
    pad = 8
    raw = {"x": box["x"] + pad, "y": box["y"] + pad,
           "width": box["width"] - 2 * pad, "height": box["height"] - 2 * pad}
    data = json.dumps({"box": raw, "pad": pad, "label": label, "texts": texts, "frame": frame})
    result = subprocess.run(
        [NODE, "--input-type=module", "-e",
         "import { placeLabel } from './scripts/demo/label-place.mjs';"
         f"process.stdout.write(placeLabel({data}, {json.dumps(preferred)}));"],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_reset_label_avoids_counter_and_point_uses_placement():
    assert place([COUNT]) == "below"
    source = (ROOT / "scripts/demo/stage.mjs").read_text()
    point = source.split("  async point(", 1)[1].split("  async unpoint(", 1)[0]
    assert "placeLabel(" in point


def test_clear_space_keeps_label_above():
    assert place([]) == "above"


def test_text_above_and_below_moves_label_right():
    assert place([COUNT, BELOW]) == "right"


def test_all_sides_covered_chooses_smallest_intersected_area():
    assert place([COUNT, BELOW, {**RIGHT, "width": 2}]) == "right"


def test_equal_intersected_areas_keep_side_order():
    assert place([{"x": 100, "y": 60, "width": 1000, "height": 540}]) == "above"


@pytest.mark.parametrize("frame, expected", [
    ({**FRAME, "top": 147}, "below"),
    ({**FRAME, "top": 147, "bottom": 250}, "right"),
    ({**FRAME, "left": 512}, "right"),
])
def test_frame_edges_and_44_pixel_vertical_room_are_respected(frame, expected):
    assert place([], frame=frame) == expected


@pytest.mark.parametrize("room, expected", [(44, "above"), (43, "below")])
def test_vertical_room_uses_unpadded_highlight_boundary(room, expected):
    raw_y = BOX["y"] + 8
    assert place([], label={**LABEL, "height": 25}, frame={**FRAME, "top": raw_y - room}) == expected


def test_right_is_skipped_when_it_leaves_frame():
    assert place([COUNT, BELOW], frame={**FRAME, "right": 620}) == "above"


def test_forced_below_still_needs_room_inside_frame():
    assert place([], frame={**FRAME, "bottom": 250}, preferred="below") == "above"


@pytest.mark.parametrize("texts, below", [([COUNT], False), ([], True)])
def test_point_translates_frame_text_and_preserves_forced_below(texts, below):
    data = json.dumps({"texts": texts, "below": below})
    result = subprocess.run(
        [NODE, "--input-type=module", "-e", """
import { Stage } from './scripts/demo/stage.mjs';
const { texts, below } = DATA;
const calls = [];
const offset = { x: 200, y: 60 };
const raw = { x: 521, y: 190, width: 48, height: 16 };
const locator = {
  first() { return this; },
  async evaluate() {
    return {
      target: { x: raw.x - offset.x, y: raw.y - offset.y },
      texts: texts.map(r => ({ ...r, x: r.x - offset.x, y: r.y - offset.y })),
      width: 1600, height: 862,
    };
  },
};
const context = {
  box: async () => raw,
  stage: async (_fn, args) => { calls.push(args); return { width: 62, height: 29 }; },
};
await Stage.prototype.point.call(context, locator, 'Reset', { reveal: false, below });
process.stdout.write(JSON.stringify(calls.filter(args => args?.b)));
""".replace("DATA", data)],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    highlights = json.loads(result.stdout)
    assert len(highlights) == 1
    assert highlights[-1]["side"] == "below"
