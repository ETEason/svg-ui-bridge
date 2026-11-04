#!/usr/bin/env python3
"""Draw the hand-drawn workflow diagrams in docs/images/ (Traditional Chinese and English).

  python tools/draw_diagrams.py              # writes docs/images/diagram-*.{zh-TW,en}.png
  python tools/draw_diagrams.py --svg-only   # keeps the SVG sources in dist/diagrams/ for review

Strokes are jittered with a fixed seed, so the same text gives the same picture. The handwriting
fonts (Segoe Print, DFKai-SB) are Windows fonts; elsewhere the browser falls back to cursive.
"""
from __future__ import annotations

import argparse
import math
import random
import sys
import tempfile
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "svg-ui-bridge" / "scripts"))

HAND = "'Segoe Print', 'DFKai-SB', 'KaiTi', 'Comic Sans MS', cursive"
MONO = "'Cascadia Code', Consolas, monospace"
INK = "#3b3f4a"
BG = "#eef0f8"
# role colours: fill, stroke
ROLE = {
    "you": ("#c9dcfa", "#4a76c9"),
    "agent": ("#bfe3c9", "#3f8f5a"),
    "tool": ("#f8d9bd", "#c0782f"),
    "decision": ("#fbe7a6", "#c79a12"),
    "end": ("#f8c9c9", "#d0605f"),
    "note": ("#fff7d6", "#b9a361"),
}
ZONE = {
    "peach": ("#f6e3d6", "#d9a07a", "#b4683a"),
    "green": ("#e0f1e6", "#86c39f", "#2f7d52"),
    "purple": ("#eee6fb", "#b9a3e3", "#7b55c2"),
    "blue": ("#e3ecfb", "#95b3e6", "#3d63b0"),
}
CHIP_FILL, CHIP_TEXT = "#2f3445", "#ffe2b8"


def text_width(text: str, size: float) -> float:
    """Approximate monospace width; wide characters take a full em."""
    return sum(size if ord(ch) > 0x2E7F else size * 0.62 for ch in text)


