#!/usr/bin/env python3
"""Browser tests for the Quick Edit panel in the preview page. Needs Playwright and a browser.

  python tests/test_quick_edit.py

Runs on a temporary copy of the bundled example. Screenshots go to tests/_out/.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "svg-ui-bridge" / "scripts"
EXAMPLE = ROOT / "skills" / "svg-ui-bridge" / "templates" / "example-screen.svg"
OUT = ROOT / "tests" / "_out"
FILE = "design/example-screen.svg"
BOX = {"SearchButton": [1120, 80, 136, 44], "SearchInput": [24, 80, 1084, 44]}

sys.path.insert(0, str(SCRIPTS))
from _svgcommon import _launch_browser  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: object = "") -> None:
    results.append((name, bool(ok), "" if ok else str(detail)[:400]))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def snapshot(prompt: str) -> dict:
    return json.loads(re.search(r"```json\n(.*)\n```", prompt).group(1))


def box_of(page, cid: str):
    return page.evaluate("""id => { const n = document.querySelector('.stage').shadowRoot.getElementById(id);
      const b = n.getBoundingClientRect(); return {top: b.top, bottom: b.bottom, left: b.left, right: b.right}; }""", cid)


def select(page, cid: str, shift: bool = False) -> None:
    """Pick through the component tree, which works at any window size."""
    page.locator(f'#tree li[data-id="{cid}"]').click(modifiers=["Shift"] if shift else [])


def click_comp(page, cid: str, shift: bool = False) -> None:
    page.evaluate("id => document.querySelector('.stage').shadowRoot.getElementById(id)"
                  ".scrollIntoView({block: 'center', inline: 'center'})", cid)
    b = box_of(page, cid)
    page.mouse.move((b["left"] + b["right"]) / 2, (b["top"] + b["bottom"]) / 2)
    if shift:
        page.keyboard.down("Shift")
    page.mouse.down()
    page.mouse.up()
    if shift:
        page.keyboard.up("Shift")


def to_origin(page) -> None:
    """Scroll the design pane and its cards back to the top-left corner."""
    page.evaluate("document.getElementById('main').scrollTo(0, 0); document.querySelectorAll('.card').forEach(c => c.scrollLeft = 0)")


def alt_drag(page, svg_box: list[int]) -> None:
    """Alt+drag over an SVG-coordinate box, whatever the zoom."""
    to_origin(page)
    r = page.evaluate("""() => { const s = document.querySelector('.stage').shadowRoot.querySelector('svg');
      const b = s.getBoundingClientRect(); return {left: b.left, top: b.top, k: b.width / s.viewBox.baseVal.width}; }""")
    x, y, w, h = svg_box
    page.keyboard.down("Alt")
    page.mouse.move(r["left"] + x * r["k"], r["top"] + y * r["k"])
    page.mouse.down()
    page.mouse.move(r["left"] + (x + w) * r["k"], r["top"] + (y + h) * r["k"], steps=4)
    page.mouse.up()
    page.keyboard.up("Alt")


def write_text(page) -> str:
    raw = page.evaluate("navigator.clipboard.readText()")
    return raw.replace("\r\n", "\n")  # the Windows clipboard stores CRLF


def test_selection(page) -> None:
    click_comp(page, "SearchButton")
    check("chip for clicked component", page.locator("#qeChips .qe-chip").count() == 1
          and "SearchButton" in page.locator("#qeChips").inner_text())
    check("breadcrumb path", page.locator("#qeCrumbs").inner_text().replace("\n", "") == "App›SearchBar›SearchButton",
          page.locator("#qeCrumbs").inner_text())
    page.locator("#qeCrumbs button", has_text="SearchBar").click()
    check("breadcrumb replaces selection", "SearchBar" in page.locator("#qeChips").inner_text()
          and "SearchButton" not in page.locator("#qeChips").inner_text())


def test_prompt(page) -> str:
    page.locator("#zoom").select_option("1")
    select(page, "SearchButton")
    page.locator("#qeText").fill('圓角改大一點\n文字改成「登入"帳號"」')
    page.locator("#qeCopy").click()
    page.wait_for_function("document.getElementById('qeStatus').textContent === '已複製'")
    text = write_text(page)
    check("first lines keep the original text", text.startswith('圓角改大一點\n文字改成「登入"帳號"」\n\nFile: ' + FILE), text[:120])
    check("reference line", f"References:\n{FILE}#SearchButton\n" in text, text)
    job = snapshot(text)
    check("snapshot bbox", job["selection"][0]["bbox"] == BOX["SearchButton"], job["selection"])
    check("snapshot path", job["selection"][0]["path"] == "App>SearchBar>SearchButton", job["selection"])
    check("snapshot keeps locating fields only", set(job["selection"][0]) == {"ref", "kind", "path", "bbox"})
    check("snapshot is one line", "\n" not in re.search(r"```json\n(.*)\n```", text).group(1))
    visible = job["view"]["visible"]
    pane = page.evaluate("document.querySelector('.card').clientWidth")
    check("visible range is what the design pane shows", visible[0] + visible[2] == 1280 and pane - 30 <= visible[2] <= pane + 2,
          (visible, pane))
    check("input and text cleared after copy", page.locator("#qeText").input_value() == "")

    page.locator("#state").select_option("hover")
    check("selection survives a state change", "SearchButton" in page.locator("#qeChips").inner_text())
    page.locator("#qeText").fill("hover 顏色再亮一點")
    page.keyboard.press("Control+Enter")
    page.wait_for_function("document.getElementById('qeStatus').textContent === '已複製'")
    hover = write_text(page)
    check("state in reference", f"{FILE}#SearchButton?state=hover" in hover, hover)
    check("state in snapshot", snapshot(hover)["state"] == "hover")
    page.locator("#state").select_option("default")
    return text


def test_render_job(prompt: str, work: Path) -> None:
    job = snapshot(prompt)
    out = work / "job.png"
    job["outputs"][0]["path"] = str(out)
    r = subprocess.run([sys.executable, str(SCRIPTS / "svg_render.py"), "--job", json.dumps(job, ensure_ascii=False)],
                       cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "SVG_UI_RENDERER": "playwright"})
    check("--job runs", r.returncode == 0 and str(out) in r.stdout, r.stdout + r.stderr)
    from PIL import Image
    im = Image.open(out).convert("RGB")
    x, y, w, h = job["view"]["visible"]
    check("--job size is visible × scale", im.size == (w, h), (im.size, job["view"]))
    bx, by, bw, bh = BOX["SearchButton"]
    edge = im.getpixel((bx - x + bw // 2, by - y))
    check("--job outlines the selection", edge == (255, 0, 170), edge)
    check("selection inside visible range", x <= bx and bx + bw <= x + w, job["view"])

    tmp_job = dict(job, outputs=[{"path": "<tmp>/svgui-test.png", "scale": 2, "highlight": False}])
    r = subprocess.run([sys.executable, str(SCRIPTS / "svg_render.py"), "--job", json.dumps(tmp_job)],
                       cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "SVG_UI_RENDERER": "playwright"})
    written = Path(tempfile.gettempdir()) / "svgui-test.png"
    check("<tmp> becomes the temp folder", written.exists() and Image.open(written).size == (w * 2, h * 2), r.stdout + r.stderr)
    written.unlink(missing_ok=True)


def test_multi(page) -> None:
    select(page, "SearchButton")
    click_comp(page, "SearchInput", shift=True)
    page.locator("#qeCopy").click()
    page.wait_for_function("document.getElementById('qeStatus').textContent === '已複製'")
    text = write_text(page)
    refs = [line for line in text.splitlines() if "#" in line and not line.startswith("```")]
    check("multi-select is one reference line", refs == [f"{FILE}#SearchButton,SearchInput"], refs)
    check("multi-select snapshot has two items", len(snapshot(text)["selection"]) == 2)

    select(page, "SearchButton")
    page.evaluate("window.scrollTo(0, 0)")
    alt_drag(page, [40, 300, 200, 100])
    select(page, "SearchInput", shift=True)
    page.locator("#qeCopy").click()
    page.wait_for_function("document.getElementById('qeStatus').textContent === '已複製'")
    text = write_text(page)
    check("region stays on its own line", re.search(rf"^{FILE}#SearchInput$", text, re.M)
          and re.search(rf"^{FILE}#region\(\d+,\d+,\d+,\d+\)@\S+$", text, re.M), text)

    select(page, "SearchButton")
    page.locator("#qeText").fill("圓角改大一點")
    page.locator("#qeQueue").click()
    check("queue count shown", "清單 1 筆" in page.locator("#qeCount").inner_text())
    alt_drag(page, [40, 300, 200, 100])
    page.locator("#qeText").fill("這裡加一個按鈕")
    page.locator("#qeCopy").click()
    page.wait_for_function("document.getElementById('qeStatus').textContent === '已複製'")
    text = write_text(page)
    check("numbered entries", text.startswith(f"1. 圓角改大一點\n   References:\n   {FILE}#SearchButton\n2. 這裡加一個按鈕\n   References:\n   {FILE}#region("), text[:160])
    check("File and snapshot appear once", text.count("File: ") == 1 and text.count("Snapshot JSON") == 1)
    check("selection keeps every item in order", [i["kind"] for i in snapshot(text)["selection"]] == ["Button", "region"],
          snapshot(text)["selection"])
    check("queue cleared after copy", page.locator("#qeCount").inner_text() == "")


def test_region_zoom(page) -> None:
    page.evaluate("window.scrollTo(0, 0)")
    page.locator("#zoom").select_option("0.5")
    alt_drag(page, [600, 300, 200, 100])
    page.locator("#qeCopy").click()
    page.wait_for_function("document.getElementById('qeStatus').textContent === '已複製'")
    text = write_text(page)
    m = re.search(rf"{FILE}#region\((\d+),(\d+),(\d+),(\d+)\)@(\S+)", text)
    near = m and all(abs(int(g) - v) <= 2 for g, v in zip(m.groups()[:4], (600, 300, 200, 100)))
    check("region coordinates at zoom 0.5", near, text[:200])
    check("region owner is the deepest component", m and m.group(5) == "ArticlePreview", text[:200])
    page.locator("#zoom").select_option("1")


def test_denied(browser, url: str) -> None:
    ctx = browser.new_context(viewport={"width": 1600, "height": 900})
    page = ctx.new_page()
    page.add_init_script("""navigator.clipboard.writeText = () => Promise.reject(new Error('denied'));
      document.execCommand = () => false;""")
    page.goto(url)
    select(page, "SearchButton")
    page.locator("#qeText").fill("改色")
    page.locator("#qeCopy").click()
    page.wait_for_selector("#qeManual.on")
    text = page.locator("#qeManual").input_value()
    check("manual fallback shows the full prompt", text.startswith("改色\n\nFile: ") and "Snapshot JSON" in text, text[:100])
    check("manual fallback keeps the input", page.locator("#qeText").input_value() == "改色")
    ctx.close()


def rect(page, selector: str) -> dict:
    return page.evaluate(f"""() => {{ const e = document.querySelector({selector!r}), b = e.getBoundingClientRect();
      return {{x: b.x, y: b.y, w: b.width, h: b.height, right: b.right, bottom: b.bottom,
               shown: getComputedStyle(e).display !== 'none', position: getComputedStyle(e).position}}; }}""")


def drag(page, selector: str, dx: float, dy: float) -> None:
    b = page.locator(selector).bounding_box()
    x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx, y + dy, steps=6)
    page.mouse.up()


def test_responsive(browser, url: str, port: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    page.goto(url)
    check("side column on the right by default", rect(page, "#side")["x"] > rect(page, "main")["right"] and
          page.locator("#sidePos").input_value() == "right")
    select(page, "SearchButton")
    m, s, a, q = rect(page, "main"), rect(page, "#side"), rect(page, "aside"), rect(page, "#qe")
    check("Quick Edit sits below the tree in the column", q["shown"] and a["bottom"] <= q["y"] and abs(q["x"] - s["x"]) < 1, (a, q))
    check("nothing floats over the design", q["position"] == "static" and s["x"] >= m["right"], (q, m, s))
    check("Copy Prompt is 40px tall and inside the window", page.locator("#qeCopy").bounding_box()["height"] >= 40 and
          rect(page, "#qeCopy")["bottom"] <= 800)

    select(page, "ArticlePreview")
    b, m = box_of(page, "ArticlePreview"), rect(page, "main")
    check("selecting scrolls the design pane to the component", b["top"] >= m["y"] - 1 and b["top"] < m["bottom"], (b, m))
    page.locator('#tree li[data-id="NavBar-Title"]').hover()
    page.wait_for_timeout(100)
    b = box_of(page, "NavBar-Title")
    check("hovering the tree still scrolls to the component", b["top"] >= m["y"] - 1 and b["bottom"] <= m["bottom"] + 1, b)

    for cid in ("SearchInput", "NavBar", "NavBar-Title", "NavBar-Status", "ResultList", "ResultCard", "DetailPanel"):
        select(page, cid, shift=True)
    chips = page.locator("#qeChips")
    grows = page.evaluate("(() => { const c = document.getElementById('qeChips'); return c.scrollHeight > c.clientHeight; })()")
    chips.hover()
    page.mouse.wheel(0, 200)
    page.wait_for_timeout(150)
    check("selected items scroll with the mouse wheel", grows and page.evaluate("document.getElementById('qeChips').scrollTop") > 0)

    m, sv, sd, a, sh, q = (rect(page, k) for k in ("main", "#splitV", "#side", "aside", "#splitH", "#qe"))
    gaps = [m["x"], sd["x"] - m["right"], 1280 - sd["right"], m["y"] - rect(page, "header")["bottom"], q["y"] - a["bottom"],
            800 - q["bottom"], sv["w"], sh["h"]]
    check("page margin, dividers and gaps are all 6px", all(abs(g - 6) <= 0.5 for g in gaps), gaps)
    hit = page.evaluate(f"document.elementFromPoint({sd['x'] + 2}, {sv['y'] + sv['h'] / 2}).id")
    check("the divider can be grabbed 2px inside the side column", hit == "splitV", hit)
    hit = page.evaluate(f"document.elementFromPoint({m['right'] - 2}, {sv['y'] + sv['h'] / 2}).id")
    check("the grab area stays off the design pane", hit != "splitV", hit)
    check("marks use the page tokens", page.evaluate("MARK === getComputedStyle(document.documentElement).getPropertyValue('--sel').trim()"))

    w0, h0 = rect(page, "#side")["w"], rect(page, "aside")["h"]
    drag(page, "#splitV", -120, 0)
    drag(page, "#splitH", 0, 60)
    w1, h1 = rect(page, "#side")["w"], rect(page, "aside")["h"]
    check("dragging the vertical splitter widens the column", abs((w1 - w0) - 120) <= 3, (w0, w1))
    check("dragging the horizontal splitter grows the tree", abs((h1 - h0) - 60) <= 3, (h0, h1))
    page.screenshot(path=str(OUT / "layout-1280x800-right.png"))

    page.locator("#sidePos").select_option("left")
    page.reload()
    check("position, width and tree height survive a reload", page.locator("#sidePos").input_value() == "left" and
          rect(page, "#side")["right"] <= rect(page, "main")["x"] + 1 and abs(rect(page, "#side")["w"] - w1) <= 1,
          (rect(page, "#side"), w1))
    select(page, "SearchButton")
    check("tree height survives a reload", abs(rect(page, "aside")["h"] - h1) <= 1, (rect(page, "aside")["h"], h1))
    page.screenshot(path=str(OUT / "layout-1280x800-left.png"))

    page.locator("#sidePos").select_option("none")
    check("hidden tree leaves only Quick Edit in the column", not rect(page, "aside")["shown"] and rect(page, "#qe")["shown"])
    page.locator("#qeText").fill("還沒送出的文字")
    page.keyboard.press("Escape")
    check("Esc closes Quick Edit", not rect(page, "#qe")["shown"])
    check("with no tree and no Quick Edit the design takes the full width",
          not rect(page, "#side")["shown"] and rect(page, "main")["w"] > 1200, rect(page, "main"))
    page.reload()
    check("hidden choice survives a reload", page.locator("#sidePos").input_value() == "none")
    page.locator("#sidePos").select_option("right")
    ctx.close()

    for w, h in ((600, 800), (390, 844)):
        ctx = browser.new_context(viewport={"width": w, "height": h})
        page = ctx.new_page()
        page.goto(url)
        check(f"{w}x{h} hides the tree and its position menu",
              not rect(page, "aside")["shown"] and not rect(page, "#sidePosLabel")["shown"])
        check(f"{w}x{h} design pane fills the window while Quick Edit is closed",
              not rect(page, "#side")["shown"] and abs(rect(page, "main")["bottom"] - (h - 6)) <= 2, rect(page, "main"))
        stage, card = rect(page, ".stage"), rect(page, ".card")
        check(f"{w}x{h} fit scales the design down to the card instead of reflowing it",
              stage["right"] <= card["right"] and page.evaluate("getComputedStyle(document.querySelector('.stage')).transform") != "none",
              (stage, card))
        click_comp(page, "NavBar-Title")
        m, sp, q = rect(page, "main"), rect(page, "#splitH"), rect(page, "#qe")
        check(f"{w}x{h} design on top and Quick Edit below, both on screen",
              m["bottom"] <= sp["y"] and sp["bottom"] <= q["y"] and q["bottom"] <= h and m["h"] >= 200 and q["position"] == "static",
              (m, sp, q))
        b = box_of(page, "NavBar-Title")
        check(f"{w}x{h} selection stays visible in the design pane", b["top"] >= m["y"] and b["bottom"] <= m["bottom"], (b, m))
        check(f"{w}x{h} buttons are 40px tall", page.locator("#qeCopy").bounding_box()["height"] >= 40)
        page.screenshot(path=str(OUT / f"layout-{w}x{h}.png"))
        q0 = rect(page, "#side")["h"]
        drag(page, "#splitH", 0, -60)
        check(f"{w}x{h} dragging the splitter up grows Quick Edit by the same amount",
              abs(rect(page, "#side")["h"] - (q0 + 60)) <= 1, (q0, rect(page, "#side")))
        page.reload()
        page.locator("#qeOpen").click()
        check(f"{w}x{h} Quick Edit height survives a reload", abs(rect(page, "#side")["h"] - (q0 + 60)) <= 1, rect(page, "#side"))
        page.keyboard.press("Escape")
        check(f"{w}x{h} Esc gives the design the full height back",
              not rect(page, "#side")["shown"] and abs(rect(page, "main")["bottom"] - (h - 6)) <= 2)
        ctx.close()

    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    page.goto(url)
    select(page, "SearchButton")
    page.locator("#qeText").fill("第一筆")
    page.locator("#qeQueue").click()
    select(page, "SearchInput")
    page.locator("#qeText").fill("還沒送出的文字")
    page.set_viewport_size({"width": 600, "height": 800})
    page.wait_for_timeout(100)
    check("resize keeps selection", "SearchInput" in page.locator("#qeChips").inner_text())
    check("resize keeps text", page.locator("#qeText").input_value() == "還沒送出的文字")
    check("resize keeps queue", "清單 1 筆" in page.locator("#qeCount").inner_text())
    ctx.close()


def post(port: int, data: bytes, origin: str | None) -> int:
    req = urllib.request.Request(f"http://127.0.0.1:{port}/__feedback", data=data, method="POST")
    if origin:
        req.add_header("Origin", origin)
    try:
        return urllib.request.urlopen(req).status
    except urllib.error.HTTPError as e:
        return e.code
    except OSError:
        return 0  # the server may close before reading an oversized body


def test_inbox(page, port: int, work: Path) -> None:
    feedback = work / "design" / "_feedback.md"
    origin = f"http://127.0.0.1:{port}"
    select(page, "SearchButton")
    page.locator("#qeText").fill("送給 agent 的建議")
    page.locator("#qeSend").click()
    page.wait_for_function("document.getElementById('qeStatus').textContent === '已送出'")
    text = feedback.read_text(encoding="utf-8")
    check("inbox writes the request", "送給 agent 的建議" in text and "Snapshot JSON" in text, text)
    check("inbox stamps each entry", re.match(r"## \d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\n", text), text[:40])
    size = feedback.stat().st_size
    check("wrong Origin gets 403", post(port, b"x", "http://evil.example") == 403)
    check("missing Origin gets 403", post(port, b"x", None) == 403)
    check("rebinding Host trick gets 403", post(port, b"x", f"http://evil.example:{port}") == 403)
    check("over 16 KB is refused", post(port, b"x" * (16 * 1024 + 1), origin) in (413, 0))
    check("refused requests write nothing", feedback.stat().st_size == size)
    check("16 KB exactly is accepted", post(port, b"y" * (16 * 1024), origin) == 204)


def test_paths(browser, work: Path) -> None:
    run = lambda *args: subprocess.run([sys.executable, str(SCRIPTS / "svg_preview.py"), "design", "--no-open", *args],
                                       cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace")
    run()
    html = (work / "design" / "_preview.html").read_text(encoding="utf-8")
    check("static page uses relative paths", f'"path": "{FILE}"' in html and str(work.as_posix()) not in html
          and os.path.expanduser("~").replace("\\", "/") not in html)
    run("--absolute-paths")
    html = (work / "design" / "_preview.html").read_text(encoding="utf-8")
    absolute = (work / FILE).resolve().as_posix()
    check("--absolute-paths writes full paths", f'"path": "{absolute}"' in html)
    job = {"input": absolute, "state": "default", "selection": [],
           "outputs": [{"path": str(work / "abs.png"), "scale": 1, "highlight": True}]}
    r = subprocess.run([sys.executable, str(SCRIPTS / "svg_render.py"), "--job", json.dumps(job)], cwd=work,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "SVG_UI_RENDERER": "playwright"})
    check("--job finds an absolute path", r.returncode == 0 and (work / "abs.png").exists(), r.stdout + r.stderr)
    run()

    page = browser.new_page(viewport={"width": 1600, "height": 900})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto((work / "design" / "_preview.html").resolve().as_uri())
    select(page, "SearchButton")
    check("static page has no inbox button", not page.locator("#qeSend").is_visible())
    check("static page has no script errors", not errors, errors)
    page.close()


HTML_FILE = "design/html/review.html"
INJECTED = ("<img id='Probe' src='missing.png' style='display:none' onerror='parent.__pwned=1'>"
            "<script>parent.__pwned=2</script>")


def html_refs(page) -> list[str]:
    return [l for l in page.evaluate("buildPrompt()").splitlines() if "#" in l and not l.startswith("```")]


def test_html(browser, work: Path) -> None:
    template = ROOT / "skills" / "svg-ui-bridge" / "templates" / "html-design"
    baseline = {}
    for w in (1280, 390):  # html_review.py on the clean template, in its own process
        out = work / f"base-{w}"
        subprocess.run([sys.executable, str(SCRIPTS / "html_review.py"), str(template / "review.html"), "--size",
                        f"{w}x800", "--out", str(out), "--standalone"], capture_output=True)
        baseline[w] = json.loads((out / "report.json").read_text(encoding="utf-8"))
    html_dir = work / "design" / "html"
    shutil.copytree(template, html_dir)
    source = html_dir / "review.html"
    source.write_text(source.read_text(encoding="utf-8").replace(
        '<p class="description" id="DefaultDescription"', INJECTED + '<p class="description" id="DefaultDescription"'),
        encoding="utf-8")
    subprocess.run([sys.executable, str(SCRIPTS / "svg_preview.py"), "design/html", "--no-open"], cwd=work,
                   capture_output=True, env={**os.environ, "SVG_UI_MODE": "local"})

    page = browser.new_page(viewport={"width": 1600, "height": 900})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto((html_dir / "_preview.html").resolve().as_uri())
    page.wait_for_function("roots.length === 2 && roots.every(r => r.doc && r.screen)")
    check("html screens become cards", page.evaluate("roots.map(r => r.kind + ':' + r.id)") ==
          ["html:SettingsDefault", "html:SettingsSaving"])
    check("html: state select hidden, width select shown",
          page.evaluate("[document.getElementById('state').parentElement.hidden, document.getElementById('width').parentElement.hidden]") == [True, False])
    check("html scripts and handlers do not run", page.evaluate("window.__pwned") is None and
          page.evaluate("roots[0].frame.contentWindow.__pwned") is None)
    check("html renders at the design width, not the card width", page.evaluate("roots.map(r => r.w)") == [1280, 1280],
          page.evaluate("roots.map(r => r.w)"))
    check("design width comes from data-target", page.evaluate("""['mobile-390x844', 'tablet-768', 'desktop-1440x900', '']
      .map(t => { const e = document.createElement('div'); e.dataset.target = t; return designW(e); })""") == [390, 768, 1440, 1280])
    geo = """roots.map(r => [...r.screen.querySelectorAll('[data-component][id]')]
      .map(n => { const b = n.getBoundingClientRect(); return [b.x, b.y, b.width, b.height].map(Math.round); }))"""
    before, k0 = page.evaluate(geo), page.evaluate("roots[0].scale")
    page.set_viewport_size({"width": 900, "height": 900})
    page.wait_for_timeout(150)
    check("a squeezed pane scales the html draft down but moves nothing inside it",
          page.evaluate(geo) == before and page.evaluate("roots[0].scale") < k0, (k0, page.evaluate("roots[0].scale")))
    page.evaluate("""() => {
      roots[1].frame.style.width = '390px'; roots[1].dw = 390; roots[1].w = 390; applyZoom(); }""")
    check("fit to width scales each card on its own", page.evaluate("roots[1].scale") == 1 and page.evaluate("roots[0].scale") < 1,
          page.evaluate("roots.map(r => r.scale)"))
    page.locator("#zoom").select_option("same")
    check("same scale gives every card the scale of the widest draft",
          page.evaluate("roots[0].scale === roots[1].scale && roots[1].scale < 1"), page.evaluate("roots.map(r => r.scale)"))
    page.locator("#zoom").select_option("fit")
    page.evaluate("roots[1].dw = 1280; sizeFrame(roots[1])")
    page.set_viewport_size({"width": 1600, "height": 900})
    page.wait_for_timeout(150)

    page.locator("#width").select_option("1280")
    page.wait_for_function("roots[0].w === 1280")
    select(page, "DefaultSave")
    check("html chip and breadcrumb", "DefaultSave" in page.locator("#qeChips").inner_text() and
          page.locator("#qeCrumbs").inner_text().replace("\n", "") == "SettingsDefault›DefaultSave",
          page.locator("#qeCrumbs").inner_text())
    check("html reference carries the width", html_refs(page) == [f"{HTML_FILE}#DefaultSave?width=1280"], html_refs(page))
    job = snapshot(page.evaluate("buildPrompt()"))
    check("html snapshot", job["format"] == "html" and job["screen"] == "SettingsDefault" and job["view"]["width"] == 1280, job)
    want = next(c for c in baseline[1280]["screens"][0]["components"] if c["id"] == "DefaultSave")["bbox"]
    got = job["selection"][0]["bbox"]
    check("html bbox matches the standalone review", all(abs(a - b) <= 1 for a, b in zip(got, want)), (got, want))
    wide = page.evaluate("roots[0].frame.offsetHeight")

    page.locator("#width").select_option("390")
    page.wait_for_function("roots[0].w === 390")
    page.wait_for_timeout(100)
    check("html reflows at 390", page.evaluate("roots[0].frame.offsetWidth") == 390 and page.evaluate("roots[0].frame.offsetHeight") > wide)
    want = next(c for c in baseline[390]["screens"][0]["components"] if c["id"] == "DefaultSave")["bbox"]
    got = snapshot(page.evaluate("buildPrompt()"))["selection"][0]["bbox"]
    check("html bbox at 390 matches", all(abs(a - b) <= 1 for a, b in zip(got, want)), (got, want))

    frame = page.frame_locator("iframe").first
    frame.locator("#DefaultEmail").click(modifiers=["Shift"])
    check("html multi-select is one line", html_refs(page) == [f"{HTML_FILE}#DefaultSave,DefaultEmail?width=390"], html_refs(page))
    select(page, "SavingSave")
    check("html state in reference", html_refs(page) == [f"{HTML_FILE}#SavingSave?state=saving&width=390"], html_refs(page))

    to_origin(page)
    f = page.locator("iframe").first.bounding_box()
    # Playwright's own drag handling stalls on a pressed button over a sandboxed iframe, so send
    # the same real mouse input through CDP instead.
    cdp = page.context.new_cdp_session(page)

    def mouse(kind, x, y, buttons=0):
        cdp.send("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left",
                                               "buttons": buttons, "clickCount": 1, "modifiers": 1})  # 1 = Alt

    mouse("mouseMoved", f["x"] + 30, f["y"] + 20)
    mouse("mousePressed", f["x"] + 30, f["y"] + 20, 1)
    for i in range(1, 5):
        mouse("mouseMoved", f["x"] + 30 + 50 * i, f["y"] + 20 + 10 * i, 1)
    mouse("mouseReleased", f["x"] + 230, f["y"] + 60)
    refs = html_refs(page)
    check("html region reference", len(refs) == 1 and re.fullmatch(
        rf"{HTML_FILE}#region\((\d+),(\d+),(\d+),(\d+)\)@SettingsDefault\?width=390", refs[0]), refs)
    check("html preview has no script errors", not errors, errors)
    page.close()


def main() -> int:
    from playwright.sync_api import sync_playwright  # type: ignore
    with tempfile.TemporaryDirectory() as td:
        work = Path(td).resolve()
        (work / "design").mkdir()
        shutil.copy(EXAMPLE, work / FILE)
        port = free_port()
        server = subprocess.Popen([sys.executable, str(SCRIPTS / "svg_preview.py"), "design", "--serve", "--no-open",
                                   "--port", str(port)], cwd=work, stdout=subprocess.DEVNULL,
                                  env={**os.environ, "SVG_UI_MODE": "local"})
        url = f"http://127.0.0.1:{port}/"
        try:
            for _ in range(50):
                try:
                    urllib.request.urlopen(url + "__version", timeout=1)
                    break
                except OSError:
                    time.sleep(0.1)
            with sync_playwright() as p:
                browser = _launch_browser(p)
                ctx = browser.new_context(viewport={"width": 1600, "height": 900})
                ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=url.rstrip("/"))
                page = ctx.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(url)
                test_selection(page)
                prompt = test_prompt(page)
                test_render_job(prompt, work)
                test_multi(page)
                test_region_zoom(page)
                test_inbox(page, port, work)
                check("no script errors", not errors, errors)
                ctx.close()
                test_denied(browser, url)
                test_responsive(browser, url, port)
                test_paths(browser, work)
                test_html(browser, work)
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=10)

    failed = [r for r in results if not r[1]]
    for n, ok, d in results:
        print(f"{'PASS' if ok else 'FAIL'}  {n}  {d}")
    print()
    if failed:
        print(f"{len(failed)} of {len(results)} checks failed")
        return 1
    print(f"ALL QUICK EDIT TESTS PASSED ({len(results)} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
