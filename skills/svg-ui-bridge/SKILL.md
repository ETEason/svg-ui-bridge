---
name: svg-ui-bridge
description: Use for any change to what a user sees, such as screens, components, layout, styling or game HUDs, in any stack. Drafts it as SVG or HTML/CSS for approval first, then verifies the build.
---

# svg-ui-bridge

Version: 0.5.0

A rendered draft is the shared language between the human's visual intent and the agent's code:
the human judges a picture, the agent reads named, layered, tokenised markup. Iterate on the
picture, not on the code. Drafts are structured SVG or static HTML/CSS; both get the same loop.

`<skill>` below means the folder that contains this SKILL.md. Work it out from where this file was
loaded, because it differs per install. Scripts live in `<skill>/scripts/` (Python 3 + Pillow, plus
one SVG renderer: resvg, rsvg-convert, Playwright with the system Chrome/Edge or cairosvg).

## When this applies

- Applies: anything with a visual outcome, including small tweaks ("move the button", "darker card").
- Skip: pure logic/back-end changes, copy-only text edits, or when the user says "no mockup".
- Inside superpowers: this runs **inside brainstorming's design step** and shapes the spec, the
  plan tasks and the verification evidence. It does not replace any superpowers stage. See
  `references/workflow-integration.md` (read it when superpowers or pstack skills are active).
  Both are optional: when they are absent, follow the steps below without mentioning them.

## Choose the format

Use the format the project or the user already chose. Otherwise one rule decides:

- **Web UI** (it will ship as HTML/CSS): an HTML/CSS draft. Follow `references/html-design.md`
  for its commands; the loop and rules below are the same.
- **Anything else** (native apps, games and HUDs, diagrams, fixed-coordinate graphics): SVG, as below.

When many components repeat, they can be generated from TSX with a shared theme; see
`references/component-authoring.md`. Small drafts are written by hand.

## Step 0: find out where you are

```
python <skill>/scripts/env_check.py
```

The last line is `MODE=local` or `MODE=sandbox`. Read `references/environments.md` when the mode is
`sandbox` or when a tool is missing.

| step | `MODE=local` | `MODE=sandbox` |
|---|---|---|
| Preview | `svg_preview.py design --serve`, tell the user the URL | Regenerate the static `_preview.html` after every SVG edit; publish it as an artifact or send the file |
| Verify | Screenshot the app on the user's computer | Web: `screenshot_web.py` on a page started in the sandbox. Native or game: ask the user to upload a screenshot at the stated size |

These rules hold equally in both modes and both formats:

- **Approval gate:** no product code until the user has seen the design and approved it.
- **Scope:** a design-only request ends with inspected drafts and the user's review. Go on to
  decomposition, implementation and screenshot verification only when implementation is asked for.
  An approval stays valid for the scope it was given.
- **Implementation evidence:** an implementation is not visually verified until `visual_diff.py` has
  passed on a real screenshot (for HTML against the `html_review.py --standalone` baseline). If no
  screenshot can be had, say that the visual check is still open. Never call a draft verified.

## The loop

### 1. Draft the SVG (design phase — no product code yet)

- Read `references/svg-conventions.md` before writing the first SVG of a session.
- Write or generate `design/<screen>.svg` (or the folder the project CLAUDE.md names). If it is
  generated from TSX, edit the source and rebuild; never patch the output. If the project has
  existing screens/tokens, reuse their tokens and copy the existing look; if the user gave a
  screenshot or sketch, trace its structure.
- Every component is a `<g id="PascalCase" data-component="Kind">`; children flow per `data-layout`;
  variants are `data-state` layers; colours/spacing are CSS variables in `<style>`.

### 2. Lint + preview + human gate

```
python <skill>/scripts/svg_lint.py design/<screen>.svg
python <skill>/scripts/svg_preview.py design --serve        # human: live browser review page (local)
python <skill>/scripts/svg_preview.py design --no-open       # human: static page to publish (sandbox)
python <skill>/scripts/svg_render.py design/<screen>.svg     # agent: PNG to look at with Read
```

- Rebuild generated SVG after every source edit, before these commands.
- Show the states or options a decision depends on as separate SVGs at the same size, so the
  preview shows them side by side. Keep captions outside the UI, and record which file, state and
  size were approved. The state switcher is for inspection, not the only way to find alternatives.
- Fix every ERROR; fix warnings unless there is a stated reason.
- **The human reviews in the browser**, not the XML and not a PNG: `svg_preview.py --serve` opens
  a page at http://localhost:8765 that reloads by itself whenever an SVG in `design/` changes, with a
  state switcher (default/hover/disabled…), hover-to-identify components (id, layout, note) and zoom.
  Start it once in the background at the beginning of design work and tell the user the URL.
  Without a long-running process: `svg_preview.py design` writes `design/_preview.html` and opens it.