class Sketch:
    def __init__(self, width: int, height: int, seed: int):
        self.w, self.h = width, height
        self.rnd = random.Random(seed)
        self.parts: list[str] = []
        self.clip = 0

    def j(self, amount: float = 1.6) -> float:
        return self.rnd.uniform(-amount, amount)

    def add(self, s: str) -> None:
        self.parts.append(s)

    # ---- primitives -------------------------------------------------------------------------
    def _side(self, x1, y1, x2, y2, bow=1.8):
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        return f"Q {mx + self.j(bow):.1f} {my + self.j(bow):.1f} {x2 + self.j():.1f} {y2 + self.j():.1f}"

    def _rrect_path(self, x, y, w, h, r):
        p = [f"M {x + r + self.j():.1f} {y + self.j():.1f}",
             self._side(x + r, y, x + w - r, y),
             f"Q {x + w + self.j():.1f} {y + self.j():.1f} {x + w + self.j():.1f} {y + r + self.j():.1f}",
             self._side(x + w, y + r, x + w, y + h - r),
             f"Q {x + w + self.j():.1f} {y + h + self.j():.1f} {x + w - r + self.j():.1f} {y + h + self.j():.1f}",
             self._side(x + w - r, y + h, x + r, y + h),
             f"Q {x + self.j():.1f} {y + h + self.j():.1f} {x + self.j():.1f} {y + h - r + self.j():.1f}",
             self._side(x, y + h - r, x, y + r),
             f"Q {x + self.j():.1f} {y + self.j():.1f} {x + r + self.j():.1f} {y + self.j():.1f}"]
        return " ".join(p)

    def rrect(self, x, y, w, h, fill, stroke, r=12, width=2.2, dash=None, opacity=1.0):
        self.add(f'<path d="{self._rrect_path(x, y, w, h, r)} Z" fill="{fill}" fill-opacity="{opacity}" stroke="none"/>')
        d = f' stroke-dasharray="{dash}"' if dash else ""
        for k in (width, width * 0.6):
            self.add(f'<path d="{self._rrect_path(x, y, w, h, r)}" fill="none" stroke="{stroke}" '
                     f'stroke-width="{k:.1f}" stroke-linecap="round" stroke-linejoin="round"{d}/>')

    def diamond(self, cx, cy, w, h, fill, stroke):
        def path():
            pts = [(cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)]
            pts = [(px + self.j(2), py + self.j(2)) for px, py in pts]
            return "M " + " L ".join(f"{px:.1f} {py:.1f}" for px, py in pts) + " Z"
        self.add(f'<path d="{path()}" fill="{fill}" stroke="none"/>')
        for k in (2.2, 1.3):
            self.add(f'<path d="{path()}" fill="none" stroke="{stroke}" stroke-width="{k}" stroke-linejoin="round"/>')

    def blob(self, cx, cy, rx, ry, fill, stroke, hachure=True):
        def path():
            pts = []
            for i in range(28):
                a = 2 * math.pi * i / 28
                pts.append((cx + (rx + self.j(2)) * math.cos(a), cy + (ry + self.j(2)) * math.sin(a)))
            return "M " + " L ".join(f"{px:.1f} {py:.1f}" for px, py in pts) + " Z"
        self.clip += 1
        cid = f"clip{self.clip}"
        self.add(f'<clipPath id="{cid}"><ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}"/></clipPath>')
        self.add(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}"/>')
        if hachure:
            lines = []
            for off in range(-int(rx + ry), int(rx + ry), 11):
                x1, y1 = cx + off - ry, cy + ry
                lines.append(f'<line x1="{x1 + self.j(1):.1f}" y1="{y1:.1f}" x2="{x1 + 2 * ry + self.j(1):.1f}" '
                             f'y2="{cy - ry:.1f}" stroke="{stroke}" stroke-width="1.4" stroke-opacity="0.55"/>')
            self.add(f'<g clip-path="url(#{cid})">{"".join(lines)}</g>')
        for k in (2.4, 1.3):
            self.add(f'<path d="{path()}" fill="none" stroke="{INK}" stroke-width="{k}" stroke-linejoin="round"/>')

    def text(self, x, y, lines, size=19, color=INK, anchor="middle", weight="normal", font=HAND, gap=1.3):
        if isinstance(lines, str):
            lines = [lines]
        y0 = y - (len(lines) - 1) * size * gap / 2
        spans = "".join(f'<tspan x="{x}" y="{y0 + i * size * gap:.1f}">{escape(t)}</tspan>' for i, t in enumerate(lines))
        self.add(f'<text font-family="{font}" font-size="{size}" fill="{color}" text-anchor="{anchor}" '
                 f'font-weight="{weight}" dominant-baseline="middle">{spans}</text>')

    def chip(self, cx, cy, label, size=14):
        w = text_width(label, size) + 18
        self.rrect(cx - w / 2, cy - size * 0.95, w, size * 1.9, CHIP_FILL, CHIP_FILL, r=7, width=1.2)
        self.text(cx, cy + 1, label, size=size, color=CHIP_TEXT, font=MONO)
        return w

    def chips(self, cx, cy, labels, size=14, gap=10):
        widths = [text_width(t, size) + 18 for t in labels]
        x = cx - (sum(widths) + gap * (len(widths) - 1)) / 2
        for t, w in zip(labels, widths):
            self.chip(x + w / 2, cy, t, size)
            x += w + gap

    def chain(self, cx, cy, labels, size=13, gap=34):
        """Chips in a row with an arrow in each gap."""
        widths = [text_width(t, size) + 18 for t in labels]
        x = cx - (sum(widths) + gap * (len(widths) - 1)) / 2
        for i, (t, w) in enumerate(zip(labels, widths)):
            self.chip(x + w / 2, cy, t, size)
            x += w
            if i < len(labels) - 1:
                self.arrow([(x + 5, cy), (x + gap - 5, cy)], width=1.4)
                x += gap

    def arrow(self, points, color=INK, label=None, label_at=0.5, width=2.2):
        pts = [(px + self.j(0.8), py + self.j(0.8)) for px, py in points]
        d = f"M {pts[0][0]:.1f} {pts[0][1]:.1f} " + " ".join(self._side(*a, *b, bow=2.4) for a, b in zip(pts, pts[1:]))
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')
        (x1, y1), (x2, y2) = points[-2], points[-1]
        a = math.atan2(y2 - y1, x2 - x1)
        tip = (x2, y2)
        left = (x2 - 15 * math.cos(a - 0.42), y2 - 15 * math.sin(a - 0.42))
        right = (x2 - 15 * math.cos(a + 0.42), y2 - 15 * math.sin(a + 0.42))
        self.add(f'<path d="M {tip[0]:.1f} {tip[1]:.1f} L {left[0]:.1f} {left[1]:.1f} L {right[0]:.1f} {right[1]:.1f} Z" '
                 f'fill="{color}" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/>')
        if label:
            seg = min(len(points) - 2, int(label_at * (len(points) - 1)))
            (ax, ay), (bx, by) = points[seg], points[seg + 1]
            lx, ly = ax + (bx - ax) * 0.5, ay + (by - ay) * 0.5
            self.rrect(lx - 22, ly - 14, 44, 28, BG, BG, r=8, width=0.1)
            self.text(lx, ly + 1, label, size=17, color=color)

    # ---- composites -------------------------------------------------------------------------
    def zone(self, x, y, w, h, kind, label):
        fill, stroke, ink = ZONE[kind]
        self.rrect(x, y, w, h, fill, stroke, r=26, width=2, dash="12 8", opacity=0.85)
        self.text(x + 22, y + 24, label, size=20, color=ink, anchor="start", weight="bold")

    def node(self, cx, cy, w, h, role, lines, tools=(), tag=None):
        fill, stroke = ROLE[role]
        self.rrect(cx - w / 2, cy - h / 2, w, h, fill, stroke)
        has_tools = bool(tools)
        ty = cy - (14 if has_tools else 0)
        self.text(cx, ty, lines, size=19)
        if has_tools:
            self.chips(cx, cy + h / 2 - 22, list(tools))
        if tag:
            tw = len(tag) * 13 + 20
            self.rrect(cx - w / 2 + 10, cy - h / 2 - 13, tw, 24, stroke, stroke, r=10, width=1)
            self.text(cx - w / 2 + 10 + tw / 2, cy - h / 2 - 1, tag, size=13, color="#ffffff", font=MONO)

    def decision(self, cx, cy, w, h, lines):
        fill, stroke = ROLE["decision"]
        self.diamond(cx, cy, w, h, fill, stroke)
        self.text(cx, cy, lines, size=18)

    def legend(self, x, y, items, title):
        w, h = 270, 46 + 36 * len(items)
        self.rrect(x, y, w, h, "#f4f6fb", "#a6adc2", r=16, width=1.6)
        self.text(x + 20, y + 26, title, size=19, anchor="start", weight="bold")
        for i, (kind, label) in enumerate(items):
            yy = y + 62 + i * 36
            if kind == "chip":
                self.rrect(x + 20, yy - 11, 38, 22, CHIP_FILL, CHIP_FILL, r=6, width=1)
                self.text(x + 39, yy + 1, "</>", size=12, color=CHIP_TEXT, font=MONO)
            elif kind == "decision":
                self.diamond(x + 39, yy, 36, 26, *ROLE["decision"])
            else:
                self.rrect(x + 22, yy - 11, 34, 22, *ROLE[kind], r=6, width=1.6)
            self.text(x + 72, yy + 1, label, size=16, anchor="start")

    def svg(self, title, title_x=None) -> str:
        body = "\n".join(self.parts)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}">\n'
                f'<rect width="{self.w}" height="{self.h}" fill="{BG}"/>\n'
                f'<text x="{title_x or self.w / 2}" y="52" font-family="{HAND}" font-size="34" fill="#2f7d52" text-anchor="middle" '
                f'font-weight="bold">{escape(title)}</text>\n{body}\n</svg>\n')


