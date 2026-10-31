#!/usr/bin/env python3
"""Screenshot a web page or local HTML file for visual_diff.py.

  python screenshot_web.py http://localhost:5173/settings -o shots/settings.png --size 1280x800
  python screenshot_web.py build/index.html -o shots/home.png --size 390x844 --scale 2 --wait-ms 500

Uses Playwright with its own Chromium, else the system Chrome or Edge. Opens only the given target:
requests to any other origin are blocked and listed, and a file target can only load local files.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _svgcommon import _launch_browser  # noqa: E402

ALLOWED_SCHEMES = ("http", "https", "file")


def target_url(target: str) -> str:
    """Turn the argument into a URL, or raise ValueError."""
    if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]+://", target):
        if urlsplit(target).scheme.lower() not in ALLOWED_SCHEMES:
            raise ValueError(f"only {', '.join(ALLOWED_SCHEMES)} URLs can be opened: {target}")
        return target
    path = Path(target)
    if not path.is_file():
        raise ValueError(f"no such file: {target}")
    return path.resolve().as_uri()


def origin(url: str) -> tuple[str, str]:
    u = urlsplit(url)
    return u.scheme.lower(), u.netloc.lower()


def shoot(url: str, out: Path, width: int, height: int, scale: float, wait_ms: int) -> list[str]:
    """Capture the page and return the requests that were blocked."""
    from playwright.sync_api import sync_playwright  # type: ignore
    allowed = origin(url)
    blocked: list[str] = []

    def only_target(route):
        req_url = route.request.url
        if origin(req_url) == allowed:
            route.continue_()
        else:
            blocked.append(req_url)
            route.abort()

    with sync_playwright() as p:
        # The design reference is rendered as an image, which never uses LCD text. Without this flag
        # the colour fringes on page text read as mismatches, enough to fail a small text component.
        b = _launch_browser(p, args=["--disable-lcd-text"])
        pg = b.new_page(viewport={"width": width, "height": height}, device_scale_factor=scale)
        pg.route("**/*", only_target)
        resp = pg.goto(url, wait_until="load")
        if resp is not None and resp.status >= 400:
            b.close()
            raise RuntimeError(f"{url} returned HTTP {resp.status}")
        pg.wait_for_timeout(wait_ms)
        pg.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": width, "height": height})
        b.close()
    return blocked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="http(s) URL or local HTML file")
    ap.add_argument("-o", "--out", required=True, help="output PNG")
    ap.add_argument("--size", default="1280x800", help="viewport as WIDTHxHEIGHT in CSS px")
    ap.add_argument("--scale", type=float, default=1.0, help="device pixel ratio")
    ap.add_argument("--wait-ms", type=int, default=300, help="wait after load, in ms")
    a = ap.parse_args()

    m = re.fullmatch(r"(\d+)x(\d+)", a.size)
    if not m:
        print(f"--size must look like 1280x800, got {a.size}", file=sys.stderr)
        return 2
    width, height = int(m.group(1)), int(m.group(2))
    try:
        url = target_url(a.target)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        blocked = shoot(url, out, width, height, a.scale, a.wait_ms)
    except ImportError:
        print("Playwright is missing: python -m pip install playwright", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"screenshot failed: {e}", file=sys.stderr)
        return 1

    for b in blocked:
        print(f"blocked {b}")
    print(f"wrote {out}  ({int(width * a.scale)}x{int(height * a.scale)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
