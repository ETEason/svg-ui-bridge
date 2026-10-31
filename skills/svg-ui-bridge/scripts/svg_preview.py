#!/usr/bin/env python3
"""Browser review page for design SVGs — the human-facing view (no PNG needed).

Builds one self-contained HTML page with every SVG side by side:
  - state switcher (default / hover / disabled / … from data-state)
  - hover a component to outline it and see id, kind, layout and note
  - component tree sidebar, zoom, light/dark backdrop
  - Quick Edit: click components or Alt+drag a region, write a change request, copy it for the agent

  python svg_preview.py design/settings.svg              # writes design/_preview.html and opens it
  python svg_preview.py design/*.svg --no-open
  python svg_preview.py design --serve                   # live: http://localhost:8765, auto-reloads
                                                         # whenever an SVG in design/ changes

In sandbox mode (no graphical interface, or SVG_UI_MODE=sandbox) the browser is never opened and
--serve writes the static page instead. The static page is self-contained: no external URLs or
CDN, so it can be published as an artifact as is.

Paths in Quick Edit prompts are relative to the working directory; --absolute-paths writes full
paths instead. With --serve, "送給 Agent" appends the request to design/_feedback.md.
"""
from __future__ import annotations

import argparse
import datetime
import http.server
import json
import os
import re
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _svgcommon import components, detect_mode, load_svg  # noqa: E402

FEEDBACK_FILE = Path("design") / "_feedback.md"
FEEDBACK_MAX_BYTES = 16 * 1024

# references an SVG can make to something outside itself; '#id' and data: URIs stay self-contained
_EXTERNAL = re.compile(r"""(?:href|src)\s*=\s*["']((?![#"']|data:)[^"']+)"""
                       r"""|url\(\s*["']?((?![#"')]|data:)[^"')]+)"""
                       r"""|@import\s+(?:url\()?\s*["']?([^"')\s;]+)""", re.I)

