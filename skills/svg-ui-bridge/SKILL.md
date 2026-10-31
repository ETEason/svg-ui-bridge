---
name: svg-ui-bridge
description: Use for any work that changes what a user sees — new screens, UI components, layout or styling changes, game HUD/menus, sprite/asset layouts — in any stack (web, Rust egui/iced/Bevy, Qt, game engines). Designs the UI as a structured SVG spec first, gets the human's approval on the rendered image, decomposes it into a component manifest, implements per component, and proves fidelity with a visual diff. Use during brainstorming/design, not only at implementation time.
---

# svg-ui-bridge

SVG is the shared language between the human's visual intent and the agent's code: the human
judges a rendered picture, the agent reads named, layered, tokenised markup. Iterate on the
picture, not on the code.

Scripts live in `scripts/` next to this file (Python 3 + Pillow, plus one SVG renderer: resvg,
rsvg-convert, Playwright with the system Chrome/Edge or cairosvg). Refer to them as `<skill>/scripts/…`.

## When this applies

- Applies: anything with a visual outcome, including small tweaks ("move the button", "darker card").
- Skip: pure logic/back-end changes, copy-only text edits, or when the user says "no mockup".
- Inside superpowers: this runs **inside brainstorming's design step** and shapes the spec, the
  plan tasks and the verification evidence. It does not replace any superpowers stage. See
  `references/workflow-integration.md` (read it when superpowers or pstack skills are active).

## The loop

### 1. Draft the SVG (design phase — no product code yet)

- Read `references/svg-conventions.md` before writing the first SVG of a session.
- Write `design/<screen>.svg` (or the folder the project CLAUDE.md names). If the project has
  existing screens/tokens, reuse their tokens and copy the existing look; if the user gave a
  screenshot or sketch, trace its structure.
- Every component is a `<g id="PascalCase" data-component="Kind">`; children flow per `data-layout`;
  variants are `data-state` layers; colours/spacing are CSS variables in `<style>`.

### 2. Lint + preview + human gate

```
python <skill>/scripts/svg_lint.py design/<screen>.svg
python <skill>/scripts/svg_preview.py design --serve        # human: live browser review page
python <skill>/scripts/svg_render.py design/<screen>.svg     # agent: PNG to look at with Read
```

- Fix every ERROR; fix warnings unless there is a stated reason.
- **The human reviews in the browser**, not the XML and not a PNG: `svg_preview.py --serve` opens
  a page at http://localhost:8765 that reloads by itself whenever an SVG in `design/` changes, with a
  state switcher (default/hover/disabled…), hover-to-identify components (id, layout, note) and zoom.
  Start it once in the background at the beginning of design work and tell the user the URL.
  Without a long-running process: `svg_preview.py design` writes `design/_preview.html` and opens it.
- **The agent checks its own drawing** by rendering a PNG and reading it (look for overlaps,
  clipped text, misalignment) before asking the user to look. `--all-states` renders each state.
- Ask for feedback in visual terms. Apply it to the SVG → re-lint → (preview refreshes) → repeat.
- **Gate:** no product code until the user approves the design (this is the design approval in
  superpowers terms).

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
  (use the project's verify skill if one exists, else Playwright / the browser tools / the
  engine's screenshot facility).
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

Visual change requests go to the SVG first (step 1 → 5 for the touched components). The SVG stays
the source of truth; if code and SVG disagree, either fix the code or get the user to approve an
SVG update — never let them drift silently.

## Red flags

| thought | instead |
|---|---|
| "It's a small UI tweak, I'll just change the CSS" | Edit the component's `<g>`, render, get a nod. Two minutes. |
| "I'll describe the layout in words" | Draw it. Words are exactly what this skill replaces. |
| "Paste the full SVG into each subagent" | Manifest row + isolated render only. |
| "Looks right to me" | Run visual_diff; report the numbers. |
| "Overall mismatch is only 1.8 %, ship it" | Check the per-component list; one component over the limit is a FAIL. |
| Show the user raw SVG markup | Show the live preview page (or a PNG if no browser). |
| "The SVG is outdated, the code is the truth now" | Update the SVG and get approval, or fix the code. |
| Exported Figma/Illustrator SVG with thousands of path points | Redraw as primitives with ids, or ask the user to export with layers/ids preserved. |
