# svg-ui-bridge

[繁體中文](README.zh-TW.md)

Design-first UI workflow for Claude Code. The agent drafts every screen as static HTML/CSS (web UI)
or a structured SVG spec (everything else), and you review it in the browser. A
design-only request ends there. When you ask for implementation, the SVG is decomposed into a
component manifest and the build is proven against the design with a per-component visual diff.

Works for web and non-web UIs (React, Rust egui/iced/Bevy, Qt, game HUDs) and slots into
[superpowers](https://github.com/obra/superpowers) (inside brainstorming's design step) and
pstack (`create-verification-skill` provides the screenshots).

## Install

**Claude Code plugin (recommended)** — one command in your shell:

```
claude plugin install svg-ui-bridge --marketplace ETEason/svg-ui-bridge
```

or the two-step form (older Claude Code versions), in a shell or inside a session with `/plugin …`:

```
claude plugin marketplace add ETEason/svg-ui-bridge
claude plugin install svg-ui-bridge@svg-ui-bridge
```

Pin a release: `claude plugin marketplace add ETEason/svg-ui-bridge#v0.1.0`.
Update later: `claude plugin update svg-ui-bridge@svg-ui-bridge`.

**For everyone working in one repository** (also covers teammates): run once in that repo, then commit
`.claude/settings.json`:

```
claude plugin marketplace add ETEason/svg-ui-bridge --scope project
```

**Agent Skills CLI** (other agents / no plugin system):

```
npx skills add ETEason/svg-ui-bridge
```

**Manual**: copy `skills/svg-ui-bridge/` into `<project>/.claude/skills/` (travels with the repo, also
works in cloud sessions) or `~/.claude/skills/` (this machine only). Install it one way only.

As a plugin the skill is invoked as `/svg-ui-bridge:svg-ui-bridge`; Claude also loads it on its own
for UI work.

## Quick Edit in the preview page

Point at the design instead of describing it. A panel opens at the bottom of the window, and the
page reserves its height so the design keeps its size and can scroll clear of the panel.

| action | how |
|---|---|
| Select a component | click it; the deepest component under the pointer is chosen |
| Select several | Shift or Ctrl + click |
| Widen the selection | click a level in the breadcrumb, such as `App › SearchBar › SearchButton` |
| Mark an empty area | hold Alt and drag |
| Queue several requests | write one, press 加入清單, select the next |
| Copy for the agent | Copy Prompt, or Ctrl/Cmd + Enter |
| Collapse the panel | click its top handle; Esc closes it |

Paste the copied text to the agent. It renders what you saw with `svg_render.py --job`, confirms the
position, then edits the SVG. If the clipboard is blocked, the panel shows the text for you to copy
by hand. With `--serve`, 送給 Agent writes the request to `design/_feedback.md` instead. Prompts use
relative paths unless you pass `--absolute-paths`.

## Choose a format

One rule, unless the project already chose: **web UI is drafted in HTML/CSS, everything else in SVG**
(native apps, games and HUDs, diagrams). Both get live preview, Quick Edit, a component manifest,
token export and a per-component visual diff. HTML drafts reflow at the width you pick in the preview,
so a responsive page is one file instead of one SVG per breakpoint.
See [html-design.md](skills/svg-ui-bridge/references/html-design.md).

For repeated components or many variants, write TSX components with a shared theme and generate the
design at build time. [examples/tsx-design](examples/tsx-design) has a pinned, type-checked example;
see [component-authoring.md](skills/svg-ui-bridge/references/component-authoring.md).

## Use in the desktop app or claude.ai

Ordinary conversations and cloud tasks run in a sandbox, so they need the skill uploaded to your
account:

1. Download [svg-ui-bridge-skill.zip](https://github.com/ETEason/svg-ui-bridge/releases/latest/download/svg-ui-bridge-skill.zip)
   from the latest release.
2. Open **Customize > Skills** ([claude.ai/customize/skills](https://claude.ai/customize/skills)),
   upload the zip, and turn the skill on.
3. Ask "which version of svg-ui-bridge did you load?" to confirm. The answer is the `Version:` line
   in `SKILL.md`.

To update, download the newest zip and upload it again. The skill detects where it runs with
`scripts/env_check.py`:

| | Claude Code on your computer (`MODE=local`) | Sandbox (`MODE=sandbox`) |
|---|---|---|
| Skill name | `/svg-ui-bridge:svg-ui-bridge` | `svg-ui-bridge` |
| Review | Live page at `localhost:8765` | Static page, published as an artifact or sent as a file |
| Verify | Screenshot your running app | Web: a page started in the sandbox. Native or games: a screenshot you upload |
| superpowers, pstack | Used when installed | Not needed |

The approval gate and the visual diff evidence are equally strict in both.
Details: [environments.md](skills/svg-ui-bridge/references/environments.md).

## Requirements

Python 3.10+, Pillow, and one SVG rasteriser (tried in this order: resvg, rsvg-convert, Playwright,
cairosvg). Easiest everywhere:

```
python -m pip install pillow playwright
```

Playwright uses the system Chrome or Edge, so no browser download is needed. Only if neither is
installed, add `python -m playwright install chromium`.

(Windows: `py -m pip …`.) For web projects set `SVG_UI_RENDERER=playwright` so the reference image is
rendered by the same engine as your app.

The TSX example also needs Node.js and npm; nothing else does.

## After installing

1. Append `skills/svg-ui-bridge/templates/global-CLAUDE.md.snippet` to `~/.claude/CLAUDE.md`.
2. Per UI project: paste `templates/project-CLAUDE.md.template` into the project's `CLAUDE.md` and fill
   it in; add `templates/gitignore.snippet` to `.gitignore`.
3. Check the toolchain: `python tests/smoke_test.py` (from a clone) should end with `ALL SMOKE TESTS PASSED`.

## What's inside

| path | purpose |
|---|---|
| `skills/svg-ui-bridge/SKILL.md` | the workflow the agent follows (6 steps, gates, red flags) |
| `references/` | SVG conventions, HTML route, component authoring, environments, superpowers/pstack integration, SVG → framework mapping |
| `scripts/env_check.py` | reports the OS, Python, Pillow, working renderers and `MODE=local` or `MODE=sandbox` |
| `scripts/svg_lint.py` | checks an SVG against the conventions |
| `scripts/svg_preview.py` | browser review page; `--serve` live-reloads on every SVG change (localhost only) |
| `scripts/svg_render.py` | PNG renders for the agent (all states / one component) |
| `scripts/svg_manifest.py` | component tree, measured bboxes, tokens, states, build order |
| `scripts/tokens_export.py` | design tokens → CSS / TS / egui / Bevy / JSON |
| `scripts/screenshot_web.py` | screenshots a URL or HTML file for `visual_diff.py` |
| `scripts/visual_diff.py` | screenshot vs design: overall and per-component mismatch, diff image, exit code |
| `scripts/html_review.py` | HTML drafts: screen PNGs, component manifests, id, resource and overflow checks; `--standalone` baseline |
| `templates/html-design/` | offline HTML/CSS draft with two states |
| `examples/tsx-design/` | TSX components generating SVG; not part of the installed skill |
| `scripts/lint_hook.py` | optional PostToolUse hook that lints SVGs the agent writes |
| `tools/build_skill_zip.py` | validates `SKILL.md` and builds the upload zip |

## Security notes

- The scripts only read and write local files. `svg_preview.py --serve` binds to `127.0.0.1` only.
  Nothing is downloaded or uploaded at run time. `screenshot_web.py` opens only the URL or file you
  name and blocks requests to other origins.
- Do not open SVGs from untrusted sources in the preview page: their content goes into the page
  as is, so a malicious SVG could run scripts or reach external URLs there.
- The plugin ships **no hooks, MCP servers or binaries**; the lint hook is opt-in (see
  `skills/svg-ui-bridge/references/workflow-integration.md`).
- Review the code before installing any skill, including this one, and pin a tag if you want
  updates only when you choose.

## License

MIT