PAGE = r"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SVG Design Review</title>
<style>
:root{--bg:#f3f4f7;--panel:#fff;--text:#1d2230;--muted:#6b7280;--line:#e3e6ec;--hi:#e5484d;--sel:#e0218a;--primary:#1d4ed8;--chip:#eef0f5;--qe-h:0px;--kb:0px;--vvh:100vh}
:root[data-theme=dark]{--bg:#0b0d11;--panel:#151821;--text:#e8eaf0;--muted:#8b93a7;--line:#262b36;--primary:#4f7dff;--chip:#262b36}
*{box-sizing:border-box}body{margin:0;padding-bottom:var(--qe-h);background:var(--bg);color:var(--text);font:14px/1.45 system-ui,"Noto Sans TC",sans-serif}
header{position:sticky;top:0;z-index:5;display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:10px 16px;background:var(--panel);border-bottom:1px solid var(--line)}
header b{font-size:15px}select,button{font:inherit;padding:4px 10px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--text);cursor:pointer}
.live{font-size:12px;color:#16a34a}.wrap{display:flex;gap:16px;padding:16px;align-items:flex-start}
aside{flex:0 0 260px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;position:sticky;top:64px;max-height:calc(100vh - 80px - var(--qe-h));overflow:auto}
aside h3{margin:4px 0 8px;font-size:13px;color:var(--muted)}aside li{list-style:none;padding:2px 6px;border-radius:4px;cursor:default;font-family:ui-monospace,monospace;font-size:12px}
aside li:hover,aside li.on{background:var(--hi);color:#fff}aside li.sel{background:var(--sel);color:#fff}aside ul{margin:0;padding:0}
main{flex:1;min-width:0;display:flex;flex-direction:column;gap:20px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;overflow:auto}
.card h2{margin:0 0 8px;font-size:14px}.card .meta{color:var(--muted);font-size:12px;font-weight:400}
.stage{transform-origin:0 0;user-select:none;-webkit-user-select:none}
#qe{position:fixed;left:16px;right:16px;bottom:calc(16px + env(safe-area-inset-bottom) + var(--kb));z-index:8;display:none;flex-direction:column;max-height:min(45vh,calc(var(--vvh) - 32px));padding:0 13px 10px;background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:12px;box-shadow:0 4px 18px #0003}
#qe.open{display:flex}#qe button:focus-visible,#qe textarea:focus-visible,#qeOpen:focus-visible,aside li:focus-visible{outline:2px solid var(--primary);outline-offset:1px}
#qeHandle{flex:none;align-self:center;width:72px;height:20px;padding:0;border:0;background:none;display:grid;place-items:center}#qeHandle::before{content:"";width:40px;height:4px;border-radius:2px;background:var(--line)}
#qeBody{flex:1;min-height:0;overflow:auto}.qe-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}.qe-head b{font-size:14px}
#qeClose{width:32px;height:24px;padding:0;border:0;background:none;color:var(--muted);font-size:18px;line-height:1}
.qe-grid{display:grid;grid-template-columns:minmax(0,376px) minmax(0,1fr);gap:14px}
#qeChips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:18px}.qe-chip{display:inline-flex;flex:none;align-items:center;gap:4px;height:28px;padding:0 4px 0 12px;border-radius:15px;background:var(--chip);font-size:12px;white-space:nowrap}.qe-chip.c{font-family:ui-monospace,monospace}
.qe-chip button{width:24px;height:24px;padding:0;border:0;border-radius:12px;background:none;color:var(--muted)}
#qeCrumbs{display:flex;flex-wrap:wrap;align-items:center;font:12px ui-monospace,monospace;color:var(--muted)}#qeCrumbs button{padding:2px 1px;border:0;background:none;color:var(--primary);font:inherit}#qeCrumbs button[aria-current]{color:var(--text);font-weight:700}#qeCrumbs i{font-style:normal;padding:0 4px}
#qeText,#qeManual{display:block;width:100%;min-height:100px;padding:10px 12px;resize:vertical;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--text);font:13px/1.45 system-ui,"Noto Sans TC",sans-serif}#qeManual{display:none;margin-top:8px;font-family:ui-monospace,monospace;font-size:12px}#qeManual.on{display:block}
.qe-actions{flex:none;display:flex;align-items:center;gap:8px;margin-top:12px}#qeCount{margin-right:auto;font-size:12px;color:var(--muted)}#qeStatus{font-size:12px;font-weight:600;color:#16a34a}
.qe-actions button{min-height:42px;padding:0 14px;border-radius:8px;background:var(--panel)}.qe-actions button.primary{border-color:var(--primary);background:var(--primary);color:#fff;font-weight:600}
#qe.collapsed #qeBody,#qe.collapsed #qeQueue,#qe.collapsed #qeSend{display:none}#qe.collapsed .qe-actions{margin-top:0}
#tip{position:fixed;pointer-events:none;z-index:9;background:#111;color:#fff;font-size:12px;padding:6px 8px;border-radius:6px;max-width:320px;display:none}
#tip code{color:#ffb4b4}
@media (max-width:800px){.wrap{flex-direction:column}aside{position:static;flex:none;width:100%;max-height:none}main{flex:none;width:100%}}
@media (max-width:719.98px),(max-height:559.98px){.qe-grid{display:block}#qeChips{flex-wrap:nowrap;overflow-x:auto;margin-bottom:8px}.qe-chip{height:30px}#qeCrumbs{margin-bottom:6px}.qe-actions button{flex:1;min-height:44px}#qe.collapsed .qe-actions button{flex:none}}
@media (max-width:719.98px){#qe{padding-bottom:23px}#qe.collapsed{padding-bottom:12px}#qeText{min-height:136px}.qe-actions{position:relative;flex-wrap:wrap;row-gap:12px}#qeCount{flex:0 0 100%;min-height:16px;margin:0}#qeStatus{position:absolute;top:0;right:0}.qe-actions button{flex:1 1 28%;padding:0 6px}#qe.collapsed .qe-actions{flex-wrap:nowrap}#qe.collapsed #qeCount{flex:1}#qe.collapsed .qe-actions button{padding:0 14px}}
</style></head><body>
<header><b>SVG Design Review</b>
<label>狀態 <select id="state"></select></label>
<label>縮放 <select id="zoom"><option>0.5</option><option>0.75</option><option selected>1</option><option>1.5</option><option>2</option></select></label>
<button id="theme">切換背景</button><button id="qeOpen">Quick Edit</button><span id="live" class="live"></span></header>
<div class="wrap"><aside><h3>元件（滑過可定位）</h3><ul id="tree"></ul></aside><main id="main"></main></div>
<div id="tip"></div>
<section id="qe" aria-label="Quick Edit">
<button id="qeHandle" aria-expanded="true" aria-label="收合或展開 Quick Edit 面板"></button>
<div id="qeBody"><div class="qe-head"><b>Quick Edit</b><button id="qeClose" aria-label="關閉 Quick Edit">×</button></div>
<div class="qe-grid"><div><div id="qeChips"></div><nav id="qeCrumbs" aria-label="元件路徑"></nav></div>
<textarea id="qeText" placeholder="描述你想怎麼改" aria-label="修改建議"></textarea></div>
<textarea id="qeManual" readonly aria-label="手動複製的全文"></textarea></div>
<div class="qe-actions"><span id="qeCount"></span><span id="qeStatus" role="status"></span><button id="qeQueue">加入清單</button><button id="qeSend" hidden>送給 Agent</button><button id="qeCopy" class="primary">Copy Prompt</button></div>
</section>
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
  roots.push({sr,file:d.path,d,host,svg:sr.querySelector('svg')});
  d.states.forEach(s=>states.add(s));
  const h=document.createElement('li');h.style.cssText='font-weight:700;font-family:inherit';h.textContent=d.screen;tree.appendChild(h);
  d.comps.forEach(k=>{const li=document.createElement('li');li.textContent=' '.repeat(k.depth*2)+k.id;li.dataset.id=k.id;li.dataset.file=d.path;li.tabIndex=0;tree.appendChild(li);});
});
const sel=document.getElementById('state');[...states].forEach(s=>sel.add(new Option(s,s)));
function applyState(){const s=sel.value;roots.forEach(({sr})=>sr.querySelectorAll('[data-state]').forEach(e=>{
  const show=e.dataset.state===s||(e.dataset.state==='default'&&!e.parentNode.querySelector(':scope>[data-state="'+s+'"]'));
  e.style.display=show?'inline':'none';}));
  /* components without the chosen state keep showing their default layer */}
sel.onchange=()=>{applyState();draw();try{sessionStorage.setItem('st',sel.value)}catch(e){}};
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
tree.addEventListener('mouseover',e=>{const id=e.target.dataset&&e.target.dataset.id;if(!id)return;const r=roots.find(x=>x.file===e.target.dataset.file);const g=r&&r.sr.getElementById(id);mark(g);if(g&&!matchMedia('(max-width:800px)').matches)g.scrollIntoView({block:'nearest',inline:'nearest'});});
/* Quick Edit: selection, region drag, prompt text */
const $=id=>document.getElementById(id),qe=$('qe'),qeText=$('qeText'),qeManual=$('qeManual'),rootEl=document.documentElement;
const MARK='#e0218a',MIN_DRAG=4,EDGE=2,picked=[];let queue=[],dragging=null,skipClick=false,statusTimer=0;
const ids=g=>chain(g).map(n=>n.id);
function isComp(n){return n.tagName==='g'&&n.dataset&&n.dataset.component!==undefined;}
function chain(g){const out=[];for(let n=g;n&&n.tagName!=='svg';n=n.parentNode)if(isComp(n)&&n.id)out.unshift(n);return out;}
function ints(b){return [b.x,b.y,b.width,b.height].map(Math.round);}
function toSvg(r,cx,cy){const b=r.svg.getBoundingClientRect(),v=r.svg.viewBox.baseVal;return [v.x+(cx-b.left)/b.width*v.width,v.y+(cy-b.top)/b.height*v.height];}
function compItem(r,g){const c=chain(g),t=c[c.length-1];return t?{root:r,g:t,id:t.id,kind:t.dataset.component||'',path:ids(t)}:null;}
function itemBox(i){return i.g?ints(i.g.getBBox()):i.bbox;}
function sameItem(a,b){return a.root===b.root&&(a.g?a.g===b.g:String(a.bbox)===String(b.bbox));}
function svgEl(tag,attrs){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);return e;}
function outline(box,dashed){return svgEl('rect',Object.assign({x:box[0]-3,y:box[1]-3,width:box[2]+6,height:box[3]+6,fill:'none',stroke:MARK,'stroke-width':2},dashed?{'stroke-dasharray':'7 4'}:{}));}
function draw(){roots.forEach(r=>{if(!r.svg)return;let o=r.svg.querySelector(':scope>.qe-marks');
    if(!o){o=svgEl('g',{class:'qe-marks','pointer-events':'none'});r.svg.appendChild(o);}o.replaceChildren();
    picked.forEach((i,n)=>{if(i.root!==r)return;const b=itemBox(i),t=svgEl('text',{x:b[0]+8,y:b[1]+1,'font-size':11,'font-weight':700,'text-anchor':'middle',fill:'#fff'});t.textContent=n+1;
      o.append(outline(b,!i.g),svgEl('rect',{x:b[0]-3,y:b[1]-12,width:22,height:18,rx:4,fill:MARK}),t);});});
  document.querySelectorAll('#tree li[data-id]').forEach(li=>li.classList.toggle('sel',picked.some(i=>i.id===li.dataset.id&&i.root.file===li.dataset.file)));}
function panelTop(){return qe.classList.contains('open')?qe.getBoundingClientRect().top:innerHeight;}
function sync(){rootEl.style.setProperty('--qe-h',qe.classList.contains('open')?qe.offsetHeight+32+'px':'0px');}
function itemRect(i){if(i.g)return i.g.getBoundingClientRect();const b=i.root.svg.getBoundingClientRect(),v=i.root.svg.viewBox.baseVal,k=b.width/v.width;
  return {left:b.left+(i.bbox[0]-v.x)*k,top:b.top+(i.bbox[1]-v.y)*k,right:b.left+(i.bbox[0]+i.bbox[2]-v.x)*k,bottom:b.top+(i.bbox[1]+i.bbox[3]-v.y)*k};}
function reveal(i){sync();const card=i.root.host.closest('.card'),c=card.getBoundingClientRect();let r=itemRect(i);
  if(r.right>c.right-12)card.scrollLeft+=Math.min(r.right-c.right+24,r.left-c.left-12);else if(r.left<c.left+12)card.scrollLeft-=c.left+12-r.left;
  r=itemRect(i);const top=document.querySelector('header').getBoundingClientRect().bottom+8,low=panelTop()-8;
  if(r.bottom>low)window.scrollBy(0,Math.min(r.bottom-low,r.top-top));else if(r.top<top)window.scrollBy(0,r.top-top);}
function pick(item,add){if(!item)return;const at=picked.findIndex(i=>sameItem(i,item));
  if(!add)picked.length=0,picked.push(item);else if(at>=0)picked.splice(at,1);else picked.push(item);
  openPanel();render();if(picked.includes(item))reveal(item);}
function regionItem(r,b){let best=null,depth=-1,area=Infinity;r.svg.querySelectorAll('g[data-component][id]').forEach(g=>{const c=g.getBBox(),a=c.width*c.height;
    if(!a||b[0]<c.x||b[1]<c.y||b[0]+b[2]>c.x+c.width||b[1]+b[3]>c.y+c.height)return;const d=chain(g).length;if(d>depth||(d===depth&&a<area))best=g,depth=d,area=a;});
  if(!best)best=r.svg.querySelector('g[data-component][id]');return {root:r,bbox:b,at:best?best.id:'',path:best?ids(best):[]};}
function setStatus(t){$('qeStatus').textContent=t;clearTimeout(statusTimer);if(t)statusTimer=setTimeout(()=>{$('qeStatus').textContent=''},2500);}
function chipLabel(i){const b=i.bbox;return i.g?i.id:`區域 ${b[0]},${b[1]},${b[2]}×${b[3]}`;}
function render(){const chips=$('qeChips'),crumbs=$('qeCrumbs');chips.replaceChildren();crumbs.replaceChildren();
  picked.forEach(i=>{const c=document.createElement('span'),x=document.createElement('button');c.className='qe-chip'+(i.g?' c':'');c.textContent=chipLabel(i);
    x.textContent='×';x.setAttribute('aria-label','移除 '+chipLabel(i));x.onclick=()=>{picked.splice(picked.indexOf(i),1);render();};c.appendChild(x);chips.appendChild(c);});
  const last=picked[picked.length-1];
  if(last){const c=chain(last.g||last.root.svg.querySelector(`g[id="${last.at}"]`));c.forEach((g,n)=>{if(n){const s=document.createElement('i');s.textContent='›';crumbs.appendChild(s);}
    const b=document.createElement('button');b.textContent=g.id;if(g===last.g)b.setAttribute('aria-current','true');b.onclick=()=>{const it=compItem(last.root,g);picked.splice(picked.indexOf(last),1,it);render();reveal(it);};crumbs.appendChild(b);});}
  $('qeCount').textContent=qe.classList.contains('collapsed')?`已選 ${picked.length} 項`:queue.length?`清單 ${queue.length} 筆`:'';draw();save();}
function openPanel(){qe.classList.add('open');sync();}
function closePanel(){qe.classList.remove('open');picked.length=0;render();sync();$('qeOpen').focus();}
function serial(i){const b=itemBox(i);return i.g?{file:i.root.file,ref:i.id,kind:i.kind,path:i.path.join('>'),bbox:b}
  :{file:i.root.file,region:true,ref:`region(${b.join(',')})${i.at?'@'+i.at:''}`,kind:'region',path:i.path.join('>'),bbox:b};}
function current(){const text=qeText.value;return text||picked.length?{text,state:sel.value,items:picked.map(serial)}:null;}
function refLines(e){const st=e.state==='default'?'':'?state='+e.state,out=[];
  [...new Set(e.items.map(i=>i.file))].forEach(f=>{const it=e.items.filter(i=>i.file===f),c=it.filter(i=>!i.region);if(c.length)out.push(f+'#'+c.map(i=>i.ref).join(',')+st);
    it.filter(i=>i.region).forEach(i=>out.push(f+'#'+i.ref+st));});return out;}
function visible(r){const b=r.svg.getBoundingClientRect(),card=r.host.closest('.card'),c=card.getBoundingClientRect(),v=r.svg.viewBox.baseVal;
  const cl=c.left+card.clientLeft,ct=c.top+card.clientTop;
  const l=Math.max(b.left,cl,0),t=Math.max(b.top,ct,document.querySelector('header').getBoundingClientRect().bottom),rt=Math.min(b.right,cl+card.clientWidth,innerWidth),bt=Math.min(b.bottom,ct+card.clientHeight,panelTop());
  if(rt<=l||bt<=t)return [v.x,v.y,v.width,v.height].map(Math.round);
  /* a sliver of EDGE px or less at the canvas edge counts as visible */
  const p=toSvg(r,l,t),q=toSvg(r,rt,bt),x2=v.x+v.width,y2=v.y+v.height,x=p[0]-v.x<=EDGE?v.x:Math.floor(p[0]),y=p[1]-v.y<=EDGE?v.y:Math.floor(p[1]);
  return [x,y,(x2-q[0]<=EDGE?x2:Math.ceil(q[0]))-x,(y2-q[1]<=EDGE?y2:Math.ceil(q[1]))-y];}
function snapshot(entries,files){const all=entries.flatMap(e=>e.items),state=entries[entries.length-1].state,zoom=+$('zoom').value;
  const jobs=files.map((f,n)=>{const r=roots.find(x=>x.file===f);return {input:f,screen:r.d.screen,target:r.d.target,state,view:{zoom,visible:visible(r)},
    selection:all.filter(i=>i.file===f).map(({ref,kind,path,bbox})=>({ref,kind,path,bbox})),
    outputs:[{path:`<tmp>/svgui-quickedit-current-view${n?'-'+(n+1):''}.png`,label:'current view',scale:1,highlight:true}]};});
  return JSON.stringify(jobs.length===1?jobs[0]:jobs);}
function buildPrompt(){const entries=queue.concat(current()||[]);if(!entries.length)return '';
  let files=[...new Set(entries.flatMap(e=>e.items.map(i=>i.file)))];if(!files.length)files=[roots[0].file];
  const fence='`'.repeat(3),tail=files.map(f=>'File: '+f).join('\n'),snap='Snapshot JSON (svg_render.py --job):\n'+fence+'json\n'+snapshot(entries,files)+'\n'+fence;
  if(entries.length===1){const e=entries[0],r=refLines(e);return (e.text?e.text+'\n\n':'')+tail+'\n'+(r.length?'References:\n'+r.join('\n')+'\n':'')+snap;}
  return entries.map((e,n)=>{const r=refLines(e);return `${n+1}. ${e.text}`+(r.length?'\n   References:\n'+r.map(x=>'   '+x).join('\n'):'');}).join('\n')+'\n\n'+tail+'\n'+snap;}
async function writeClipboard(text){try{if(navigator.clipboard&&navigator.clipboard.writeText){await navigator.clipboard.writeText(text);return true;}}catch(e){}
  try{const a=document.createElement('textarea');a.value=text;a.readOnly=true;a.style.cssText='position:fixed;top:0;left:0;opacity:0';document.body.appendChild(a);a.select();const ok=document.execCommand('copy');a.remove();if(ok)return true;}catch(e){}
  return false;}
function finished(msg){qeManual.classList.remove('on');qeManual.value='';qeText.value='';queue=[];setStatus(msg);render();sync();}
async function copyAll(){const text=buildPrompt();if(!text)return;if(await writeClipboard(text)){finished('已複製');return;}
  qe.classList.remove('collapsed');qeManual.value=text;qeManual.classList.add('on');setStatus('請手動複製');sync();qeManual.focus();qeManual.select();}
async function sendAll(){const text=buildPrompt();if(!text)return;try{const r=await fetch('/__feedback',{method:'POST',body:text});if(r.ok){finished('已送出');return;}setStatus('送出失敗：'+r.status);}catch(e){setStatus('送出失敗');}}
function save(){try{sessionStorage.setItem('qe',JSON.stringify({text:qeText.value,queue}));}catch(e){}}
main.addEventListener('click',e=>{if(skipClick){skipClick=false;return;}const g=compAt(e);if(!g)return;const n=e.composedPath().find(x=>x.tagName==='svg'),r=roots.find(x=>x.svg===n);if(r)pick(compItem(r,g),e.shiftKey||e.ctrlKey||e.metaKey);});
tree.addEventListener('click',e=>{const d=e.target.dataset;if(!d||!d.id)return;const r=roots.find(x=>x.file===d.file);if(r)pick(compItem(r,r.sr.getElementById(d.id)),e.shiftKey||e.ctrlKey||e.metaKey);});
tree.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.dataset.id){e.preventDefault();e.target.click();}});
main.addEventListener('mousedown',e=>{if(!e.altKey||e.button)return;const n=e.composedPath().find(x=>x.tagName==='svg'),r=roots.find(x=>x.svg===n);if(!r)return;e.preventDefault();
  const start=toSvg(r,e.clientX,e.clientY),box=svgEl('rect',{fill:'none',stroke:MARK,'stroke-width':2,'stroke-dasharray':'7 4','pointer-events':'none'});r.svg.appendChild(box);dragging={r,start,box,add:e.shiftKey||e.ctrlKey||e.metaKey,b:null};});