- **The agent checks its own drawing** by rendering a PNG and reading it (look for overlaps,
  clipped text, misalignment) before asking the user to look. `--all-states` renders each state.
- Ask for feedback in visual terms. Apply it to the SVG or its source (then rebuild) → re-lint →
  (preview refreshes) → repeat.
- Tell the user they can click components in the preview, write a change in Quick Edit and copy it
  to you. The panel sits at the bottom of the window, so nothing in the design is compressed.
- When a message contains `Snapshot JSON (svg_render.py --job)` and a `.svg#` reference: first run
  `python <skill>/scripts/svg_render.py --job '<json>'` and read the PNG to confirm you see what the
  user saw, then find each component or region from its reference and follow this loop. The syntax
  is in `references/svg-conventions.md`.
- With `--serve`, the "送給 Agent" button writes to `design/_feedback.md`. During review, read new
  entries in that file before each reply. Mark handled entries `[done]`; do not delete them.
- **Gate:** no product code until the user approves the design (this is the design approval in
  superpowers terms). For a design-only request, the work ends here.

### 3. Decompose

```
python <skill>/scripts/svg_manifest.py design/<screen>.svg
```

Produces `<screen>.components.md/.json`: component tree, measured bboxes, tokens, states,
notes, and a leaves-first build order. Put a "Visual design" section in the spec that links the
SVG, the manifest, and the acceptance threshold (default: overall ≤ 2 %, no component > 10 %).

If the manifest shows a component without clear layout, states or behaviour, that is a design
gap: ask, then fix the SVG — the visual spec forces those decisions before code exists.

### 4. Plan + implement per component

- Map SVG → code with the project CLAUDE.md mapping, else `references/framework-mapping.md`.
- Generate the token/theme file from the SVG, never hand-copy colours:
  `python <skill>/scripts/tokens_export.py design/<screen>.svg --format css|ts|egui|bevy|json -o <file>`
- One plan task per component (leaves first), then one assembly task per screen.
- Give each implementer (or subagent) only: its manifest row, `svg_render.py --component <Id>`
  PNG, and the `<g>` subtree if needed. Do not paste the whole SVG into every prompt.

### 5. Verify visually

- Screenshot the running implementation at the SVG's `data-target` size, cropped to the canvas
  (use the project's verify skill if one exists, else `screenshot_web.py` for web pages, or the
  browser tools / the engine's screenshot facility). See Step 0 for what each mode can reach.
- Run:
  ```
  python <skill>/scripts/visual_diff.py design/<screen>.svg shots/<screen>.png --manifest design/<screen>.components.json [--scale <dpr>]
  ```
  For web apps set `SVG_UI_RENDERER=playwright` so the reference is rendered by the same engine
  as the app (far less text noise). PASS requires overall ≤ `--max` **and** every component
  ≤ `--max-component`; a wrong button is <1 % of a screen but ~40 % of the button, so never judge
  by the overall number alone.
- PASS → report the numbers and the diff image path as evidence. FAIL → open the diff image
  (design | implementation | heat-map), fix the components listed over the limit, re-run. To find
  an offset, compare the component's manifest bbox with the element's real box (e.g. via the
  browser's getBoundingClientRect). Residual text anti-aliasing is expected; don't chase it below
  the threshold.

### 6. Later changes

Visual change requests go to the design first (step 1 → 5 for the touched components). For
generated SVG, edit the TSX, theme or data and rebuild every affected view. The approved SVG is the
visual baseline; if code and SVG disagree, either fix the code or get the user to approve an SVG
update — never let them drift silently.

## Red flags

| thought | instead |
|---|---|
| "It's a small UI tweak, I'll just change the CSS" | Edit the component's `<g>` (or its source, then rebuild), render, get a nod. |
| "The user only wanted a design, but I'll start the app too" | Stop at the reviewed draft until implementation is asked for. |
| "I'll describe the layout in words" | Draw it. Words are exactly what this skill replaces. |
| "Paste the full SVG into each subagent" | Manifest row + isolated render only. |
| "Looks right to me" | Run visual_diff; report the numbers. |
| "Overall mismatch is only 1.8 %, ship it" | Check the per-component list; one component over the limit is a FAIL. |
| Show the user raw SVG markup | Show the live preview, or in a sandbox the static page. |
| "`--serve` is running in the sandbox, the user can open it" | They cannot reach it. Publish the static page. |
| "The SVG is outdated, the code is the truth now" | Update the SVG and get approval, or fix the code. |
| Exported Figma/Illustrator SVG with thousands of path points | Redraw as primitives with ids, or ask the user to export with layers/ids preserved. |
