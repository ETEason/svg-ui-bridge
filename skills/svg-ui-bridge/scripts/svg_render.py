#!/usr/bin/env python3
"""Render a design SVG to PNG for human review or as the visual-diff reference.

Examples
  python svg_render.py design/settings.svg                       # -> design/settings.png
  python svg_render.py design/settings.svg --scale 2             # retina-size review image
  python svg_render.py design/settings.svg --state hover -o out.png
  python svg_render.py design/settings.svg --component SaveButton
  python svg_render.py design/settings.svg --all-states          # one PNG per data-state value
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _svgcommon import canvas_size, isolate, load_svg, render_svg_bytes, show_state  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("svg")
    ap.add_argument("-o", "--out")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--state", help="show this data-state instead of 'default'")
    ap.add_argument("--component", help="render only the element with this id")
    ap.add_argument("--all-states", action="store_true")
    a = ap.parse_args()

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
