# Static HTML/CSS design route

Use for web UI: anything that will ship as HTML/CSS, including forms, long text and responsive
pages. It has the same loop as the SVG route (preview, Quick Edit, manifest, tokens, per-component
visual diff) with HTML-specific commands. Reuse the project's design system before adding one.
Inspection needs Python, Playwright and a Chromium-based browser; authoring needs no npm or server.

## Author and compare

Copy `templates/html-design/` to a design folder such as `design/html/`, keeping `review.html`
beside `theme.css`. The draft opens directly in a browser (`file://`). Use no scripts, remote
fonts, CDNs or libraries; scripts are stripped from previews and disabled during inspection. Use
local resources and shared CSS variables; Grid/Flex handle layout and inline SVG handles graphics.
Repeated markup can be generated from TSX (`component-authoring.md`); never edit generated output.

Each independently reviewed UI is a screen: an element with a unique PascalCase `id`, a
`data-screen` name and a `data-state`. Screens cannot nest. Give components `data-component="Kind"`
and a unique PascalCase `id`, and keep ids stable across revisions. All ids in one document must be
unique, so prefix repeated instances with their state. Hidden components are left out of reports.

Show the states a decision depends on as separate screens side by side, stacking them at narrow
widths. Keep headings, rationale and captions outside `[data-screen]`; text inside a screen reads
as real UI copy. Do not implement navigation, events or network requests to demonstrate a state.
Write real copy, including realistic long strings.

## Preview and Quick Edit

```text
python <skill>/scripts/svg_preview.py design/html --serve     # local: live page, tell the user the URL
python <skill>/scripts/svg_preview.py design/html --no-open   # sandbox: static page to publish
```

The preview shows each screen in its own card, rendered from the draft's HTML and local CSS with
scripts removed. The 寬度 select sets the viewport width (1280, 768, 390, or the card width), so
media queries apply and text reflows. Selection, Alt-drag regions, the breadcrumb and the Quick Edit
panel work as on the SVG route. A request references `file.html#Id?state=…&width=…`; region
coordinates are CSS pixels relative to the screen. Handle it as SKILL.md describes: run
`svg_render.py --job` first and read the PNG, which renders the same screen at the same width.

## Inspect before asking for review

```text
python <skill>/scripts/html_review.py design/html/review.html --size 1280x800 --out shots/html-desktop
python <skill>/scripts/html_review.py design/html/review.html --size 390x844 --out shots/html-mobile
```

Use a separate output folder for each viewport and revision. The tool opens the local file with
page JavaScript disabled, blocks external requests, and checks screen and component ids, static
content, failed resources and basic overflow. Exit codes: 0 = structural PASS, 1 = draft issues,
2 = invalid input or capture failure. It is a local authoring helper, not a sandbox for untrusted
files.

On PASS it writes, per screen, a PNG and `<id>.components.json`, plus `report.json`. On FAIL it
writes only the report. Use only files listed in the current successful report; older files may
remain. Boxes are CSS pixels relative to each screen's top-left at DPR 1.

Read every PNG and fix clipped text, awkward wrapping, alignment and spacing before sharing.
Overflow checks are heuristics: they also flag intentional scrolling and cannot prove there are no
overlaps or clipped text. Record intentional exceptions and inspect them by eye; never call a
failing report PASS.

## Tokens

```text
python <skill>/scripts/tokens_export.py design/html/review.html --format ts -o src/theme/tokens.ts
```

It reads the CSS variables from the draft's local stylesheets and `<style>` blocks; a `.css` file
works as input too.

## Verify an implementation

Capture the approved baseline with each screen alone at the target viewport width, which is what an
implementation screenshot shows:

```text
python <skill>/scripts/html_review.py design/html/review.html --size 1280x800 --out shots/baseline-1280 --standalone
```

Screenshot the implementation at the same width and crop it to the screen (`screenshot_web.py`
for web pages), then compare:

```text
python <skill>/scripts/visual_diff.py shots/baseline-1280/SettingsDefault.png shots/app-settings.png --manifest shots/baseline-1280/SettingsDefault.components.json
```

The same thresholds apply as on the SVG route: overall ≤ 2 % and no component over 10 %. Content,
state and fonts must match the baseline; dynamic data in the implementation shows up as a mismatch.

## What each route offers

| | SVG route | HTML route |
|---|---|---|
| Preview and Quick Edit | `svg_preview.py` | `svg_preview.py`, plus the 寬度 select |
| Reproduce a Quick Edit view | `svg_render.py --job` | `svg_render.py --job` (`format: html`) |
| Draft checks | `svg_lint.py` | `html_review.py` |
| Component manifest | `svg_manifest.py` | `html_review.py` (`<id>.components.json`) |
| Token export | `tokens_export.py` on the SVG | `tokens_export.py` on the HTML or CSS |
| Per-component visual diff | `visual_diff.py design.svg …` | `visual_diff.py baseline.png …` with the manifest |
| State layers in one file | `data-state` layers | one screen per state |