addEventListener('mousemove',e=>{if(!dragging)return;const{r,start,box}=dragging,p=toSvg(r,e.clientX,e.clientY),v=r.svg.viewBox.baseVal;
  const x=Math.max(v.x,Math.min(start[0],p[0])),y=Math.max(v.y,Math.min(start[1],p[1])),w=Math.min(v.x+v.width,Math.max(start[0],p[0]))-x,h=Math.min(v.y+v.height,Math.max(start[1],p[1]))-y;
  dragging.b=[x,y,w,h].map(Math.round);for(const[k,val]of Object.entries({x,y,width:w,height:h}))box.setAttribute(k,val);});
addEventListener('mouseup',()=>{if(!dragging)return;const{r,box,add,b}=dragging;dragging=null;box.remove();skipClick=true;setTimeout(()=>{skipClick=false},0);if(b&&b[2]>=MIN_DRAG&&b[3]>=MIN_DRAG)pick(regionItem(r,b),add);});
$('qeOpen').onclick=()=>{openPanel();render();qeText.focus();};$('qeClose').onclick=closePanel;$('qeCopy').onclick=copyAll;$('qeSend').onclick=sendAll;$('qeSend').hidden=!LIVE;
$('qeQueue').onclick=()=>{const e=current();if(!e)return;queue.push(e);qeText.value='';picked.length=0;render();sync();qeText.focus();};
$('qeHandle').onclick=()=>{const c=qe.classList.toggle('collapsed');$('qeHandle').setAttribute('aria-expanded',String(!c));render();sync();};
qeText.addEventListener('input',save);
addEventListener('keydown',e=>{if(!qe.classList.contains('open'))return;if(e.key==='Escape')closePanel();else if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();copyAll();}});
new ResizeObserver(sync).observe(qe);addEventListener('resize',sync);
if(window.visualViewport){const vv=visualViewport,fit=()=>{rootEl.style.setProperty('--kb',Math.max(0,innerHeight-vv.height-vv.offsetTop)+'px');rootEl.style.setProperty('--vvh',vv.height+'px');};vv.addEventListener('resize',fit);vv.addEventListener('scroll',fit);}
try{const s=sessionStorage.getItem('st');if(s&&[...sel.options].some(o=>o.value===s))sel.value=s;const z=sessionStorage.getItem('zm');if(z){document.getElementById('zoom').value=z;document.getElementById('zoom').onchange({target:{value:z}})}
  const q=JSON.parse(sessionStorage.getItem('qe')||'null');if(q){qeText.value=q.text||'';queue=q.queue||[];if(qeText.value||queue.length)openPanel();}}catch(e){}
