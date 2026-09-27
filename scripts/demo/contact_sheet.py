#!/usr/bin/env python3
"""Contact sheets of stills from a demo video, for fast visual QA.

Pick the moments to look at, and this tiles one still per moment into a single PNG you can open or show to a
reviewer. Works on macOS, Linux and Windows; needs ffmpeg and ffprobe (on PATH, or FFMPEG=/path/to/ffmpeg, with
ffprobe next to it).

  python3 contact_sheet.py demo.mp4 --at 5,62,118.5          # stills at these seconds (m:ss also accepted)
  python3 contact_sheet.py demo.mp4 --every 30               # one still every 30 s
  python3 contact_sheet.py demo.mp4 --chapters               # a still ~2 s into every MP4 chapter
  python3 contact_sheet.py demo.mp4 --joins                  # just before and just after every chapter boundary
  python3 contact_sheet.py demo.mp4 --end                    # the last seconds (is the closing card there, full length?)
  python3 contact_sheet.py demo.mp4 --chapters --end --cols 4 --width 480 --out sheet.png

On Windows use `python` if `python3` is not on PATH. Each tile is labelled with its timestamp (and chapter title
when known) so findings can be reported as "03:12 · Search".
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def tools() -> tuple[str, str]:
    ffmpeg = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("ffmpeg not found: install it or set FFMPEG=/path/to/ffmpeg")
    p = Path(ffmpeg)
    probe_name = p.name.replace("ffmpeg", "ffprobe")
    ffprobe = str(p.with_name(probe_name)) if p.parent != Path(".") and p.with_name(probe_name).exists() else shutil.which("ffprobe")
    if not ffprobe:
        sys.exit("ffprobe not found: install it next to ffmpeg or on PATH")
    return ffmpeg, ffprobe


def probe(ffprobe: str, video: Path) -> tuple[float, list[dict]]:
    out = subprocess.run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_chapters", str(video)],
                         capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    duration = float(data["format"]["duration"])
    chapters = [{"start": float(c["start_time"]), "end": float(c["end_time"]), "title": (c.get("tags") or {}).get("title", f"Chapter {i + 1}")}
                for i, c in enumerate(data.get("chapters") or [])]
    return duration, chapters


def parse_time(s: str) -> float:
    s = s.strip()
    if ":" in s:
        parts = [float(x) for x in s.split(":")]
        secs = 0.0
        for x in parts:
            secs = secs * 60 + x
        return secs
    return float(s)


def fmt(t: float) -> str:
    t = max(0.0, t)
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def chapter_at(chapters: list[dict], t: float) -> str | None:
    for c in chapters:
        if c["start"] <= t < c["end"]:
            return c["title"]
    return chapters[-1]["title"] if chapters and t >= chapters[-1]["start"] else None


def pick(args, duration: float, chapters: list[dict]) -> list[float]:
    times: list[float] = []
    if args.at:
        times += [parse_time(x) for x in args.at.split(",") if x.strip()]
    if args.every:
        n = int(duration // args.every)
        times += [i * args.every for i in range(n + 1)]
    if args.chapters:
        if not chapters:
            print("note: the video has no chapter markers; --chapters ignored", file=sys.stderr)
        times += [min(c["start"] + args.offset, c["end"] - 0.1) for c in chapters]
    if args.joins:
        if not chapters:
            print("note: the video has no chapter markers; --joins ignored", file=sys.stderr)
        for c in chapters[1:]:
            times += [c["start"] - args.join_gap, c["start"] + args.join_gap]
    if args.end:
        times += [duration - x for x in (args.end_span, args.end_span / 2, 0.3)]
    if not times:
        sys.exit("choose what to sample: --at, --every, --chapters, --joins and/or --end")
    clamped = sorted({round(min(max(t, 0.0), max(duration - 0.05, 0.0)), 2) for t in times})
    return clamped


def label_with_pillow(tile: Path, label: str) -> bool:
    """Write the label into the white strip under the frame. Pillow is optional; returns False when unavailable."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    img = Image.open(tile).convert("RGB")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=18)
    except TypeError:  # Pillow < 10.1 has no sized default font
        font = ImageFont.load_default()
    draw.text((10, img.height - 28), label, fill=(34, 34, 34), font=font)
    img.save(tile)
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Tile stills from a video into one labelled contact sheet.")
    ap.add_argument("video", type=Path)
    ap.add_argument("--at", help="comma-separated timestamps in seconds or m:ss")
    ap.add_argument("--every", type=float, help="one still every N seconds")
    ap.add_argument("--chapters", action="store_true", help="one still OFFSET seconds into every chapter")
    ap.add_argument("--offset", type=float, default=2.0, help="seconds into each chapter for --chapters (default 2)")
    ap.add_argument("--joins", action="store_true", help="stills just before and after every chapter boundary")
    ap.add_argument("--join-gap", type=float, default=0.6, help="seconds either side of a boundary for --joins (default 0.6)")
    ap.add_argument("--end", action="store_true", help="stills from the last END_SPAN seconds")
    ap.add_argument("--end-span", type=float, default=6.0, help="seconds before the end for --end (default 6)")
    ap.add_argument("--cols", type=int, default=3, help="tiles per row (default 3)")
    ap.add_argument("--width", type=int, default=640, help="tile width in pixels (default 640)")
    ap.add_argument("--out", type=Path, help="output PNG (default: <video>-sheet.png next to the video)")
    args = ap.parse_args()

    if not args.video.exists():
        sys.exit(f"no such video: {args.video}")
    ffmpeg, ffprobe = tools()
    duration, chapters = probe(ffprobe, args.video)
    times = pick(args, duration, chapters)
    out = args.out or args.video.with_name(args.video.stem + "-sheet.png")

    unlabelled: list[str] = []
    with tempfile.TemporaryDirectory(prefix="contact-sheet-") as tmp:
        tiles = []
        for i, t in enumerate(times):
            label = fmt(t) + (f" · {chapter_at(chapters, t)}" if chapters else "")
            tile = Path(tmp) / f"t{i:03d}.png"
            # Label below the frame so it never hides UI; drawtext needs no font file when fontconfig is present,
            # so fall back to an unlabelled tile if the ffmpeg build lacks it.
            safe = re.sub(r"[\\:'%]", " ", label)
            base = ["-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i", str(args.video), "-frames:v", "1"]
            vf = (f"scale={args.width}:-2,pad=iw:ih+34:0:0:white,"
                  f"drawtext=text='{safe}':x=10:y=h-26:fontsize=18:fontcolor=0x222222")
            r = subprocess.run([ffmpeg, *base, "-vf", vf, str(tile)], capture_output=True, text=True)
            if r.returncode != 0:  # ffmpeg built without drawtext (no libfreetype): label with Pillow, else unlabelled
                subprocess.run([ffmpeg, *base, "-vf", f"scale={args.width}:-2,pad=iw:ih+34:0:0:white", str(tile)], check=True)
                if not label_with_pillow(tile, label):
                    unlabelled.append(label)
            tiles.append(tile)

        cols = max(1, min(args.cols, len(tiles)))
        rows = math.ceil(len(tiles) / cols)
        # Pad the last row with blank tiles of the same size so the grid is rectangular.
        filler = []
        for j in range(rows * cols - len(tiles)):
            f = Path(tmp) / f"blank{j}.png"
            subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-i", str(tiles[0]), "-vf", "drawbox=c=white:t=fill", "-frames:v", "1", str(f)], check=True)
            filler.append(f)
        grid = tiles + filler
        inputs = [x for t in grid for x in ("-i", str(t))]
        if len(grid) == 1:
            shutil.copyfile(grid[0], out)
        else:
            # xstack positions: column c sits at w0+w0+... (c times), row r at h0+h0+... (r times); all tiles share one size.
            layout = "|".join(("0" if c == 0 else "+".join(["w0"] * c)) + "_" + ("0" if r == 0 else "+".join(["h0"] * r))
                              for r in range(rows) for c in range(cols))
            fc = "".join(f"[{i}:v]" for i in range(len(grid))) + f"xstack=inputs={len(grid)}:layout={layout}:fill=white"
            subprocess.run([ffmpeg, "-loglevel", "error", "-y", *inputs, "-filter_complex", fc, "-frames:v", "1", str(out)], check=True)

    if unlabelled:
        # No way to draw text: write the tile order next to the sheet instead.
        legend = out.with_suffix(".txt")
        legend.write_text("\n".join(f"{i + 1:2d}. {lab}" for i, lab in enumerate(unlabelled)) + "\n", encoding="utf-8")
        print(f"note: ffmpeg has no drawtext and Pillow is not installed; tile labels are in {legend}", file=sys.stderr)
    print(out.resolve())
    print(f"{len(times)} stills: " + ", ".join(fmt(t) for t in times), file=sys.stderr)


if __name__ == "__main__":
    main()
