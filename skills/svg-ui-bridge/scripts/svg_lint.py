#!/usr/bin/env python3
"""Check that a design SVG follows the svg-ui-bridge conventions before it is used as a spec.

Exit code 0 = no errors (warnings allowed), 1 = errors found.

  python svg_lint.py design/settings.svg
  python svg_lint.py design/*.svg --strict      # warnings also fail
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _svgcommon import canvas_size, components, load_svg, local  # noqa: E402

PASCAL = re.compile(r"^[A-Z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*$")
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
LAYOUT_KEYS = {"row", "col", "stack", "grid", "absolute", "wrap"}
SHAPES = {"rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text", "image", "use"}


def lint(path: Path) -> tuple[list[str], list[str], dict]:
    errs, warns = [], []
    tree = load_svg(path)
    root = tree.getroot()
    raw = path.read_text(encoding="utf-8", errors="replace")

    w, h = canvas_size(root)
    if not root.get("viewBox"):
        errs.append("root <svg> has no viewBox — the canvas size must be explicit")
    if not root.get("data-screen"):
        warns.append("root <svg> has no data-screen=\"<ScreenName>\" — manifests will use the file name")

    comps = list(components(root))
    if not any(c.get("data-component") is not None for c, _, _ in comps):
        errs.append("no <g data-component> found — mark every UI component group")

    ids = {}
    for e in root.iter():
        i = e.get("id")
        if i:
            ids.setdefault(i, 0)
            ids[i] += 1
    for i, n in ids.items():
        if n > 1:
            errs.append(f"duplicate id '{i}' ({n}x)")

    for c, depth, parent in comps:
        cid = c.get("id")
        if not cid:
            errs.append(f"a data-component group (child of {parent or 'root'}) has no id")
            continue
        if not PASCAL.match(cid):
            warns.append(f"id '{cid}' is not PascalCase (e.g. SaveButton, NavBar-Item)")
        lay = c.get("data-layout")
        if lay:
            head = lay.split()[0]
            if head not in LAYOUT_KEYS:
                warns.append(f"{cid}: data-layout starts with '{head}', expected one of {sorted(LAYOUT_KEYS)}")
        else:
            kids = [k for k in c if local(k.tag) == "g" and k.get("data-component") is not None]
            if len(kids) >= 2:
                warns.append(f"{cid}: has {len(kids)} child components but no data-layout (how do they flow?)")

    # loose shapes directly under root (not in any component)
    loose = [local(k.tag) for k in root if local(k.tag) in SHAPES]
    if loose:
        warns.append(f"{len(loose)} shape(s) sit directly under <svg> outside any component: {sorted(set(loose))}")

    # colours: count hex literals outside :root/<style> token definitions
    style_text = "".join((s.text or "") for s in root.iter() if local(s.tag) == "style")
    hexes_total = len(HEX.findall(raw))
    hexes_in_style = len(HEX.findall(style_text))
    literal = hexes_total - hexes_in_style
    token_refs = len(re.findall(r"var\(--", raw)) + len(re.findall(r'data-token="', raw))
    if literal > 0 and token_refs == 0:
        warns.append(f"{literal} hard-coded colour(s) and no tokens — define colours as CSS variables in <style>")
    elif literal > 6:
        warns.append(f"{literal} hard-coded colour(s) outside <style>; prefer var(--token)")

    # text
    for t in root.iter():
        if local(t.tag) == "text" and not (t.get("font-family") or t.get("class") or "font" in (t.get("style") or "")):
            if "font-family" not in style_text:
                warns.append("<text> without a font-family and no font rule in <style>")
                break

    # path soup / size
    paths = [p for p in root.iter() if local(p.tag) == "path"]
    total_d = sum(len(p.get("d", "")) for p in paths)
    if total_d > 20000:
        warns.append(f"path data is {total_d} chars — looks like exported path soup; use rect/text/circle where possible")
    if any(local(e.tag) == "image" and (e.get("href") or "").startswith("data:") for e in root.iter()):
        warns.append("embedded base64 <image> — reference asset files instead (tokens + diffs stay small)")
    kb = path.stat().st_size / 1024
    if kb > 60:
        warns.append(f"file is {kb:.0f} KB — large SVGs defeat the token-saving purpose")

    stats = {"canvas": f"{w:g}x{h:g}", "components": len(comps), "kb": round(kb, 1),
             "states": sorted({e.get('data-state') for e in root.iter() if e.get('data-state')})}
    return errs, warns, stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("svgs", nargs="+")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    a = ap.parse_args()
    bad = False
    for s in a.svgs:
        p = Path(s)
        errs, warns, st = lint(p)
        print(f"== {p}  canvas {st['canvas']} · {st['components']} components · {st['kb']} KB · states {st['states'] or '-'}")
        for e in errs:
            print(f"  ERROR  {e}")
        for w in warns:
            print(f"  warn   {w}")
        if not errs and not warns:
            print("  OK")
        bad |= bool(errs) or (a.strict and bool(warns))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
