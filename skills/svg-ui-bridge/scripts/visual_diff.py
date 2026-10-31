#!/usr/bin/env python3
"""Compare a screenshot of the real UI against the SVG design and report where they differ.

This is the evidence step for verification-before-completion: it prints a mismatch % overall
and per component (when a manifest is given), writes a side-by-side + heat-map image, and exits
non-zero when the overall mismatch exceeds --max.

  python visual_diff.py design/settings.svg shots/settings.png
  python visual_diff.py design/settings.svg shots/settings.png --manifest design/settings.components.json
  python visual_diff.py design/settings.png shots/settings.png --tol 24 --max 2.0

Notes
- The screenshot must show the same region as the SVG canvas (crop to the component/screen).
  If sizes differ the screenshot is resized to the design size and a warning is printed.
- --tol is the per-pixel colour distance (0-255) treated as "same"; raise it for anti-aliasing /
  font-rendering noise (16-32 is typical). --shift gives 1-2 px positional slack.
- PASS needs BOTH: overall <= --max and every component <= --max-component. The per-component
  gate matters: a wrong button is <1 % of a whole screen but ~40 % of the button.
- Least noise for web projects: render the reference with the same engine as the app
  (SVG_UI_RENDERER=playwright).
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

# Windows consoles default to a legacy code page; never crash on a non-ASCII character.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image, ImageChops, ImageDraw  # noqa: E402


def to_png(path: Path, scale: float, td: str) -> Path:
    if path.suffix.lower() != ".svg":
        return path
    from _svgcommon import canvas_size, load_svg, render_svg_bytes, show_state
    tree = load_svg(path)
    out = Path(td) / (path.stem + ".ref.png")
    render_svg_bytes(show_state(tree, None), out, scale=scale, size=canvas_size(tree.getroot()))
    return out


def mismatch_mask(ref: Image.Image, act: Image.Image, tol: int, shift: int) -> Image.Image:
    """255 where a pixel differs by more than `tol` from every pixel of the other image within
    +/-`shift` px (both directions). Absorbs 1-px anti-aliasing / glyph-hinting offsets while still
    catching real size, spacing, colour and missing-element errors."""
    def one_way(a_, b_):
        best = None
        for dx in range(-shift, shift + 1):
            for dy in range(-shift, shift + 1):
                d = ImageChops.difference(a_, ImageChops.offset(b_, dx, dy)).convert("L")
                best = d if best is None else ImageChops.darker(best, d)
        return best
    d = ImageChops.lighter(one_way(ref, act), one_way(act, ref))
    return d.point(lambda v: 255 if v > tol else 0)


def flatten(im: Image.Image, bg=(255, 255, 255)) -> Image.Image:
    im = im.convert("RGBA")
    base = Image.new("RGBA", im.size, bg + (255,))
    base.alpha_composite(im)
    return base.convert("RGB")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("design", help="design .svg or its rendered .png")
    ap.add_argument("actual", help="screenshot .png of the implementation")
    ap.add_argument("--manifest", help="<name>.components.json for per-component scores")
    ap.add_argument("--scale", type=float, default=1.0, help="device pixel ratio of the screenshot")
    ap.add_argument("--tol", type=int, default=24)
    ap.add_argument("--max", type=float, default=2.0, help="max overall mismatch %% to pass")
    ap.add_argument("--max-component", type=float, default=10.0,
                    help="max mismatch %% for any single component (needs --manifest)")
    ap.add_argument("--shift", type=int, default=1, help="px of positional slack (0 = exact)")
    ap.add_argument("--bg", default="#ffffff", help="background used to flatten transparency")
    ap.add_argument("-o", "--out", help="diff image path (default: <actual>.diff.png)")
    a = ap.parse_args()

    bg = tuple(int(a.bg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    with tempfile.TemporaryDirectory() as td:
        ref = flatten(Image.open(to_png(Path(a.design), a.scale, td)), bg)
    act = flatten(Image.open(a.actual), bg)
    if act.size != ref.size:
        print(f"warn: screenshot {act.size} != design {ref.size}; resizing screenshot to design size")
        act = act.resize(ref.size, Image.LANCZOS)

    mask = mismatch_mask(ref, act, a.tol, a.shift)
    W, H = ref.size
    total = W * H
    bad = mask.histogram()[255]
    overall = 100.0 * bad / total

    per = []
    if a.manifest:
        man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
        for c in man["components"]:
            if not c.get("bbox"):
                continue
            x, y, w, h = (v * a.scale for v in c["bbox"])
            box = (int(x), int(y), int(min(W, x + w)), int(min(H, y + h)))
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            region = mask.crop(box)
            n = (box[2] - box[0]) * (box[3] - box[1])
            pct = 100.0 * region.histogram()[255] / n
            per.append({"id": c["id"], "mismatch_pct": round(pct, 2), "box": box})
        per.sort(key=lambda r: -r["mismatch_pct"])

    # side-by-side: design | implementation | heat-map
    heat = Image.new("RGB", ref.size, (255, 255, 255))
    heat.paste(Image.blend(ref, Image.new("RGB", ref.size, (255, 255, 255)), 0.75))
    red = Image.new("RGB", ref.size, (230, 30, 60))
    heat.paste(red, mask=mask)
    d = ImageDraw.Draw(heat)
    for r in per[:5]:
        if r["mismatch_pct"] > a.max_component:
            d.rectangle(r["box"], outline=(230, 30, 60), width=2)
            d.text((r["box"][0] + 3, r["box"][1] + 2), r["id"], fill=(230, 30, 60))
    sheet = Image.new("RGB", (W * 3 + 20, H), (240, 240, 240))
    for i, im in enumerate((ref, act, heat)):
        sheet.paste(im, (i * (W + 10), 0))
    out = Path(a.out) if a.out else Path(a.actual).with_suffix(".diff.png")
    sheet.save(out)

    worst = [r for r in per if r["mismatch_pct"] > a.max_component]
    ok = overall <= a.max and not worst
    print(f"overall mismatch {overall:.2f}% (max {a.max}%), components over {a.max_component}%: "
          f"{len(worst)}  [tol {a.tol}, shift {a.shift}px] -> {'PASS' if ok else 'FAIL'}")
    for r in per:
        flag = "  <-- over limit" if r["mismatch_pct"] > a.max_component else ""
        print(f"  {r['id']:<28} {r['mismatch_pct']:6.2f}%{flag}")
    print(f"diff image: {out}  (design | implementation | heat-map)")
    report = {"overall_pct": round(overall, 3), "pass": ok, "tol": a.tol, "shift": a.shift,
              "max": a.max, "max_component": a.max_component,
              "components": per, "diff_image": str(out)}
    out.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
