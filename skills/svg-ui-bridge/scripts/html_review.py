#!/usr/bin/env python3
"""Inspect a local static HTML draft; export screen PNGs, DOM geometry and component manifests.

python html_review.py design/settings.html --size 1280x800 --out shots/html-desktop
python html_review.py design/settings.html --size 390x844 --out shots/html-mobile --standalone
Exit 0: structural checks passed; 1: draft issues; 2: invalid arguments or capture failure.

Each screen also gets <id>.components.json, the manifest format visual_diff.py --manifest reads.
--standalone measures and captures each screen alone at the viewport width, which is what an
implementation screenshot shows; use those files as the visual baseline.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _htmldraft import ISOLATE_SCREEN, css_tokens  # noqa: E402
from _svgcommon import _launch_browser  # noqa: E402


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
          bbox:[r.x-box.x,r.y-box.y,r.width,r.height], note:e.dataset.note || '',
          text:(e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 80)});
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


def manifest(screen: dict, source: Path, tokens: dict[str, str]) -> dict:
    """The SVG manifest schema for one HTML screen, so visual_diff.py --manifest can read it."""
    parents = {c['id']: c['parent'] for c in screen['components']}

    def depth(cid):
        n, p = 0, parents.get(cid)
        while p:
            n, p = n + 1, parents.get(p)
        return n

    return {'screen': screen['id'], 'source': source.name, 'format': 'html', 'state': screen['state'],
            'canvas': [round(v, 1) for v in screen['size']], 'tokens': tokens, 'undefined_tokens': [],
            'components': [{'id': c['id'], 'kind': c['kind'], 'parent': c['parent'], 'depth': depth(c['id']),
                            'bbox': [round(v, 1) for v in c['bbox']], 'layout': '', 'tokens': [],
                            'states': [screen['state']], 'text': [c['text']] if c.get('text') else [],
                            'note': c.get('note', '')} for c in screen['components']]}


def review(target: Path, out: Path, width: int, height: int, standalone: bool = False) -> dict:
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
            def load(screen_id=None):
                page.goto(target.as_uri(), wait_until='load')
                page.evaluate('() => document.fonts.ready')
                # Freeze authored animations so geometry and screenshots refer to one static state.
                # add_style_tag waits for an onload callback that cannot fire with page JS disabled.
                page.evaluate("""() => {
                  const style = document.createElement('style');
                  style.textContent = '*,*::before,*::after { animation: none !important; transition: none !important; }';
                  document.head.append(style);
                }""")
                if screen_id:
                    page.evaluate(ISOLATE_SCREEN, screen_id)

            load()
            report = page.evaluate(INSPECT)
            report.update(format='html-review-v1', source=str(target), viewport=[width, height], scale=1,
                          standalone=standalone, blocked=blocked, failed=failed)
            if standalone and not report['errors']:
                # measure each screen alone at the viewport width, as an implementation would show it
                for screen in report['screens']:
                    load(screen['id'])
                    alone = page.evaluate(INSPECT)
                    report['errors'] += [f"{e} (standalone)" for e in alone['errors']]
                    if alone['screens']:
                        screen.update({k: alone['screens'][0][k] for k in ('size', 'components', 'overflow')})
            report['errors'] += [f'Blocked external resource: {u}' for u in sorted(set(blocked))]
            report['errors'] += [f'Failed resource: {u}' for u in sorted(set(failed)-set(blocked))]
            # No ambiguous captures for malformed ids or incomplete resources.
            if not report['errors']:
                tokens = css_tokens(target)
                for screen in report['screens']:
                    if standalone:
                        load(screen['id'])
                    filename = f"{screen['id']}.png"
                    page.locator(f"[id='{screen['id']}']").screenshot(path=str(out / filename))
                    screen['screenshot'] = filename
                    screen['manifest'] = f"{screen['id']}.components.json"
                    (out / screen['manifest']).write_text(json.dumps(manifest(screen, target, tokens), ensure_ascii=False,
                                                                     indent=2), encoding='utf-8')
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
    parser.add_argument('--standalone', action='store_true',
                        help='capture each screen alone at the viewport width (implementation baseline)')
    args = parser.parse_args()
    size = re.fullmatch(r'([1-9][0-9]*)x([1-9][0-9]*)', args.size)
    if not size:
        parser.error('--size must contain positive WIDTHxHEIGHT')
    try:
        report = review(args.target, args.out, *map(int, size.groups()), standalone=args.standalone)
    except Exception as exc:
        print(f'HTML review failed: {exc}', file=sys.stderr)
        return 2
    for error in report['errors']:
        print(error)
    print(f"{report['status']}: draft structure only; inspect PNGs visually. Report: {args.out / 'report.json'}")
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
