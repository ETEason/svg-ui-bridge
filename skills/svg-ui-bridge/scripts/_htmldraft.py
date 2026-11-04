"""Shared helpers for static HTML/CSS drafts: their local CSS, tokens and standalone screens."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

HTML_SUFFIXES = {".html", ".htm"}
_LINK = re.compile(r"<link\b[^>]*>", re.I)
_ATTR = re.compile(r"""([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""")
_STYLE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.I | re.S)
_TOKEN = re.compile(r"--([\w-]+)\s*:\s*([^;}]+)[;}]")

# Moves one screen into an otherwise empty body: the same standalone view in preview, render and review.
ISOLATE_SCREEN = """id => { const s = document.getElementById(id); if (!s) return false;
  document.body.replaceChildren(s); document.body.style.margin = '0'; return true; }"""


def is_html(path: Path) -> bool:
    return path.suffix.lower() in HTML_SUFFIXES


def _attrs(tag: str) -> dict[str, str]:
    return {m.group(1).lower(): next(g for g in m.groups()[1:] if g is not None) for m in _ATTR.finditer(tag)}


def stylesheets(path: Path) -> tuple[list[Path], list[str]]:
    """Local stylesheets linked from the draft, and links that cannot be read locally."""
    text = path.read_text(encoding="utf-8", errors="replace")
    found, problems = [], []
    for tag in _LINK.findall(text):
        a = _attrs(tag)
        if "stylesheet" not in a.get("rel", "").lower() or not a.get("href"):
            continue
        href = a["href"]
        if urlsplit(href).scheme or href.startswith("//"):
            problems.append(href)
            continue
        css = (path.parent / unquote(href.split("#")[0].split("?")[0])).resolve()
        (found if css.is_file() else problems).append(css if css.is_file() else href)
    return found, problems


def css_text(path: Path) -> str:
    """All CSS a draft uses: linked local stylesheets, then inline <style> blocks; or the file itself."""
    if path.suffix.lower() == ".css":
        return path.read_text(encoding="utf-8", errors="replace")
    sheets, _ = stylesheets(path)
    parts = [p.read_text(encoding="utf-8", errors="replace") for p in sheets]
    parts += _STYLE.findall(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def css_tokens(path: Path) -> dict[str, str]:
    return {k: v.strip() for k, v in _TOKEN.findall(css_text(path))}


def local_only(blocked: list[str]):
    """Playwright route handler: allow file: and data: URLs, record and abort everything else."""
    def handle(route):
        if urlsplit(route.request.url).scheme in {"file", "data"}:
            route.continue_()
        else:
            blocked.append(route.request.url)
            route.abort()
    return handle


def open_draft(browser, path: Path, width: int, height: int = 800, scale: float = 1.0, blocked=None):
    """A page showing the draft with page JavaScript disabled and only local resources."""
    context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=scale,
                                  java_script_enabled=False, service_workers="block", reduced_motion="reduce")
    context.route("**/*", local_only(blocked if blocked is not None else []))
    page = context.new_page()
    page.goto(path.resolve().as_uri(), wait_until="load")
    page.evaluate("() => document.fonts.ready")
    # add_style_tag waits for an onload callback that cannot fire with page JS disabled
    page.evaluate("""() => { const s = document.createElement('style');
      s.textContent = '*,*::before,*::after { animation: none !important; transition: none !important; }';
      document.head.append(s); }""")
    return page


def render_screen(path: Path, screen: str, width: int, out: Path, scale: float = 1.0) -> list[float]:
    """Screenshot one [data-screen] alone in an empty page at this viewport width; return its CSS size."""
    from playwright.sync_api import sync_playwright  # type: ignore
    from _svgcommon import _launch_browser
    with sync_playwright() as p:
        browser = _launch_browser(p, args=["--disable-lcd-text"])
        try:
            page = open_draft(browser, path, width, scale=scale)
            if not page.evaluate(ISOLATE_SCREEN, screen):
                raise ValueError(f"no element with id '{screen}' in {path}")
            element = page.locator(f"[id='{screen}']")
            element.screenshot(path=str(out))
            box = element.bounding_box()
            return [box["width"], box["height"]]
        finally:
            browser.close()
