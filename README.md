# svg-ui-bridge

[繁體中文](README.zh-TW.md)

SVG-first UI workflow for Claude Code. The agent designs every screen as a structured SVG spec,
you review it live in the browser, the SVG is decomposed into a component manifest, and the
implementation is proven against the design with a per-component visual diff.

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

## After installing

1. Append `skills/svg-ui-bridge/templates/global-CLAUDE.md.snippet` to `~/.claude/CLAUDE.md`.
2. Per UI project: paste `templates/project-CLAUDE.md.template` into the project's `CLAUDE.md` and fill
   it in; add `templates/gitignore.snippet` to `.gitignore`.
3. Check the toolchain: `python tests/smoke_test.py` (from a clone) should end with `ALL SMOKE TESTS PASSED`.

## What's inside

| path | purpose |
|---|---|
| `skills/svg-ui-bridge/SKILL.md` | the workflow the agent follows (6 steps, gates, red flags) |
| `references/` | SVG conventions, superpowers/pstack integration, SVG → framework mapping |
| `scripts/svg_lint.py` | checks an SVG against the conventions |
| `scripts/svg_preview.py` | browser review page; `--serve` live-reloads on every SVG change (localhost only) |
| `scripts/svg_render.py` | PNG renders for the agent (all states / one component) |
| `scripts/svg_manifest.py` | component tree, measured bboxes, tokens, states, build order |
| `scripts/tokens_export.py` | design tokens → CSS / TS / egui / Bevy / JSON |
| `scripts/visual_diff.py` | screenshot vs design: overall and per-component mismatch, diff image, exit code |
| `scripts/lint_hook.py` | optional PostToolUse hook that lints SVGs the agent writes |

## Security notes

- The scripts only read and write local files. `svg_preview.py --serve` binds to `127.0.0.1` only.
  Nothing is downloaded or uploaded at run time.
- The plugin ships **no hooks, MCP servers or binaries**; the lint hook is opt-in (see
  `skills/svg-ui-bridge/references/workflow-integration.md`).
- Review the code before installing any skill, including this one, and pin a tag if you want
  updates only when you choose.

## License

MIT
