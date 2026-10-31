"""Shared helpers for svg-ui-bridge scripts.

Only needs the Python standard library + Pillow. SVG rasterising tries, in order:
  1. resvg CLI            (fastest, most accurate; `cargo install resvg` or a release binary)
  2. rsvg-convert CLI     (librsvg; common on Linux, `choco install rsvg-convert` / MSYS2 on Windows)
  3. Playwright Chromium  (`pip install playwright && playwright install chromium`)
  4. cairosvg            (`pip install cairosvg`, needs the cairo DLL on Windows)
Set SVG_UI_RENDERER=resvg|rsvg|playwright|cairosvg to force one.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

# Windows consoles default to a legacy code page; never crash on a non-ASCII character.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


def local(tag: str) -> str:
    """Strip the XML namespace from a tag name."""
    return tag.split("}", 1)[-1] if "}" in tag else tag


def load_svg(path: str | Path) -> ET.ElementTree:
    return ET.parse(str(path))


def canvas_size(root: ET.Element) -> tuple[float, float]:
    vb = root.get("viewBox")
    if vb:
        parts = [float(x) for x in re.split(r"[ ,]+", vb.strip()) if x]
        if len(parts) == 4:
            return parts[2], parts[3]
    def num(v):
        m = re.match(r"[\d.]+", v or "")
        return float(m.group()) if m else 0.0
    return num(root.get("width")), num(root.get("height"))


def components(root: ET.Element):
    """Yield (element, depth, parent_component_id) for every <g data-component>.

    Falls back to <g id> when no data-component attributes exist at all."""
    has_marked = any(
        local(e.tag) == "g" and e.get("data-component") is not None for e in root.iter()
    )

    def walk(el, depth, parent):
        for child in el:
            if local(child.tag) != "g":
                walk(child, depth, parent)  # e.g. <a>, <switch>
                continue
            is_comp = child.get("data-component") is not None if has_marked else child.get("id") is not None
            if is_comp:
                yield child, depth, parent
                yield from walk(child, depth + 1, child.get("id"))
            else:
                yield from walk(child, depth, parent)

    yield from walk(root, 0, None)


# --------------------------------------------------------------------------- render

def _which_renderer() -> list[str]:
    forced = os.environ.get("SVG_UI_RENDERER")
    order = ["resvg", "rsvg", "playwright", "cairosvg"]
    return [forced] if forced else order


_VARDEF = re.compile(r"--([\w-]+)\s*:\s*([^;}]+)[;}]")
_VARUSE = re.compile(r"var\(\s*--([\w-]+)\s*(?:,\s*([^)]+))?\)")


def resolve_tokens(svg_bytes: bytes) -> bytes:
    """Inline CSS-variable tokens (var(--x)) as literal values.

    Browsers understand var() in SVG attributes, but resvg/librsvg/cairosvg do not (they paint
    black). Rasterisers therefore get a copy with every var() replaced by its :root value."""
    text = svg_bytes.decode("utf-8")
    defs: dict[str, str] = {}
    for block in re.findall(r"<style[^>]*>(.*?)</style>", text, flags=re.S):
        for k, v in _VARDEF.findall(block):
            defs[k] = v.strip()
    for _ in range(5):  # tokens that reference other tokens
        changed = False
        for k, v in list(defs.items()):
            nv = _VARUSE.sub(lambda m: defs.get(m.group(1), (m.group(2) or "").strip()) or m.group(0), v)
            if nv != v:
                defs[k], changed = nv, True
        if not changed:
            break
    text = _VARUSE.sub(lambda m: defs.get(m.group(1), (m.group(2) or "").strip()) or m.group(0), text)
    return text.encode("utf-8")


def render_svg_bytes(svg_bytes: bytes, out_png: str | Path, scale: float = 1.0,
                     size: tuple[float, float] | None = None) -> str:
    """Rasterise SVG bytes to PNG. Returns the renderer name that succeeded."""
    out_png = str(out_png)
    errors = []
    svg_bytes = resolve_tokens(svg_bytes)
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in.svg")
        with open(src, "wb") as f:
            f.write(svg_bytes)
        for name in _which_renderer():
            try:
                if name == "resvg" and shutil.which("resvg"):
                    subprocess.run(["resvg", f"--zoom={scale}", src, out_png], check=True,
                                   capture_output=True)
                    return "resvg"
                if name == "rsvg" and shutil.which("rsvg-convert"):
                    subprocess.run(["rsvg-convert", "-z", str(scale), "-o", out_png, src],
                                   check=True, capture_output=True)
                    return "rsvg-convert"
                if name == "playwright":
                    from playwright.sync_api import sync_playwright  # type: ignore
                    if size is None:
                        size = canvas_size(ET.fromstring(svg_bytes))
                    w, h = max(1, int(round(size[0]))), max(1, int(round(size[1])))
                    html = ("<html><body style='margin:0;background:transparent'>"
                            f"<img src='{Path(src).as_uri()}' width='{w}' height='{h}'>"
                            "</body></html>")
                    hp = os.path.join(td, "p.html")
                    with open(hp, "w", encoding="utf-8") as f:
                        f.write(html)
                    with sync_playwright() as p:
                        b = p.chromium.launch()
                        pg = b.new_page(viewport={"width": w, "height": h},
                                        device_scale_factor=scale)
                        pg.goto(Path(hp).as_uri())
                        pg.screenshot(path=out_png, omit_background=True,
                                      clip={"x": 0, "y": 0, "width": w, "height": h})
                        b.close()
                    return "playwright"
                if name == "cairosvg":
                    import cairosvg  # type: ignore
                    cairosvg.svg2png(bytestring=svg_bytes, write_to=out_png, scale=scale)
                    return "cairosvg"
            except Exception as e:  # try the next renderer
                errors.append(f"{name}: {e}")
    raise RuntimeError("No SVG renderer worked. Install one of resvg / rsvg-convert / "
                       "playwright / cairosvg.\n" + "\n".join(errors))


def isolate(tree: ET.ElementTree, keep_id: str) -> bytes:
    """Return SVG bytes where only element `keep_id` (plus <defs>/<style>) is visible."""
    import copy
    root = copy.deepcopy(tree.getroot())
    target = None
    parent_of = {c: p for p in root.iter() for c in p}
    for e in root.iter():
        if e.get("id") == keep_id:
            target = e
            break
    if target is None:
        raise KeyError(keep_id)
    keep = {target}
    node = target
    while node in parent_of:
        node = parent_of[node]
        keep.add(node)
    keep_sub = set(target.iter())

    def prune(el):
        for child in list(el):
            if local(child.tag) in ("defs", "style", "title", "desc", "metadata"):
                continue
            if child in keep_sub:
                continue
            if child in keep:
                prune(child)
            else:
                el.remove(child)
    prune(root)
    return ET.tostring(root, encoding="utf-8")


def show_state(tree: ET.ElementTree, state: str | None) -> bytes:
    """Show one data-state layer per component.

    For each group of sibling state layers: the layer matching `state` is shown; if the component
    has no such layer its 'default' layer stays visible. state=None shows 'default' everywhere."""
    import copy
    root = copy.deepcopy(tree.getroot())
    parent_of = {c: p for p in root.iter() for c in p}
    for e in root.iter():
        s = e.get("data-state")
        if s is None:
            continue
        siblings = {c.get("data-state") for c in parent_of.get(e, [])}
        want = state if state in siblings else "default"
        visible = s == want
        if not visible:
            e.set("display", "none")
        elif e.get("display") == "none":
            del e.attrib["display"]
    return ET.tostring(root, encoding="utf-8")
