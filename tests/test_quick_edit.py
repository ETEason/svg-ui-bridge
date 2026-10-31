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
    b = box_of(page, cid)
    page.mouse.move((b["left"] + b["right"]) / 2, (b["top"] + b["bottom"]) / 2)
    if shift:
        page.keyboard.down("Shift")
    page.mouse.down()
    page.mouse.up()
    if shift:
        page.keyboard.up("Shift")


def alt_drag(page, svg_box: list[int]) -> None:
    """Alt+drag over an SVG-coordinate box, whatever the zoom."""
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


def test_responsive(browser, url: str, port: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for w, h in ((1280, 800), (600, 800), (390, 844), (1024, 500)):
        ctx = browser.new_context(viewport={"width": w, "height": h})
        page = ctx.new_page()
        page.goto(url)
        select(page, "NavBar-Title")
        p = page.evaluate("() => { const b = document.getElementById('qe').getBoundingClientRect(); return {l: b.left, r: innerWidth - b.right, t: b.top, b: innerHeight - b.bottom, h: b.height}; }")
        check(f"{w}x{h} bottom panel with 16px sides", abs(p["l"] - 16) < 1 and abs(p["r"] - 16) < 1 and abs(p["b"] - 16) < 1, p)
        check(f"{w}x{h} panel at most 45vh", p["h"] <= h * 0.45 + 1, p)

        copy = page.locator("#qeCopy").bounding_box()
        check(f"{w}x{h} Copy Prompt reachable and 40px tall", copy["height"] >= 40 and copy["y"] + copy["height"] <= h, copy)
        select(page, "ArticlePreview")
        b, top = box_of(page, "ArticlePreview"), page.evaluate("document.getElementById('qe').getBoundingClientRect().top")
        ok = b["bottom"] <= top or b["top"] <= page.evaluate("document.querySelector('header').getBoundingClientRect().bottom") + 9
        check(f"{w}x{h} selected component clear of panel", ok, (b, top))
        select(page, "NavBar-Status")
        b = box_of(page, "NavBar-Status")
        check(f"{w}x{h} small component above panel", b["bottom"] <= page.evaluate("document.getElementById('qe').getBoundingClientRect().top") + 1, b)

        tree_box = page.evaluate("document.querySelector('aside').getBoundingClientRect().toJSON()")
        if w > 800:
            check(f"{w}x{h} tree stays clear of panel", tree_box["bottom"] <= page.evaluate("document.getElementById('qe').getBoundingClientRect().top") + 1, tree_box)
        page.locator("#qeText").fill("示範文字")
        page.screenshot(path=str(OUT / f"quick-edit-{w}x{h}.png"))
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
    full = page.locator("#qe").bounding_box()["height"]
    page.locator("#qeHandle").click()
    small = page.locator("#qe").bounding_box()["height"]
    check("handle collapses to one line", small < 90 and "已選 1 項" in page.locator("#qeCount").inner_text(), small)
    check("collapsed Copy Prompt still there", page.locator("#qeCopy").is_visible())
    page.screenshot(path=str(OUT / "quick-edit-collapsed.png"))
    page.locator("#qeHandle").click()
    check("handle expands again", abs(page.locator("#qe").bounding_box()["height"] - full) < 2)

    page.keyboard.press("Escape")
    check("Esc closes the panel", not page.locator("#qe").is_visible())
    check("closing releases the reserved space", page.evaluate("getComputedStyle(document.body).paddingBottom") == "0px")
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
