# Environments: local and sandbox

The same skill runs in two places. `scripts/env_check.py` prints which one this is on its last
line, `MODE=local` or `MODE=sandbox`. `SVG_UI_MODE=local|sandbox` overrides the detection; the user
may set it when the detection is wrong, for example on a Linux machine reached over SSH with
port forwarding.

| | `MODE=local` | `MODE=sandbox` |
|---|---|---|
| Where | The user's computer: terminal, VS Code, desktop app's Claude Code tab | Cloud sandbox of a desktop app or claude.ai conversation, or any Linux without a display |
| Skill name | `/svg-ui-bridge:svg-ui-bridge` as a plugin | `svg-ui-bridge` as an uploaded skill |
| Human review | `svg_preview.py design --serve`, give the user the URL | Static page, published or sent |
| Verification | Screenshot the app running on the user's computer | Web: a page started in the sandbox. Native: a screenshot the user uploads |
| superpowers, pstack | Use them when present | Normally absent |

## Preview

**local:** follow SKILL.md step 2. Start the server once in the background and tell the user the URL.

**sandbox:** localhost does not connect the user and the sandbox in either direction, and no
browser can open here, so a live server shows nobody anything.

1. Run `python <skill>/scripts/svg_preview.py design --no-open`. It writes `design/_preview.html`.
2. Fix any `warn:` line it prints. A referenced file cannot load inside a static page, so inline
   the asset or draw it as primitives.
3. Publish the page as an artifact when artifacts are available. Otherwise send the file.
4. After every SVG edit, regenerate the page and update the same artifact, or send the file again,
   so the user never reviews a stale design.

`--serve` in sandbox mode prints a notice, writes the same static page and exits. HTML drafts in the
folder are included with their local CSS inlined, so the static page still needs no other files.

Quick Edit works inside an artifact as well. If the iframe blocks the clipboard, the panel shows the
full text for the user to copy by hand. Artifact comments stay available. The "送給 Agent" button
needs `--serve`, so it does not appear on a static page.

The user's approval is what passes the gate, in the same way as in local mode. Do not write product
code until they have seen the page and approved it.

## Verification

Both modes need `visual_diff.py` output before anything is called done. The only difference is
where the screenshot comes from.

**local:** screenshot the running app. For web apps:

```
python <skill>/scripts/screenshot_web.py http://localhost:5173/settings -o shots/settings.png --size 1280x800
```

**sandbox, web projects:** start the app in the sandbox, or build it to HTML, and screenshot that.
The user's own running app cannot be reached from here.

```
python <skill>/scripts/screenshot_web.py build/index.html -o shots/settings.png --size 1280x800
```

**sandbox, native apps and games:** the sandbox cannot run them with a screen. Tell the user the
exact size to capture, taken from the SVG's `data-target` and canvas, and which screen and state to
show. Run `visual_diff.py` on the file they upload. If they cannot provide one, report that the
visual check is still open. An unverified implementation is not done.

`screenshot_web.py` blocks requests to other origins and lists them as `blocked …`. If a listed
resource matters to the look of the page, such as a web font, serve it from the same origin or the
diff will show it as missing.

Prefer `screenshot_web.py` for web pages. It turns LCD text off to match how the design reference is
rendered. Other screenshot tools leave it on, and the colour fringes can push a small text
component over the limit.

## Missing tools

`env_check.py` tests each renderer by rendering a small SVG. If none works:

1. Try `python -m pip install pillow playwright`, then run `env_check.py` again. In a sandbox this
   only works when package installs are allowed.
2. Playwright needs a browser. It uses Chrome or Edge when present. Otherwise run
   `python -m playwright install chromium`, if downloads are allowed.
3. If rendering stays impossible, these still work: `svg_lint.py`, `svg_preview.py`,
   `tokens_export.py`, and `svg_manifest.py --no-bbox`. Without a renderer the agent cannot look at
   its own drawing and `visual_diff.py` cannot run on an SVG, so tell the user which step is blocked.

## Companion skills

superpowers and pstack are optional. Their guidance in `workflow-integration.md` applies only when
they appear among the available skills. When they are absent, follow the six steps in SKILL.md on
their own. Do not report an error and do not suggest installing them.
