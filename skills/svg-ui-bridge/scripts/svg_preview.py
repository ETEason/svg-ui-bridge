#!/usr/bin/env python3
"""Browser review page for design SVGs — the human-facing view (no PNG needed).

Builds one self-contained HTML page with every SVG side by side:
  - state switcher (default / hover / disabled / … from data-state)
  - hover a component to outline it and see id, kind, layout and note
  - component tree sidebar, zoom, light/dark backdrop

  python svg_preview.py design/settings.svg              # writes design/_preview.html and opens it
  python svg_preview.py design/*.svg --no-open
  python svg_preview.py design --serve                   # live: http://localhost:8765, auto-reloads
                                                         # whenever an SVG in design/ changes
"""
from __future__ import annotations

import argparse
import http.server
import json
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _svgcommon import components, load_svg  # noqa: E402

PAGE = r"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SVG Design Review</title>
<style>
:root{--bg:#f3f4f7;--panel:#fff;--text:#1d2230;--muted:#6b7280;--line:#e3e6ec;--hi:#e5484d}
:root[data-theme=dark]{--bg:#0b0d11;--panel:#151821;--text:#e8eaf0;--muted:#8b93a7;--line:#262b36}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,"Noto Sans TC",sans-serif}
header{position:sticky;top:0;z-index:5;display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:10px 16px;background:var(--panel);border-bottom:1px solid var(--line)}
header b{font-size:15px}select,button{font:inherit;padding:4px 10px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--text);cursor:pointer}
.live{font-size:12px;color:#16a34a}.wrap{display:flex;gap:16px;padding:16px;align-items:flex-start}
aside{flex:0 0 260px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;position:sticky;top:64px;max-height:calc(100vh - 80px);overflow:auto}
aside h3{margin:4px 0 8px;font-size:13px;color:var(--muted)}aside li{list-style:none;padding:2px 6px;border-radius:4px;cursor:default;font-family:ui-monospace,monospace;font-size:12px}
aside li:hover,aside li.on{background:var(--hi);color:#fff}aside ul{margin:0;padding:0}
main{flex:1;min-width:0;display:flex;flex-direction:column;gap:20px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;overflow:auto}
.card h2{margin:0 0 8px;font-size:14px}.card .meta{color:var(--muted);font-size:12px;font-weight:400}
.stage{transform-origin:0 0}
#tip{position:fixed;pointer-events:none;z-index:9;background:#111;color:#fff;font-size:12px;padding:6px 8px;border-radius:6px;max-width:320px;display:none}
#tip code{color:#ffb4b4}
@media (max-width:800px){.wrap{flex-direction:column}aside{position:static;flex:none;width:100%}}
</style></head><body>
<header><b>SVG Design Review</b>
<label>狀態 <select id="state"></select></label>
<label>縮放 <select id="zoom"><option>0.5</option><option>0.75</option><option selected>1</option><option>1.5</option><option>2</option></select></label>
<button id="theme">切換背景</button><span id="live" class="live"></span></header>
<div class="wrap"><aside><h3>元件（滑過可定位）</h3><ul id="tree"></ul></aside><main id="main"></main></div>
<div id="tip"></div>
<script>
const DATA = __DATA__;
const LIVE = __LIVE__;
const main=document.getElementById('main'),tree=document.getElementById('tree'),tip=document.getElementById('tip');
const states=new Set(['default']);const roots=[];
DATA.forEach(d=>{
  const c=document.createElement('section');c.className='card';
  c.innerHTML=`<h2>${d.screen} <span class="meta">${d.file} · ${d.target||''} · ${d.comps.length} components</span></h2><div class="stage"></div>`;
  main.appendChild(c);
  /* each SVG lives in its own shadow root so ids and :root tokens of different screens don't clash */
  const host=c.querySelector('.stage'), sr=host.attachShadow({mode:'open'});
  sr.innerHTML='<style>svg{display:block;box-shadow:0 1px 4px #0003}</style>'+d.svg.replace(/:root\b/g,':host');
  roots.push({sr,file:d.file});
  d.states.forEach(s=>states.add(s));
  const h=document.createElement('li');h.style.cssText='font-weight:700;font-family:inherit';h.textContent=d.screen;tree.appendChild(h);
  d.comps.forEach(k=>{const li=document.createElement('li');li.textContent=' '.repeat(k.depth*2)+k.id;li.dataset.id=k.id;li.dataset.file=d.file;tree.appendChild(li);});
});
const sel=document.getElementById('state');[...states].forEach(s=>sel.add(new Option(s,s)));
function applyState(){const s=sel.value;roots.forEach(({sr})=>sr.querySelectorAll('[data-state]').forEach(e=>{
  const show=e.dataset.state===s||(e.dataset.state==='default'&&!e.parentNode.querySelector(':scope>[data-state="'+s+'"]'));
  e.style.display=show?'inline':'none';}));
  /* components without the chosen state keep showing their default layer */}
sel.onchange=()=>{applyState();try{sessionStorage.setItem('st',sel.value)}catch(e){}};
document.getElementById('zoom').onchange=e=>{document.querySelectorAll('.stage').forEach(s=>s.style.transform=`scale(${e.target.value})`);try{sessionStorage.setItem('zm',e.target.value)}catch(_){}};
document.getElementById('theme').onclick=()=>{const r=document.documentElement;r.dataset.theme=r.dataset.theme==='dark'?'light':'dark';};
function info(g){return `<code>#${g.id}</code> ${g.dataset.component||''}${g.dataset.layout?'<br>layout: '+g.dataset.layout:''}${g.dataset.note?'<br>note: '+g.dataset.note:''}${g.dataset.bind?'<br>bind: '+g.dataset.bind:''}`}
let cur=null,box=null;
function mark(g){if(g===cur)return;cur=g;if(box){box.remove();box=null;}
  if(g&&g.ownerSVGElement){const b=g.getBBox(),NS='http://www.w3.org/2000/svg';box=document.createElementNS(NS,'rect');
    for(const[k,v]of Object.entries({x:b.x-2,y:b.y-2,width:b.width+4,height:b.height+4,fill:'none',stroke:'#e5484d','stroke-width':2,'stroke-dasharray':'6 3','pointer-events':'none'}))box.setAttribute(k,v);
    g.ownerSVGElement.appendChild(box);}document.querySelectorAll('#tree li').forEach(li=>li.classList.toggle('on',g&&li.dataset.id===g.id));}
function compAt(e){for(const n of e.composedPath()){if(n.tagName==='g'&&n.dataset&&n.dataset.component!==undefined)return n;if(n===main)break;}return null;}
main.addEventListener('mousemove',e=>{const g=compAt(e);if(!g){mark(null);tip.style.display='none';return;}
  mark(g);tip.innerHTML=info(g);tip.style.display='block';const tw=tip.offsetWidth,th=tip.offsetHeight;tip.style.left=Math.min(e.clientX+14,innerWidth-tw-8)+'px';tip.style.top=(e.clientY+14+th>innerHeight?e.clientY-th-10:e.clientY+14)+'px';});
main.addEventListener('mouseleave',()=>{mark(null);tip.style.display='none'});
tree.addEventListener('mouseover',e=>{const id=e.target.dataset&&e.target.dataset.id;if(!id)return;const r=roots.find(x=>x.file===e.target.dataset.file);const g=r&&r.sr.getElementById(id);mark(g);if(g)g.scrollIntoView({block:'nearest',inline:'nearest'});});
try{const s=sessionStorage.getItem('st');if(s&&[...sel.options].some(o=>o.value===s))sel.value=s;const z=sessionStorage.getItem('zm');if(z){document.getElementById('zoom').value=z;document.getElementById('zoom').onchange({target:{value:z}})}}catch(e){}
applyState();
if(LIVE){const l=document.getElementById('live');let v=null;l.textContent='● 即時預覽中';
  setInterval(()=>fetch('/__version').then(r=>r.text()).then(t=>{if(v&&t!==v)location.reload();v=t}).catch(()=>{l.textContent='○ 預覽伺服器已停止'}),1000);}
</script></body></html>"""


def collect(paths: list[Path]) -> list[dict]:
    out = []
    for p in paths:
        try:
            tree = load_svg(p)
        except Exception as e:  # half-written file while the agent is editing
            out.append({"file": p.name, "screen": p.stem + " (parse error)", "target": str(e),
                        "svg": "", "comps": [], "states": []})
            continue
        root = tree.getroot()
        comps = [{"id": g.get("id"), "depth": d} for g, d, _ in components(root) if g.get("id")]
        states = sorted({e.get("data-state") for e in root.iter() if e.get("data-state")} - {"default"})
        out.append({"file": p.name, "screen": root.get("data-screen") or p.stem,
                    "target": root.get("data-target") or "",
                    "svg": p.read_text(encoding="utf-8"), "comps": comps, "states": states})
    return out


def svg_files(targets: list[str]) -> list[Path]:
    files = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            files += sorted(x for x in p.glob("*.svg"))
        elif p.suffix.lower() == ".svg":
            files.append(p)
    return files


def build(targets: list[str], live: bool) -> str:
    data = json.dumps(collect(svg_files(targets)), ensure_ascii=False).replace("</", "<\\/")
    return PAGE.replace("__DATA__", data).replace("__LIVE__", "true" if live else "false")


def version(targets: list[str]) -> str:
    return ",".join(f"{p.name}:{p.stat().st_mtime_ns}" for p in svg_files(targets))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="+", help="SVG files and/or folders")
    ap.add_argument("-o", "--out", help="output HTML (default: <first folder>/_preview.html)")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--serve", action="store_true", help="live preview server with auto-reload")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()

    if not svg_files(a.targets):
        print("no .svg files found", file=sys.stderr)
        return 1

    if a.serve:
        targets = a.targets

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = (version(targets) if self.path == "/__version" else build(targets, True)).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8" if self.path == "/__version"
                                 else "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        url = f"http://localhost:{a.port}/"
        with socketserver.ThreadingTCPServer(("127.0.0.1", a.port), H) as srv:
            print(f"live preview at {url}  (Ctrl+C to stop; page reloads when an SVG changes)")
            if not a.no_open:
                threading.Timer(0.5, lambda: webbrowser.open(url)).start()
            try:
                srv.serve_forever()
            except KeyboardInterrupt:
                pass
        return 0

    first = svg_files(a.targets)[0]
    out = Path(a.out) if a.out else first.parent / "_preview.html"
    out.write_text(build(a.targets, False), encoding="utf-8")
    print(f"wrote {out}")
    if not a.no_open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