# ---- texts ----------------------------------------------------------------------------------
T = {
    "zh-TW": {
        "flow": "svg-ui-bridge 工作流程", "render": "兩種格式的渲染路徑", "qe": "Quick Edit 的一次來回",
        "legend": "圖例", "you": "你", "agent": "Agent", "tool": "程式步驟", "chip": "實際執行的程式",
        "decision": "判斷", "end": "結束", "yes": "是", "no": "否", "pass": "通過", "fail": "未過",
        "z1": "① 選擇格式", "z2": "② 草稿與自我檢查", "z3": "③ 你審閱", "z4": "④ 實作與驗證（要求實作時）",
        "start": "你提出 UI 需求", "q1": ["專案或你", "指定了格式？"], "given": "照指定的格式",
        "q2": ["是網頁 UI？"], "html": "HTML/CSS 設計稿", "svgf": "SVG 設計稿",
        "env": ["判斷執行環境", "local 或 sandbox"], "draft": ["寫設計稿", "元件多時可用 TSX 產生"],
        "self": ["自我檢查：檢查規範、算圖、看 PNG"], "preview": ["預覽頁：即時頁面或靜態頁"],
        "ok": ["你核准了嗎？"], "fb": ["用 Quick Edit", "或文字回饋"], "impl": ["要求實作嗎？"],
        "done1": ["結束：", "交付核准的設計稿"], "split": ["拆解元件清單、匯出 token"],
        "build": ["逐元件實作，截取實際畫面"], "shot": "screenshot_web.py（網頁）", "diff": ["和設計基準逐元件比對"],
        "passq": ["整體 ≤ 2%", "每個元件 ≤ 10%？"], "fix": ["修正超標的元件"],
        "done2": ["完成：回報數字", "與差異圖"],
        "design": "設計稿", "svgz": "SVG", "htmlz": "HTML/CSS",
        "youview": ["給你看：預覽頁"], "agentview": ["給 Agent 看：PNG"],
        "svgyou": ["嵌進頁面（shadow root）", "狀態選單切換圖層", "縮放選單"],
        "htmlyou": ["每個畫面一個 iframe", "移除腳本與事件屬性", "寬度選單會重新排版"],
        "svgagent": ["依序嘗試四種算圖器", "非瀏覽器時文字可能略有差異"],
        "htmlagent": ["一律用瀏覽器算圖（關閉 JS）", "和你看到的一致"],
        "chain": "第一個能用的就用", "same": "同一個預覽頁、同一個 Quick Edit",
        "pick": ["在預覽頁點選元件", "Shift 多選、Alt 框選"], "write": ["寫修改建議", "按 Copy Prompt"],
        "prompt": ["剪貼簿：建議原文 + File", "+ References + Snapshot JSON"],
        "refs": ["login.svg#SignInButton?state=hover", "review.html#DefaultSave?width=390"],
        "repro": ["重現你看到的畫面", "並標出選取，看圖確認位置"], "edit": ["依 reference 找到元件", "修改設計稿"],
        "refresh": ["更新預覽頁", "--serve 自動重載，靜態頁重新產生"], "again": ["你再看一次：", "核准或繼續修改"],
        "inbox": ["或：--serve 時按「送給 Agent」", "寫進 design/_feedback.md"],
    },
    "en": {
        "flow": "svg-ui-bridge workflow", "render": "How each format is rendered", "qe": "One Quick Edit round trip",
        "legend": "Legend", "you": "You", "agent": "Agent", "tool": "Tool step", "chip": "Script that runs",
        "decision": "Decision", "end": "End", "yes": "yes", "no": "no", "pass": "pass", "fail": "fail",
        "z1": "1  Choose the format", "z2": "2  Draft and self-check", "z3": "3  Your review",
        "z4": "4  Build and verify (when asked)",
        "start": "You ask for UI work", "q1": ["Format set by the", "project or you?"], "given": "Use that format",
        "q2": ["Web UI?"], "html": "HTML/CSS draft", "svgf": "SVG draft",
        "env": ["Detect the environment", "local or sandbox"], "draft": ["Write the draft", "TSX when parts repeat"],
        "self": ["Self-check: lint, render, read the PNG"], "preview": ["Preview page: live or static"],
        "ok": ["Approved?"], "fb": ["Quick Edit", "or written feedback"], "impl": ["Build it?"],
        "done1": ["Done: deliver the", "approved draft"], "split": ["Split into a manifest, export tokens"],
        "build": ["Build per component, screenshot it"], "shot": "screenshot_web.py (web)", "diff": ["Compare per component"],
        "passq": ["Overall ≤ 2%,", "each part ≤ 10%?"], "fix": ["Fix parts over the limit"],
        "done2": ["Done: report numbers", "and the diff image"],
        "design": "Draft", "svgz": "SVG", "htmlz": "HTML/CSS",
        "youview": ["What you see: preview page"], "agentview": ["What the agent sees: PNG"],
        "svgyou": ["Inline in a shadow root", "State select swaps layers", "Zoom select"],
        "htmlyou": ["One iframe per screen", "Scripts and handlers removed", "Width select reflows"],
        "svgagent": ["Tries four renderers in order", "Non-browser text may differ slightly"],
        "htmlagent": ["Always a browser, JS off", "Matches what you see"],
        "chain": "first one that works", "same": "Same preview page, same Quick Edit",
        "pick": ["Click parts in the preview", "Shift to add, Alt-drag a region"],
        "write": ["Write the change", "press Copy Prompt"],
        "prompt": ["Clipboard: your text + File", "+ References + Snapshot JSON"],
        "refs": ["login.svg#SignInButton?state=hover", "review.html#DefaultSave?width=390"],
        "repro": ["Re-renders your view", "marks it, checks the spot"], "edit": ["Finds the part by reference", "edits the draft"],
        "refresh": ["Refresh the preview", "live with --serve, else regenerate"], "again": ["You look again:", "approve or edit more"],
        "inbox": ["Or, with --serve: send to agent", "writes design/_feedback.md"],
    },
}


