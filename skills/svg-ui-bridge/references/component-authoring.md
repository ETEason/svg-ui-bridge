# Component authoring and static review

Read this when repeated components, multiple screen variants, or state comparisons make raw SVG
expensive to maintain. SVG remains the tool interchange format; it need not be the authoring format.

## Choose the smallest useful authoring layer

- Edit a small existing SVG directly when extraction would add more work than it removes.
- For repeated cards, rows, controls or screen variants, prefer TSX functions and typed props.
  Reuse the project's design build if available. JSX is a build-time template language here;
  it does not require a React app, hydration, event handlers, or a development server.
- Keep shared colours, fonts and dimensions in one theme module; use data arrays for repetition.
  Pass an explicit stable instance id to each component. Preserve the SVG conventions in output,
  including `data-component`, `data-layout`, tokens, target size, and state layers.
- SVG itself has reuse mechanisms such as `defs`/`use`, but those do not replace typed component
  composition. Emit inspectable `<g>` instances for UI components so manifests and Quick Edit
  can identify each instance independently.

Suggested project layout (adapt to existing paths):

```text
design/system/components/    shared TSX design components
design/system/theme.ts       shared design tokens
design/system/pages/         screen templates and explicit variants
design/system/build.tsx      static export entrypoint
design/*.svg                generated tool inputs and review artifacts
```

The optional `templates/tsx-design/` starter demonstrates two static screen states from one
component. Copy that folder to `design/system`, run `npm install` there once, then `npm run build`.
It needs Node.js and npm only for authoring; the existing Python workflow remains available
without them. Commit the resulting lockfile in the consuming project. The starter has no watcher:
rebuild after every source edit, before previewing, linting, manifest generation or token export.

## One editable source, reproducible output

Record the source path and build command in the project's instructions. Edit TSX/theme/data,
then rebuild SVG; never patch generated SVG as a lasting change. Quick Edit still addresses
`file.svg#ComponentId`: reproduce its snapshot first, then trace that stable id back to its source.
When a shared component changes, regenerate and check all screens that use it.

Commit source, build configuration and lockfile. By default also commit generated SVG and manifests
as reviewable snapshots, matching this skill's existing handoff. A project may ignore generated
artifacts if its build/CI regenerates them before review and verification; record that policy.
Do not ignore hand-authored SVG. The editable source is authoritative for edits; the approved
generated SVG is the visual acceptance baseline. Regeneration that changes approved output needs
review before it becomes a new baseline. Keep design components independent of production code;
implement the approved appearance and behaviour using the target stack.

## Compare pictures, not interactions

Choose the states relevant to the decision (for example default, empty, loading or error).
Render them as separate named SVG files at the same target size so the preview shows multiple
cards at once. Keep ids stable across files. Existing `data-state` layers and the preview switcher
remain useful for inspecting a component; use `svg_render.py --all-states` for their snapshots.
Do not require the reviewer to click through a working application to discover the design options.

Group related views with a heading and short rationale outside the mock-ups. Align compared
canvases, let captions wrap, and keep review notes distinct from actual UI copy. Compare only
enough alternatives to resolve the current question; avoid generating every possible combination.
Record which file/state/viewport was approved, then use that same baseline for implementation.

The preview's zoom, selection and Quick Edit are review tools, not product behaviour. Do not add
application logic to a design draft. For a design-only request, finish after rendering, inspecting
and delivering reviewable drafts; production screenshots and visual diffs apply only when an
implementation is requested. Never label a draft as a verified implementation.

## Keep context small

Read and edit the source component, relevant props and theme rather than repeatedly loading all
expanded SVG output. For implementation, hand off the manifest row and isolated render. A large
generated SVG is not itself proof of excessive model token use; inspect repetitive authored source
and oversized geometry separately. Do not promise a token reduction percentage without measuring it.

## Background

Inspired by the user-provided summary of https://www.youtube.com/watch?v=q8uBFzcZLo4 (not a verified
transcript) and [OpenCut's UI design skill](https://github.com/waterblower/opencut/blob/main/.agents/skills/ui-design/SKILL.md)
(inspected blob `6afda2627fd6669877e3a1080f51edb57d708bdf`). That skill currently prefers HTML JSX
for its own target. Here we adopt component reuse and static comparison while retaining structured
SVG, because this repository's lint, manifest, Quick Edit and diff tools depend on it. HTML review
documents can surround SVG mock-ups; arbitrary HTML is not input to those SVG tools.
