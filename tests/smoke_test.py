#!/usr/bin/env python3
"""End-to-end smoke test for the svg-ui-bridge scripts. Runs on Linux, macOS and Windows.

  python tests/smoke_test.py              # full run (needs Pillow + one SVG renderer)
  python tests/smoke_test.py --no-render  # skip everything that rasterises

Works on a temporary copy of the bundled example, so the repository stays clean.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "svg-ui-bridge"
SCRIPTS = SKILL / "scripts"
EXAMPLE = SKILL / "templates" / "example-screen.svg"
BUILD_ZIP = ROOT / "tools" / "build_skill_zip.py"

BAD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">
  <rect x="0" y="0" width="400" height="200" fill="#222"/>
  <g id="saveBtn"><rect x="10" y="10" width="80" height="30" fill="#4f8cff"/></g>
</svg>"""

MIXED_STATE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 40" width="100" height="40">
  <g id="Field" data-component="Input">
    <text x="2" y="12" font-size="10" fill="#000000">Label</text>
    <g data-state="default"><rect x="0" y="20" width="100" height="20" fill="#00aa00"/></g>
    <g data-state="error" display="none"><rect x="0" y="20" width="100" height="20" fill="#cc0000"/></g>
  </g>
</svg>"""

results: list[tuple[str, bool, str]] = []


def run(name: str, args: list[str], expect: int = 0, stdin: str | None = None, cwd: Path | None = None,
        must_contain: str | None = None, env: dict[str, str] | None = None,
        timeout: float | None = None) -> str:
    try:
        p = subprocess.run([sys.executable, *args], input=stdin, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=cwd, timeout=timeout,
                           env={**os.environ, **env} if env else None)
    except subprocess.TimeoutExpired:
        results.append((name, False, f"still running after {timeout}s"))
        return ""
    out = (p.stdout or "") + (p.stderr or "")
    ok = p.returncode == expect and (must_contain is None or must_contain in out)
    detail = f"exit {p.returncode} (expected {expect})"
    if must_contain and must_contain not in out:
        detail += f", missing '{must_contain}'"
    results.append((name, ok, detail if not ok else ""))
    if not ok:
        print(f"--- output of {name} ---\n{out}\n---")
    return out


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, cond, "" if cond else detail))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()

    try:
        import PIL  # noqa: F401
    except ImportError:
        print("Pillow is missing: python -m pip install pillow")
        return 1

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        design = work / "design"
        design.mkdir()
        svg = design / "example.svg"
        shutil.copy(EXAMPLE, svg)
        s = lambda n: str(SCRIPTS / n)  # noqa: E731

        # 1. lint: good file passes, bad file fails with the expected errors
        run("lint good", [s("svg_lint.py"), str(svg)], must_contain="OK")
        bad = design / "bad.svg"
        bad.write_text(BAD_SVG, encoding="utf-8")
        run("lint bad", [s("svg_lint.py"), str(bad)], expect=1, must_contain="no viewBox")

        # 2. hook: bad SVG under design/ -> exit 2; non-SVG -> 0
        payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(bad)}})
        run("hook blocks bad svg", [s("lint_hook.py")], expect=2, stdin=payload)
        payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(work / "x.html")}})
        run("hook ignores non-svg", [s("lint_hook.py")], expect=0, stdin=payload)
        bad.unlink()

        # 3. tokens
        out = run("tokens css", [s("tokens_export.py"), str(svg), "--format", "css"], must_contain="--color-primary")
        run("tokens egui", [s("tokens_export.py"), str(svg), "--format", "egui"], must_contain="Color32")
        run("tokens bevy", [s("tokens_export.py"), str(svg), "--format", "bevy"], must_contain="srgba_u8")

        # 4. manifest without rendering
        run("manifest (no bbox)", [s("svg_manifest.py"), str(svg), "--no-bbox"])
        man = json.loads((design / "example.components.json").read_text(encoding="utf-8"))
        ids = [c["id"] for c in man["components"]]
        check("manifest components", len(ids) == 15 and "SearchButton" in ids, f"got {len(ids)}: {ids[:5]}")
        btn = next(c for c in man["components"] if c["id"] == "SearchButton")
        check("manifest states", btn["states"] == ["default", "disabled", "hover"], str(btn["states"]))

        # 5. static preview page
        run("preview html", [s("svg_preview.py"), str(design), "--no-open"])
        html = (design / "_preview.html").read_text(encoding="utf-8")
        check("preview content", "SearchButton" in html and "attachShadow" in html, "page missing data")
        urls = {u for u in re.findall(r"https?://[^\s\"'`<>\\]+", html) if "www.w3.org/" not in u}
        check("preview self-contained", not urls, str(sorted(urls)[:5]))

        # 6. environment report, and --serve falling back to a static page in sandbox mode
        run("env_check", [s("env_check.py")], must_contain="MODE=", timeout=120)
        out = run("env_check json", [s("env_check.py"), "--json"], env={"SVG_UI_MODE": "sandbox"}, timeout=120)
        report = json.loads(out)
        check("env_check forced mode", report["mode"] == "sandbox" and report["mode_source"] == "SVG_UI_MODE",
              str(report.get("mode")))
        (design / "_preview.html").unlink()
        run("serve in sandbox goes static", [s("svg_preview.py"), str(design), "--serve"],
            env={"SVG_UI_MODE": "sandbox"}, must_contain="改用靜態頁", timeout=30)
        check("serve in sandbox wrote page", (design / "_preview.html").exists())

        # 7. skill zip: right layout, nothing excluded, same bytes every time
        stray = SKILL / "templates" / "_smoke.png"
        stray.write_bytes(b"not an image")
        try:
            zip_a, zip_b = work / "a.zip", work / "b.zip"
            run("build skill zip", [str(BUILD_ZIP), "--out", str(zip_a)], must_contain="wrote")
            run("rebuild skill zip", [str(BUILD_ZIP), "--out", str(zip_b)])
        finally:
            stray.unlink()
        names = zipfile.ZipFile(zip_a).namelist() if zip_a.exists() else []
        check("zip layout", all(n.startswith("svg-ui-bridge/") for n in names) and {
            "svg-ui-bridge/SKILL.md", "svg-ui-bridge/scripts/env_check.py",
            "svg-ui-bridge/references/environments.md",
            "svg-ui-bridge/templates/example-screen.svg"} <= set(names), str(names[:5]))
        check("zip includes HTML source", "svg-ui-bridge/templates/html-design/review.html" in names
              and "svg-ui-bridge/templates/html-design/theme.css" in names)
        banned = [n for n in names if n != "svg-ui-bridge/templates/html-design/review.html" and re.search(r"__pycache__|\.pyc$|\.png$|\.html$|\.components\.|"
                                                r"/tests/|/docs/|\.claude-plugin", n)]
        check("zip excludes generated files", names and not banned, str(banned[:5]))
        check("zip is repeatable", zip_a.exists() and zip_b.exists()
              and zip_a.read_bytes() == zip_b.read_bytes())

        if not a.no_render:
            # 8. render all states
            out = run("render all states", [s("svg_render.py"), str(svg), "--all-states"], must_contain="rendered")
            for st in ("", ".hover", ".disabled", ".selected"):
                check(f"png exists{st or ' default'}", (design / f"example{st}.png").exists())
            from PIL import Image
            im = Image.open(design / "example.png").convert("RGB")
            px = im.getpixel((640, 400))
            check("tokens resolved (not black)", px != (0, 0, 0), f"pixel {px}")
            check("canvas size", im.size == (1280, 800), str(im.size))

            # a state layer next to plain siblings: the default layer must stay visible
            mixed = work / "mixed.svg"
            mixed.write_text(MIXED_STATE_SVG, encoding="utf-8")
            run("render mixed default", [s("svg_render.py"), str(mixed), "-o", str(work / "mixed.png")])
            run("render mixed error", [s("svg_render.py"), str(mixed), "--state", "error",
                                       "-o", str(work / "mixed.error.png")])
            for png, want in (("mixed.png", (0, 170, 0, 255)), ("mixed.error.png", (204, 0, 0, 255))):
                pixel = Image.open(work / png).convert("RGBA").getpixel((50, 30))
                check(f"state layer in {png}", pixel == want, f"pixel {pixel}, wanted {want}")

            # 9. manifest with measured bboxes
            run("manifest (bbox)", [s("svg_manifest.py"), str(svg)])
            man = json.loads((design / "example.components.json").read_text(encoding="utf-8"))
            btn = next(c for c in man["components"] if c["id"] == "SearchButton")
            bb = btn["bbox"] or [0, 0, 0, 0]
            check("bbox SearchButton", abs(bb[0] - 1120) <= 2 and abs(bb[2] - 136) <= 2, str(bb))

            # 10. visual diff: identical -> PASS; broken button -> FAIL naming SearchButton
            shots = work / "shots"
            shots.mkdir()
            same = shots / "same.png"
            shutil.copy(design / "example.png", same)
            run("diff identical passes", [s("visual_diff.py"), str(svg), str(same),
                                          "--manifest", str(design / "example.components.json")],
                must_contain="PASS")
            broken = Image.open(design / "example.png").convert("RGB")
            from PIL import ImageDraw
            ImageDraw.Draw(broken).rectangle((1120, 80, 1256, 124), fill=(15, 17, 21))  # erase the button
            bp = shots / "broken.png"
            broken.save(bp)
            out = run("diff broken fails", [s("visual_diff.py"), str(svg), str(bp),
                                            "--manifest", str(design / "example.components.json")],
                      expect=1, must_contain="FAIL")
            check("diff names SearchButton", "SearchButton" in out and "over limit" in out, "component not flagged")
            check("diff image written", (shots / "broken.diff.png").exists())

            # 11. web screenshot of a page showing the example, compared with the SVG
            if importlib.util.find_spec("playwright"):
                page = design / "page.html"
                page.write_text("<!doctype html><meta charset=utf-8><body style='margin:0'>"
                                + EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
                web = shots / "web.png"
                run("screenshot page", [s("screenshot_web.py"), str(page), "-o", str(web),
                                        "--size", "1280x800"], must_contain="wrote")
                run("diff web screenshot passes", [s("visual_diff.py"), str(svg), str(web),
                                                   "--manifest", str(design / "example.components.json")],
                    env={"SVG_UI_RENDERER": "playwright"}, must_contain="PASS")
                run("screenshot rejects other schemes", [s("screenshot_web.py"), "ftp://example.invalid/x",
                                                         "-o", str(web)], expect=2)
                leak = design / "leak.html"
                leak.write_text("<img src='http://example.invalid/x.png'>", encoding="utf-8")
                run("screenshot blocks other origins", [s("screenshot_web.py"), str(leak), "-o", str(web)],
                    must_contain="blocked http://example.invalid/x.png")
            else:
                print("SKIP  web screenshot checks: Playwright is not installed")

    width = max(len(n) for n, _, _ in results)
    failed = [r for r in results if not r[1]]
    for n, ok, d in results:
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(width)}  {d}")
    print()
    if failed:
        print(f"{len(failed)} of {len(results)} checks failed")
        return 1
    print(f"ALL SMOKE TESTS PASSED ({len(results)} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