def legend_items(t):
    return [("you", t["you"]), ("agent", t["agent"]), ("tool", t["tool"]), ("chip", t["chip"]),
            ("decision", t["decision"]), ("end", t["end"])]


def flow(t) -> str:
    s = Sketch(1520, 1700, seed=7)
    C = 560
    s.zone(60, 160, 1120, 300, "peach", t["z1"])
    s.zone(60, 480, 1120, 340, "green", t["z2"])
    s.zone(60, 840, 1120, 330, "purple", t["z3"])
    s.zone(60, 1190, 1120, 470, "blue", t["z4"])

    s.blob(C, 112, 150, 38, "#ffffff", "#7d8597")
    s.text(C, 113, t["start"], size=21, weight="bold")
    s.arrow([(C, 152), (C, 196)])
    s.decision(C, 250, 270, 104, t["q1"])
    s.node(220, 250, 220, 64, "you", t["given"])
    s.arrow([(C - 135, 250), (330, 250)], label=t["yes"])
    s.arrow([(C, 302), (C, 336)], label=t["no"])
    s.decision(C, 380, 210, 84, t["q2"])
    s.node(860, 330, 220, 56, "agent", t["html"])
    s.node(860, 420, 220, 56, "agent", t["svgf"])
    s.arrow([(C + 105, 372), (750, 336)], label=t["yes"])
    s.arrow([(C + 105, 390), (750, 416)], label=t["no"])

    s.node(C, 552, 380, 96, "tool", t["env"], tools=["env_check.py"], tag=t["tool"])
    s.arrow([(315, 282), (315, 552), (C - 190, 552)])
    s.arrow([(970, 330), (1110, 330), (1110, 532), (C + 190, 532)])
    s.arrow([(970, 420), (1080, 420), (1080, 572), (C + 190, 572)])
    s.node(C, 665, 380, 66, "agent", t["draft"], tag=t["agent"])
    s.arrow([(C, 600), (C, 630)])
    s.node(C, 770, 460, 74, "tool", t["self"], tools=["svg_lint.py", "html_review.py", "svg_render.py"])
    s.arrow([(C, 698), (C, 731)])

    s.node(C, 910, 420, 84, "tool", t["preview"], tools=["svg_preview.py"])
    s.arrow([(C, 807), (C, 866)])
    s.decision(C, 1020, 220, 90, t["ok"])
    s.arrow([(C, 952), (C, 973)])
    s.node(900, 1020, 220, 72, "you", t["fb"], tag=t["you"])
    s.arrow([(C + 110, 1020), (790, 1020)], label=t["no"])
    s.arrow([(1010, 1000), (1140, 1000), (1140, 665), (C + 190, 665)])
    s.decision(C, 1125, 220, 80, t["impl"])
    s.arrow([(C, 1065), (C, 1085)], label=t["yes"])
    s.node(220, 1125, 240, 72, "end", t["done1"])
    s.arrow([(C - 110, 1125), (340, 1125)], label=t["no"])

    s.node(C, 1295, 660, 84, "tool", t["split"], tools=["svg_manifest.py", "html_review.py --standalone", "tokens_export.py"])
    s.arrow([(C, 1165), (C, 1251)], label=t["yes"])
    s.node(C, 1400, 440, 74, "agent", t["build"], tools=[t["shot"]])
    s.arrow([(C, 1337), (C, 1361)])
    s.node(C, 1495, 360, 74, "tool", t["diff"], tools=["visual_diff.py"])
    s.arrow([(C, 1437), (C, 1456)])
    s.decision(C, 1600, 300, 110, t["passq"])
    s.arrow([(C, 1532), (C, 1544)])
    s.node(920, 1600, 220, 56, "agent", t["fix"])
    s.arrow([(C + 150, 1600), (808, 1600)], label=t["fail"])
    s.arrow([(1030, 1580), (1130, 1580), (1130, 1400), (C + 220, 1400)])
    s.node(200, 1600, 240, 72, "end", t["done2"])
    s.arrow([(C - 150, 1600), (322, 1600)], label=t["pass"])

    s.legend(1215, 160, legend_items(t), t["legend"])
    return s.svg(t["flow"], title_x=620)


