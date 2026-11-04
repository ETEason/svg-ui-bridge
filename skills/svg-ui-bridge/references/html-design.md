# Static HTML/CSS design route

Use for flowing text, forms and responsive layouts. This route replaces the SVG-specific loop;
do not pass HTML into `svg_lint.py`, `svg_manifest.py`, `svg_preview.py` or `visual_diff.py`.
It needs Python + Playwright and a supported Chromium browser for inspection, but no npm or server
for authoring or opening the bundled draft. Reuse the project's design system before adding one.

## Author and compare

Copy `templates/html-design/` to a design folder, keeping `review.html` beside `theme.css`.
Open the HTML directly in a browser (`file://`). In a sandbox deliver the folder/zip or an artifact
with its CSS; sending only the HTML loses styling. The template deliberately uses no scripts,
remote fonts, CDNs or libraries. Use local resources and shared CSS variables; Grid/Flex handle
layout while inline SVG handles graphics. Repeated markup can use an existing template system
when useful; JSX is optional, and generated HTML remains static. Do not edit generated output.

Each independently captured UI has a unique PascalCase `id`, `data-screen` name and `data-state`.
Screen roots cannot nest. Put `data-component="Kind"` and a unique PascalCase `id` on components;
keep ids stable across revisions. Within one HTML document all ids must be unique, so use state
prefixes for repeated instances. Hidden components are omitted from the geometry report.

Show decision-relevant states side by side, stacking them at narrow widths. Keep headings,
rationale and captions outside `[data-screen]`; text inside a screen reads as actual UI copy.
Do not implement navigation, events or network requests to demonstrate a state. Write real copy,
including realistic long strings. Use consistent tokens and component classes across variants.

## Inspect before asking for review

From the consuming project's root (replace `<skill>` with this skill's installed folder):

```text
python <skill>/scripts/html_review.py design/html/review.html --size 1280x800 --out shots/html-desktop
python <skill>/scripts/html_review.py design/html/review.html --size 390x844 --out shots/html-mobile
```

Use a separate output folder for each viewport/revision. The tool opens a local file with page
JavaScript disabled, blocks external requests, and checks screen/component identifiers, static
content, failed resources and basic overflow. Exit codes: 0 = structural PASS, 1 = draft issues,
2 = invalid input or capture failure. It is a local authoring helper, not an untrusted-file sandbox.

On PASS it writes one PNG per screen and `report.json`. On FAIL it writes the report without new
PNGs. Only use screenshots listed in the current successful report; old files may still exist.
The report records browser viewport, actual screen size, and visible component boxes in CSS pixels
relative to each screen's top-left, at DPR 1. PNG edges round fractional CSS coordinates to pixels.
A comparison sheet's screen is narrower than its browser viewport. For a full app-viewport
baseline, use a standalone screen with no review margins.
Never compare a whole review page against a cropped product screenshot.

Read all PNGs and fix clipped text, awkward wrapping, alignment and spacing before sharing.
Overflow checks are heuristics: they also flag intentional scrolling, and cannot prove there are
no overlaps or clipped text. Record any intentional exception and inspect it manually; do not
call a failing report PASS. For scrollable UI, capture and label the relevant visible states.
No automated accessibility or production visual-fidelity certification is provided by this check.

## Review and handoff

Share the rendered review page and ask about appearance. Address feedback using `file.html#Id`,
state and viewport; edit source/theme, rerun all affected captures and inspect the results. The SVG
Quick Edit selection panel and snapshot-job syntax are not supported for HTML in this version.

Record approved source revision, file, screen id/state, viewport, actual screen dimensions and PNG.
Commit HTML/CSS and local assets (or source/build configuration when generated); keep captures in
the project's evidence location. Design-only tasks finish here, without creating a product app.

If implementation is requested, hand off relevant component geometry and crops, shared CSS tokens,
behaviour notes and approved screenshots. `report.json` is an HTML review report, not the SVG
component-manifest schema or a build-order plan. It must not be fed into the SVG diff pipeline.
Use the target project's browser screenshot comparison tooling at matching sizes, content and
states. If unavailable, report manual comparison and the missing automated evidence explicitly;
do not claim this route provides the SVG route's 2% / 10% automated acceptance checks.

## Capabilities in this version

| Capability | SVG route | HTML route |
|---|---|---|
| Static review and rendered screenshots | Existing preview/render | Local HTML and `html_review.py` |
| Component identification | SVG groups and manifest | DOM ids and measured report |
| Quick Edit and snapshot jobs | Supported | Not supported |
| Token export | `tokens_export.py` | Maintain shared CSS variables directly |
| Automated implementation pixel diff | `visual_diff.py` | Use project tooling; not built in |

Optional workflow integrations must use this capability boundary as well: link HTML, reports and
approved PNGs in a design spec; do not require an SVG manifest or SVG diff for an HTML draft.
