#!/usr/bin/env python3
"""Render a design SVG to PNG for human review or as the visual-diff reference.

Examples
  python svg_render.py design/settings.svg                       # -> design/settings.png
  python svg_render.py design/settings.svg --scale 2             # retina-size review image
  python svg_render.py design/settings.svg --state hover -o out.png
  python svg_render.py design/settings.svg --component SaveButton
  python svg_render.py design/settings.svg --all-states          # one PNG per data-state value
  python svg_render.py --job '{"input":"design/settings.svg", ...}'   # Quick Edit Snapshot JSON
  python svg_render.py --job snapshot.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _svgcommon import canvas_size, isolate, load_svg, local, render_svg_bytes, show_state  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

HIGHLIGHTS = ((255, 0, 170), (0, 230, 118))  # magenta, or green when the design's primary is close
DASH = 10


def highlight_colour(root: ET.Element) -> tuple[int, int, int]:
    css = "".join((s.text or "") for s in root.iter() if local(s.tag) == "style")
    m = re.search(r"--color-primary\s*:\s*#([0-9a-fA-F]{6})", css)
    if not m:
        return HIGHLIGHTS[0]
    primary = [int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4)]
    return HIGHLIGHTS[1] if sum(abs(a - b) for a, b in zip(primary, HIGHLIGHTS[0])) < 160 else HIGHLIGHTS[0]


def dashed_rect(draw, box, colour, width: int) -> None:
    x0, y0, x1, y1 = box
    for x in range(x0, x1, DASH * 2):
        draw.line([(x, y0), (min(x + DASH, x1), y0)], fill=colour, width=width)
        draw.line([(x, y1), (min(x + DASH, x1), y1)], fill=colour, width=width)
    for y in range(y0, y1, DASH * 2):
        draw.line([(x0, y), (x0, min(y + DASH, y1))], fill=colour, width=width)
        draw.line([(x1, y), (x1, min(y + DASH, y1))], fill=colour, width=width)


def annotate(im, job: dict, visible: list[int], scale: float, colour) -> None:
    from PIL import ImageDraw
    draw = ImageDraw.Draw(im)
    width = max(2, round(2 * scale))
    for n, item in enumerate(job.get("selection", []), 1):
        x, y, w, h = item["bbox"]
        box = [round((x - visible[0]) * scale), round((y - visible[1]) * scale),
               round((x + w - visible[0]) * scale), round((y + h - visible[1]) * scale)]
        if item.get("kind") == "region":
            dashed_rect(draw, box, colour, width)
        else:
            draw.rectangle(box, outline=colour, width=width)
        label = str(n)
        tl, tt, tr, tb = draw.textbbox((0, 0), label)
        lx, ly = box[0], max(0, box[1] - (tb - tt) - 8)
        draw.rectangle([lx, ly, lx + tr - tl + 8, ly + tb - tt + 8], fill=colour)
        draw.text((lx + 4 - tl, ly + 4 - tt), label, fill=(0, 0, 0))


def find_input(name: str, job_file: Path | None) -> Path:
    path = Path(name)
    if path.exists() or job_file is None:
        return path
    return job_file.parent / path


def run_job(job: dict, job_file: Path | None) -> None:
    from PIL import Image
    src = find_input(job["input"], job_file)
    tree = load_svg(src)
    state = job.get("state")
    data = show_state(tree, None if state in (None, "default") else state)
    size = canvas_size(tree.getroot())
    visible = (job.get("view") or {}).get("visible") or [0, 0, size[0], size[1]]
    colour = highlight_colour(tree.getroot())
    for output in job.get("outputs", []):
        scale = float(output.get("scale", 1))
        out = Path(output["path"].replace("<tmp>", tempfile.gettempdir()))
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as td:
            full = Path(td) / "full.png"
            render_svg_bytes(data, full, scale=scale, size=size)
            with Image.open(full) as im:
                x, y, w, h = visible
                crop = im.convert("RGBA").crop((round(x * scale), round(y * scale),
                                                round((x + w) * scale), round((y + h) * scale)))
        if output.get("highlight"):
            annotate(crop, job, visible, scale, colour)
        crop.save(out)
        print(f"rendered {out}  ({crop.width}x{crop.height}, {output.get('label', '')})")


def load_jobs(arg: str) -> tuple[list[dict], Path | None]:
    if arg.lstrip()[:1] in ("{", "["):
        parsed, job_file = json.loads(arg), None
    else:
        job_file = Path(arg)
        parsed = json.loads(job_file.read_text(encoding="utf-8"))
    return (parsed if isinstance(parsed, list) else [parsed]), job_file


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("svg", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--state", help="show this data-state instead of 'default'")
    ap.add_argument("--component", help="render only the element with this id")
    ap.add_argument("--all-states", action="store_true")
    ap.add_argument("--job", help="Quick Edit Snapshot JSON, as text or a .json file")
    a = ap.parse_args()

    if a.job:
        jobs, job_file = load_jobs(a.job)
        for job in jobs:
            run_job(job, job_file)
        return 0
    if not a.svg:
        ap.error("the svg argument is required unless --job is given")

    src = Path(a.svg)
    tree = load_svg(src)
    size = canvas_size(tree.getroot())

    states = [a.state]
    if a.all_states:
        found = sorted({e.get("data-state") for e in tree.getroot().iter() if e.get("data-state")})
        states = [None] + [s for s in found if s != "default"]

    for st in states:
        data = show_state(tree, st)
        if a.component:
            data = isolate(ET.ElementTree(ET.fromstring(data)), a.component)
        if a.out and len(states) == 1:
            out = Path(a.out)
        else:
            suffix = (f".{a.component}" if a.component else "") + (f".{st}" if st else "")
            out = src.with_name(src.stem + suffix + ".png")
        used = render_svg_bytes(data, out, scale=a.scale, size=size)
        print(f"rendered {out}  ({int(size[0]*a.scale)}x{int(size[1]*a.scale)}, via {used})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