def render_paths(t) -> str:
    s = Sketch(1500, 930, seed=11)
    s.blob(600, 125, 120, 38, "#ffffff", "#7d8597")
    s.text(600, 126, t["design"], size=22, weight="bold")
    s.zone(60, 200, 520, 600, "peach", t["svgz"])
    s.zone(620, 200, 520, 600, "green", t["htmlz"])
    s.arrow([(520, 152), (320, 196)])
    s.arrow([(680, 152), (880, 196)])

    s.node(320, 365, 440, 170, "you", [t["youview"][0], *t["svgyou"]], tools=["svg_preview.py"], tag=t["you"])
    s.node(880, 365, 440, 170, "you", [t["youview"][0], *t["htmlyou"]], tools=["svg_preview.py"], tag=t["you"])
    s.node(320, 595, 440, 150, "agent", [t["agentview"][0], *t["svgagent"]], tools=["svg_render.py"], tag=t["agent"])
    s.node(880, 595, 440, 150, "agent", [t["agentview"][0], *t["htmlagent"]],
           tools=["svg_render.py --job", "html_review.py"], tag=t["agent"])
    s.chain(320, 718, ["resvg", "rsvg-convert", "Playwright", "cairosvg"])
    s.text(320, 760, t["chain"], size=16, color="#b4683a")
    s.chain(880, 718, ["Playwright"])

    s.rrect(60, 830, 1080, 56, ROLE["note"][0], ROLE["note"][1], r=14, width=1.8)
    s.text(600, 859, t["same"], size=19, color="#7a5b1a")
    s.legend(1190, 200, legend_items(t), t["legend"])
    return s.svg(t["render"], title_x=600)