applyState();render();
if(LIVE){const l=document.getElementById('live');let v=null;l.textContent='● 即時預覽中';
  setInterval(()=>fetch('/__version').then(r=>r.text()).then(t=>{if(v&&t!==v)location.reload();v=t}).catch(()=>{l.textContent='○ 預覽伺服器已停止'}),1000);}
</script></body></html>"""


def prompt_path(p: Path, absolute: bool) -> str:
    """The path written into Quick Edit prompts, always with forward slashes."""
    if absolute:
        return p.resolve().as_posix()
    try:
        return Path(os.path.relpath(p.resolve(), Path.cwd().resolve())).as_posix()
    except ValueError:  # another drive on Windows
        return p.name


def collect(paths: list[Path], absolute: bool = False) -> list[dict]:
    out = []
    for p in paths:
        path = prompt_path(p, absolute)
        try:
            tree = load_svg(p)
        except Exception as e:  # half-written file while the agent is editing
            out.append({"file": p.name, "path": path, "screen": p.stem + " (parse error)", "target": str(e),
                        "svg": "", "comps": [], "states": []})
            continue
        root = tree.getroot()
        comps = [{"id": g.get("id"), "depth": d} for g, d, _ in components(root) if g.get("id")]
        states = sorted({e.get("data-state") for e in root.iter() if e.get("data-state")} - {"default"})
        out.append({"file": p.name, "path": path, "screen": root.get("data-screen") or p.stem,
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


def build(targets: list[str], live: bool, absolute: bool = False) -> str:
    data = json.dumps(collect(svg_files(targets), absolute), ensure_ascii=False).replace("</", "<\\/")
    return PAGE.replace("__DATA__", data).replace("__LIVE__", "true" if live else "false")


def version(targets: list[str]) -> str:
    return ",".join(f"{p.name}:{p.stat().st_mtime_ns}" for p in svg_files(targets))


def external_refs(paths: list[Path]) -> list[str]:
    """Warnings for resources a static page or artifact could not load."""
    out = []
    for p in paths:
        for groups in _EXTERNAL.findall(p.read_text(encoding="utf-8", errors="replace")):
            ref = next(g for g in groups if g)
            out.append(f"warn: {p.name} references '{ref}', which a static page cannot load")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="+", help="SVG files and/or folders")
    ap.add_argument("-o", "--out", help="output HTML (default: <first folder>/_preview.html)")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--serve", action="store_true", help="live preview server with auto-reload")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--absolute-paths", action="store_true",
                    help="write absolute paths into Quick Edit prompts (default: relative to the working directory)")
    a = ap.parse_args()

    if not svg_files(a.targets):
        print("no .svg files found", file=sys.stderr)
        return 1

    mode = detect_mode()
    open_browser = mode == "local" and not a.no_open
    if a.serve and mode == "sandbox":
        print("此環境我看不到預覽，改用靜態頁")
        a.serve = False

    if a.serve:
        targets = a.targets
        own_origins = {f"http://127.0.0.1:{a.port}", f"http://localhost:{a.port}"}
        write_lock = threading.Lock()

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = (version(targets) if self.path == "/__version"
                        else build(targets, True, a.absolute_paths)).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8" if self.path == "/__version"
                                 else "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def reply(self, status: int) -> None:
                self.send_response(status)
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()

            def do_POST(self):
                # the fixed origin list, not the Host header, is what stops a rebinding page
                if (self.path != "/__feedback" or self.client_address[0] != "127.0.0.1"
                        or self.headers.get("Origin") not in own_origins):
                    return self.reply(403)
                try:
                    length = int(self.headers.get("Content-Length", ""))
                except ValueError:
                    return self.reply(411)
                if length < 0 or length > FEEDBACK_MAX_BYTES:
                    return self.reply(413)
                text = self.rfile.read(length).decode("utf-8", errors="replace")
                stamp = datetime.datetime.now().isoformat(timespec="seconds")
                with write_lock:
                    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
                    with FEEDBACK_FILE.open("a", encoding="utf-8", newline="\n") as f:
                        f.write(f"## {stamp}\n\n{text}\n\n")
                return self.reply(204)

            def log_message(self, *args):
                pass

        url = f"http://localhost:{a.port}/"
        with socketserver.ThreadingTCPServer(("127.0.0.1", a.port), H) as srv:
            print(f"live preview at {url}  (Ctrl+C to stop; page reloads when an SVG changes)")
            if open_browser:
                threading.Timer(0.5, lambda: webbrowser.open(url)).start()
            try:
                srv.serve_forever()
            except KeyboardInterrupt:
                pass
        return 0

    first = svg_files(a.targets)[0]
    out = Path(a.out) if a.out else first.parent / "_preview.html"
    out.write_text(build(a.targets, False, a.absolute_paths), encoding="utf-8")
    print(f"wrote {out}")
    for w in external_refs(svg_files(a.targets)):
        print(w)
    if open_browser:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
