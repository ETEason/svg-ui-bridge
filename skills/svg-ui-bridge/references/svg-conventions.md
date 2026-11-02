# SVG design-spec conventions

The SVG is a **spec**, not an illustration. Every rule below exists so an agent can read structure
straight from the markup and so `svg_lint.py` / `svg_manifest.py` / `visual_diff.py` can work.

## 1. Root

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 800" width="1280" height="800"
     data-screen="Settings" data-target="desktop-1280">
  <style>
    :root {
      --color-bg: #0f1115;  --color-surface: #181b22;  --color-primary: #4f8cff;
      --color-on-primary: #ffffff; --color-text: #e8eaf0; --color-muted: #8b93a7;   --color-danger: #ff5c6c;
      --radius-md: 8px;     --space-2: 8px;            --space-4: 16px;
    }
    text { font-family: Inter, "Noto Sans TC", sans-serif; }
  </style>
  ...
</svg>
```

- `viewBox` = the logical canvas in CSS px (1×). One SVG per screen **and** per breakpoint when
  layouts differ (`settings.desktop.svg`, `settings.mobile.svg`).
- `data-screen` names the screen; `data-target` says which viewport/window size it represents.
- **All colours, radii, spacing live as CSS variables in `<style>`** and are used as
  `fill="var(--color-primary)"`. These become the design tokens in code.
- Declare the font stack once. Text that matters (labels, numbers) uses real copy, not lorem.

## 2. Components

```xml
<g id="SaveButton" data-component="Button" data-layout="row center gap-8"
   data-note="primary action; disabled until form is dirty">
  <g data-state="default">
    <rect x="1120" y="728" width="128" height="40" rx="8" fill="var(--color-primary)"/>
    <text x="1184" y="753" text-anchor="middle" font-size="15" fill="var(--color-on-primary)">儲存</text>
  </g>
  <g data-state="hover" display="none"> ... </g>
  <g data-state="disabled" display="none"> ... </g>
</g>
```

| attribute | meaning |
|---|---|
| `id` | **PascalCase, unique.** Becomes the component / widget name in code. Sub-parts may use `Parent-Part` (e.g. `NavBar-Item`). |
| `data-component` | The kind: `Button`, `Card`, `List`, `ListItem`, `Input`, `Toggle`, `Panel`, `Icon`, `Sprite`, `HUD`… Marks the group as a component (the scripts only treat `<g data-component>` as components). |
| `data-layout` | How children flow — the part SVG cannot express. Grammar: `row|col|stack|grid|absolute|wrap` then modifiers: `gap-<n>`, `pad-<n>` / `pad-<y>-<x>`, `center`, `start`, `end`, `between`, `fill` (stretch to parent), `fixed-<w>x<h>`, `scroll-y`. Required when a component has ≥2 child components. |
| `data-state` | Variant layers inside a component: `default` (visible) plus `hover`, `pressed`, `disabled`, `selected`, `error`, `empty`, `loading`… Non-default states carry `display="none"`. |
| `data-token` | Optional, for a semantic token that is not a colour (e.g. `data-token="type.title"`). |
| `data-note` | Behaviour the picture can't show: "debounced search", "truncates with ellipsis", "drag to reorder". Keep it one line. |
| `data-bind` | Optional: data source of dynamic content (`data-bind="user.name"`, `data-bind="items[]"`). For lists draw 2–3 items and mark the first with `data-repeat="items"`. |

Nesting rule: **the `<g>` tree is the component tree.** A `Card` that contains a `Button` contains
that button's `<g>`. Purely decorative groups don't need `data-component`.

## 3. Drawing rules

- Use primitives (`rect`, `circle`, `line`, `text`) wherever possible; `path` only for icons/shapes.
- No exported "path soup", no flattened text-to-outline, no embedded base64 images. Icons: keep them
  small (`<g data-component="Icon" id="Icon-Search">`), or reference an asset (`<use href="icons.svg#search">`).
- Coordinates are absolute and integer where possible (keeps the diff stable).
- Aim to keep hand-authored SVG under ~60 KB. For repetition, use `component-authoring.md`.
  Generated output may be larger: inspect source repetition and geometry separately, avoid loading
  expanded output into prompts, and document any accepted size warning.

## 4. Game / canvas UI

- One SVG per scene/HUD layout. Sprites and atlas regions are `<g data-component="Sprite" id="Player-Idle">`
  with `data-note="atlas: chars.png 0,0,64,64; anchor bottom-center"`.
- Animated parts: draw keyframes as states (`data-state="frame-1"`…) and note timing in `data-note`.
- Layering order in the SVG = z-order in the engine; say so in the project CLAUDE.md mapping.

## 5. Quick Edit references

A change request copied from the preview page points at parts of a design like this. Paths are
relative to the folder `svg_preview.py` ran in, or absolute with `--absolute-paths`.

| form | meaning |
|---|---|
| `design/login.svg#SignInButton` | one component |
| `design/login.svg#SignInButton,RememberMe` | several components selected together; split on commas after `#` (ids never contain commas) |
| `design/login.svg#SignInButton?state=hover` | not the default state; `?state=` goes last and applies to the whole line |
| `design/login.svg#region(480,600,320,40)@LoginCard` | a region in SVG coordinates, rounded to integers, and the component it falls in. Each region has its own line |

A selection across files gets one line per file. The `Snapshot JSON (svg_render.py --job)` block
reproduces what the user saw: `view.visible` is `[x, y, w, h]` in SVG coordinates, and `selection`
holds `ref`, `kind`, `path` and `bbox`. When files differ it is a list with one job per file.

## 6. What the agent reads vs. what the human reads

- Human reviews the browser preview or delivered static page. The agent inspects PNG renders
  (`svg_render.py`) before sharing. Show compared states together, not only through a switcher.
- Agent implementing a component reads **only that component**: its row in `<name>.components.md`
  plus `svg_render.py --component <Id>` output, or the `<g>` subtree. Never paste the whole SVG
  into every subagent prompt — that is where the token saving comes from.