def quick_edit(t) -> str:
    s = Sketch(1500, 900, seed=23)
    s.zone(60, 120, 520, 690, "blue", t["you"])
    s.zone(620, 120, 520, 690, "green", t["agent"])
    s.node(320, 235, 400, 84, "you", t["pick"], tag=t["you"])
    s.node(320, 380, 400, 84, "you", t["write"])
    s.arrow([(320, 277), (320, 336)])
    fill, stroke = ROLE["note"]
    s.rrect(100, 475, 440, 170, fill, stroke)
    s.text(320, 520, t["prompt"], size=19)
    s.text(320, 595, t["refs"], size=14, font=MONO, color="#7a5b1a")
    s.arrow([(320, 422), (320, 471)])
    s.node(320, 745, 400, 70, "note", t["inbox"])
    s.arrow([(520, 745), (600, 745), (600, 560)], color="#b9a361", width=1.6)

    s.node(880, 235, 430, 100, "tool", t["repro"], tools=["svg_render.py --job"], tag=t["agent"])
    s.arrow([(544, 560), (600, 560), (600, 235), (661, 235)])
    s.node(880, 400, 430, 84, "agent", t["edit"])
    s.arrow([(880, 287), (880, 356)])
    s.node(880, 548, 430, 104, "tool", t["refresh"], tools=["svg_preview.py"])
    s.arrow([(880, 444), (880, 494)])
    s.node(880, 700, 430, 80, "you", t["again"])
    s.arrow([(880, 600), (880, 658)])
    s.arrow([(880, 742), (880, 850), (90, 850), (90, 235), (116, 235)], color="#4a76c9")
    s.legend(1190, 120, legend_items(t), t["legend"])
    return s.svg(t["qe"], title_x=600)


DIAGRAMS = {"flow": flow, "render": render_paths, "quick-edit": quick_edit}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "docs" / "images"))
    ap.add_argument("--svg-only", action="store_true", help="write SVGs to dist/diagrams/ without rendering")
    ap.add_argument("--scale", type=float, default=1.5)
    a = ap.parse_args()
    from _svgcommon import render_svg_bytes
    out = Path(a.out)
    svg_dir = ROOT / "dist" / "diagrams"
    svg_dir.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    for lang, texts in T.items():
        for name, draw in DIAGRAMS.items():
            svg = draw(texts)
            (svg_dir / f"diagram-{name}.{lang}.svg").write_text(svg, encoding="utf-8")
            if a.svg_only:
                continue
            png = out / f"diagram-{name}.{lang}.png"
            render_svg_bytes(svg.encode("utf-8"), png, scale=a.scale, renderers=["playwright"])
            print(f"wrote {png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
