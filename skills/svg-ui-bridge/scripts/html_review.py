#!/usr/bin/env python3
"""Inspect a local static HTML draft; export screen PNGs and DOM geometry, not a visual diff.

python html_review.py design/settings.html --size 1280x800 --out shots/html-desktop
Exit 0: structural checks passed; 1: draft issues; 2: invalid arguments or capture failure.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from _svgcommon import _launch_browser


INSPECT = r"""() => {
  const errors = [], screens = [], ids = new Set();
  const visible = e => {
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  for (const e of document.querySelectorAll('[id]')) {
    if (ids.has(e.id)) errors.push(`Duplicate id: ${e.id}`);
    ids.add(e.id);
  }
  for (const e of document.querySelectorAll('*')) {
    if (['SCRIPT','IFRAME','OBJECT','EMBED'].includes(e.tagName.toUpperCase()) ||
        [...e.attributes].some(a => /^on/i.test(a.name) || /^javascript:/i.test(a.value.trim())) ||
        (e.tagName === 'META' && /refresh/i.test(e.httpEquiv)))
      errors.push(`Non-static content: ${e.tagName}#${e.id}`);
  }
  const roots = [...document.querySelectorAll('[data-screen]')];
  if (!roots.length) errors.push('No [data-screen] roots');
  for (const root of roots) {
    if (!/^[A-Z][A-Za-z0-9-]*$/.test(root.id)) errors.push('Screen needs a PascalCase id');
    if (!root.dataset.screen.trim()) errors.push(`Empty data-screen: ${root.id}`);
    if (!root.dataset.state) errors.push(`Missing data-state: ${root.id}`);
    if (root.parentElement?.closest('[data-screen]')) errors.push(`Nested screen: ${root.id}`);
    if (!visible(root)) { errors.push(`Hidden/empty screen: ${root.id}`); continue; }
    const box = root.getBoundingClientRect(), components = [], overflow = [];
    for (const e of [root, ...root.querySelectorAll('*')]) {
      if (!visible(e)) continue;
      const r = e.getBoundingClientRect();
      if (e.hasAttribute('data-component')) {
        if (!/^[A-Z][A-Za-z0-9-]*$/.test(e.id) || !e.dataset.component.trim())
          errors.push(`Component needs id and kind: ${root.id}/${e.id}`);
        const parent = e.parentElement?.closest('[data-component]');
        components.push({id:e.id, kind:e.dataset.component,
          parent:parent && root.contains(parent) ? parent.id : null,
          bbox:[r.x-box.x,r.y-box.y,r.width,r.height]});
      }
      // Geometry and scroll extents are heuristics, not a text/overlap proof.
      if (r.left < box.left-1 || r.right > box.right+1 ||
          r.top < box.top-1 || r.bottom > box.bottom+1 ||
          (e.clientWidth > 0 && e.scrollWidth > e.clientWidth+1) ||
          (e.clientHeight > 0 && e.scrollHeight > e.clientHeight+1))
        overflow.push(e.id || e.tagName.toLowerCase());
    }
    if (!components.length) errors.push(`No visible components: ${root.id}`);
    if (overflow.length) errors.push(`Overflow in ${root.id}: ${overflow.join(', ')}`);
    screens.push({id:root.id, name:root.dataset.screen, state:root.dataset.state,
      size:[box.width,box.height], components, overflow});
  }
  for (const e of document.querySelectorAll('[data-component]'))
    if (!e.closest('[data-screen]')) errors.push(`Component outside screen: ${e.id}`);
  return {errors, screens};
}"""


def review(target: Path, out: Path, width: int, height: int) -> dict:
    from playwright.sync_api import sync_playwright

    target = target.resolve()
    if not target.is_file() or target.suffix.lower() not in {'.html', '.htm'}:
        raise ValueError('target must be an existing local .html or .htm file')
    if width <= 0 or height <= 0:
        raise ValueError('viewport dimensions must be positive')
    out.mkdir(parents=True, exist_ok=True)
    blocked, failed = [], []

    def route_request(route):
        if urlsplit(route.request.url).scheme in {'file', 'data'}:
            route.continue_()
        else:
            blocked.append(route.request.url)
            route.abort()

    with sync_playwright() as p:
        browser = _launch_browser(p, args=['--disable-lcd-text'])
        try:
            context = browser.new_context(viewport={'width': width, 'height': height},
                                          device_scale_factor=1, java_script_enabled=False,
                                          service_workers='block', reduced_motion='reduce')
            context.route('**/*', route_request)
            page = context.new_page()
            page.on('requestfailed', lambda request: failed.append(request.url))
            page.goto(target.as_uri(), wait_until='load')
            page.evaluate('() => document.fonts.ready')
            # Freeze authored animations so geometry and screenshots refer to one static state.
            # add_style_tag waits for an onload callback that cannot fire with page JS disabled.
            page.evaluate("""() => {
              const style = document.createElement('style');
              style.textContent = '*,*::before,*::after { animation: none !important; transition: none !important; }';
              document.head.append(style);
            }""")
            report = page.evaluate(INSPECT)
            report.update(format='html-review-v1', source=str(target),
                          viewport=[width, height], scale=1, blocked=blocked, failed=failed)
            report['errors'] += [f'Blocked external resource: {u}' for u in sorted(set(blocked))]
            report['errors'] += [f'Failed resource: {u}' for u in sorted(set(failed)-set(blocked))]
            # No ambiguous captures for malformed ids or incomplete resources.
            if not report['errors']:
                for screen in report['screens']:
                    filename = f"{screen['id']}.png"
                    page.locator(f"[id='{screen['id']}']").screenshot(path=str(out / filename))
                    screen['screenshot'] = filename
            report['status'] = 'FAIL' if report['errors'] else 'PASS'
            (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            return report
        finally:
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--size', default='1280x800')
    args = parser.parse_args()
    size = re.fullmatch(r'([1-9][0-9]*)x([1-9][0-9]*)', args.size)
    if not size:
        parser.error('--size must contain positive WIDTHxHEIGHT')
    try:
        report = review(args.target, args.out, *map(int, size.groups()))
    except Exception as exc:
        print(f'HTML review failed: {exc}', file=sys.stderr)
        return 2
    for error in report['errors']:
        print(error)
    print(f"{report['status']}: draft structure only; inspect PNGs visually. Report: {args.out / 'report.json'}")
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
