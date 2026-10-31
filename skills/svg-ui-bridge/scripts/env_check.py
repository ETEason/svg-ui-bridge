#!/usr/bin/env python3
"""Report what this environment can do and which svg-ui-bridge mode to use.

The last line of the normal output is MODE=local (live preview, can open a browser) or
MODE=sandbox (static preview only). Each renderer is tested by rendering a small SVG.

  python env_check.py
  python env_check.py --json
  SVG_UI_MODE=sandbox python env_check.py      # force a mode (local or sandbox)
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _svgcommon import detect_mode, has_gui, render_svg_bytes  # noqa: E402

RENDERERS = ["resvg", "rsvg", "playwright", "cairosvg"]
PROBE = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8" width="8" height="8">'
         b'<rect width="8" height="8" fill="#4f8cff"/></svg>')
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def probe_renderer(name: str) -> dict:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "probe.png"
        try:
            render_svg_bytes(PROBE, out, renderers=[name])
        except Exception as e:
            lines = str(e).splitlines()[1:]  # the first line is the generic "no renderer worked"
            return {"ok": False, "detail": lines[0][:160] if lines else "not installed"}
        if not out.exists() or out.read_bytes()[:8] != PNG_SIGNATURE:
            return {"ok": False, "detail": "did not produce a PNG"}
    return {"ok": True, "detail": ""}


def pillow_version() -> str | None:
    try:
        import PIL
    except ImportError:
        return None
    return PIL.__version__


def gui_reason() -> str:
    if sys.platform in ("win32", "darwin"):
        return platform.system()
    for var in ("DISPLAY", "WAYLAND_DISPLAY"):
        if os.environ.get(var):
            return var
    return "no DISPLAY or WAYLAND_DISPLAY"


def collect() -> dict:
    scripts = Path(__file__).resolve().parent
    renderers = {name: probe_renderer(name) for name in RENDERERS}
    forced = os.environ.get("SVG_UI_MODE", "").strip().lower()
    return {
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "pillow": pillow_version(),
        "renderers": renderers,
        "usable_renderers": [n for n, r in renderers.items() if r["ok"]],
        "gui": has_gui(),
        "gui_reason": gui_reason(),
        "skill_dir": str(scripts.parent),
        "scripts_dir": str(scripts),
        "mode": detect_mode(),
        "mode_source": "SVG_UI_MODE" if forced in ("local", "sandbox") else "detected",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON")
    a = ap.parse_args()

    info = collect()
    if a.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0

    print(f"os        {info['os']}")
    print(f"python    {info['python']}")
    print(f"pillow    {info['pillow'] or 'missing'}")
    for name, r in info["renderers"].items():
        print(f"renderer  {name:<11}{'ok' if r['ok'] else 'no: ' + r['detail']}")
    print(f"gui       {'yes' if info['gui'] else 'no'} ({info['gui_reason']})")
    print(f"scripts   {info['scripts_dir']}")
    print(f"source    {info['mode_source']}")
    print(f"MODE={info['mode']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
