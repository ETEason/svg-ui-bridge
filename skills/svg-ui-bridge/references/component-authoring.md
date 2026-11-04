# Component authoring and static review

Read this when repeated components, multiple screen variants, or state comparisons make raw SVG or
HTML expensive to maintain. The tools read SVG (or HTML on that route); that need not be what you
write by hand.

## Choose the smallest useful authoring layer

- Edit a small existing SVG or HTML draft directly when extraction would add more work than it
  removes. Do not introduce a build chain just for one small static draft.
- For repeated cards, rows, controls or screen variants, prefer TSX functions and typed props.
  Reuse the project's design build if it has one. JSX is a build-time template language here; it
  does not need a React app, hydration, event handlers, or a development server.
- Keep shared colours, fonts and dimensions in one theme module; use data arrays for repetition.
  Pass an explicit stable instance id to each component. Keep the SVG conventions in the output,
  including `data-component`, `data-layout`, tokens, target size, and state layers.
- SVG `defs`/`use` does not replace typed component composition. Emit inspectable `<g>` instances
  for UI components so manifests and Quick Edit can identify each instance.
- Run a real type checker such as `tsc --noEmit`. A successful build only shows that the code
  transpiled, not that its types are correct.

Suggested project layout (adapt to existing paths):

```text
design/system/components/    shared TSX design components
design/system/theme.ts       shared design tokens
design/system/pages/         screen templates and explicit variants
design/system/build.tsx      static export entrypoint
design/*.svg                generated tool inputs and review artifacts
```

The svg-ui-bridge repository has a working example in `examples/tsx-design/`: two static states of
one screen from a shared Button component, with pinned dependencies, a lockfile and a `typecheck`
script. It is not part of the installed skill. To use it, copy the folder to `design/system`, run
`npm ci` there once, then `npm run typecheck` and `npm run build`. Node.js and npm are needed only
for authoring; the Python tools work without them. There is no watcher: rebuild after every source
edit, before previewing, linting, generating a manifest or exporting tokens.

## One editable source, reproducible output

Record the source path and build command in the project's instructions. Edit TSX, theme or data,
then rebuild; never patch generated SVG as a lasting change. Quick Edit still addresses
`file.svg#ComponentId`: reproduce its snapshot first, then trace that stable id back to its source.
When a shared component changes, regenerate and check every screen that uses it.

Commit the source, build configuration and lockfile. By default also commit generated SVG and
manifests as reviewable snapshots. A project may ignore generated artifacts if its build or CI
regenerates them before review and verification; record that policy. Never ignore hand-authored
SVG. The editable source is what you change; the approved generated SVG is the visual baseline.
Regeneration that changes approved output needs review before it becomes the new baseline. Keep
design components independent of production code, and implement the approved look and behaviour
in the target stack.

## Compare pictures, not interactions

Choose the states relevant to the decision (for example default, empty, loading or error). Render
them as separate named files at the same target size so the preview shows them at once. Keep ids
stable across files. `data-state` layers and the preview switcher remain useful for inspecting one
component; `svg_render.py --all-states` renders their snapshots. Do not make the reviewer click
through a working application to discover the options.

Group related views under a heading with a short rationale outside the mock-ups. Align compared
canvases, let captions wrap, and keep review notes apart from real UI copy. Compare only enough
alternatives to settle the current question. Record which file, state and size was approved, and
use that same baseline for implementation.

Zoom, selection and Quick Edit in the preview are review tools, not product behaviour. Do not add
application logic to a design draft.

## Keep context small

Read and edit the source component, its props and the theme instead of loading all expanded output
again. For implementation, hand off the manifest row and the isolated render. A large generated
file is not by itself proof of high token use; look at repetition in the source and oversized
geometry separately. Do not promise a token saving without measuring it.
