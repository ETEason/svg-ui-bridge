# SVG → framework mapping

The project CLAUDE.md states the target stack; this file gives the default translation so the
agent doesn't improvise. A project may override any row in its own CLAUDE.md.

## Universal rules

1. `id` → component / widget / struct name. Keep the name identical so grep finds both sides.
2. CSS-variable tokens → the framework's theme object, generated **once** from
   `<name>.components.json → tokens` into a single theme file; components reference tokens, never literals.
3. `data-layout` → the framework's layout primitive (table below). The SVG's absolute x/y are only
   for checking; never hard-code them unless `data-layout="absolute"`.
4. `data-state` → a state enum / props / style variants on one component, not separate components.
5. `data-note` → behaviour to implement and to test.
6. `data-bind` / `data-repeat` → props and list rendering.

## data-layout translation

| data-layout | Web (React + CSS/Tailwind) | Rust egui | Rust iced | Bevy UI | Qt / QML |
|---|---|---|---|---|---|
| `row gap-8` | `display:flex; gap:8px` / `flex gap-2` | `ui.horizontal(\|ui\| …)` + `ui.spacing_mut().item_spacing.x = 8.0` | `row![…].spacing(8)` | `Node{flex_direction: Row, column_gap: Val::Px(8.)}` | `RowLayout { spacing: 8 }` |
| `col gap-16` | `flex-direction:column; gap:16px` | `ui.vertical(…)` | `column![…].spacing(16)` | `flex_direction: Column, row_gap` | `ColumnLayout` |
| `center` | `align-items:center; justify-content:center` | `ui.centered_and_justified` / `Layout::centered_and_justified` | `.align_x(Center)` / `center(…)` | `align_items/justify_content: Center` | `Layout.alignment: Qt.AlignCenter` |
| `between` | `justify-content:space-between` | add `ui.with_layout(Layout::right_to_left(..))` for trailing items | `horizontal_space()` between | `JustifyContent::SpaceBetween` | `Item { Layout.fillWidth: true }` spacer |
| `pad-16` | `padding:16px` | `Frame::new().inner_margin(16.0)` | `.padding(16)` | `padding: UiRect::all(Val::Px(16.))` | `anchors.margins / padding` |
| `grid cols-3 gap-12` | `display:grid; grid-template-columns:repeat(3,1fr)` | `egui::Grid::new(id).num_columns(3)` | `grid` widget / nested rows | `display: Display::Grid, grid_template_columns` | `GridLayout { columns: 3 }` |
| `stack` | `position:relative` + absolutely-positioned children | layered `ui.put(rect, …)` | `stack![…]` | children with `PositionType::Absolute` | `Item` with overlapping children |
| `scroll-y` | `overflow-y:auto` | `ScrollArea::vertical()` | `scrollable(…)` | `Overflow::scroll_y()` | `ScrollView` |
| `fill` | `flex:1` / `w-full` | `ui.add_sized(ui.available_size(), …)` | `Length::Fill` | `flex_grow: 1.0` | `Layout.fillWidth: true` |

## Tokens

| target | where tokens go |
|---|---|
| Web | `src/styles/tokens.css` (`:root{--color-primary:…}`) or `tailwind.config` theme extend |
| egui | `theme.rs`: `pub const PRIMARY: Color32 = …;` + apply to `ctx.style_mut()` visuals |
| iced | custom `Theme` / palette module |
| Bevy | `Resource` struct `UiTheme { primary: Color, … }` |
| Qt/QML | `Theme.qml` singleton |

## Game assets

- `data-component="Sprite"` with an atlas note → load region from atlas, anchor as noted.
- Groups representing art layers → separate exported PNGs only if the engine needs them; the
  agent may slice them with `svg_render.py --component <Id> --scale 2`.
- SVG z-order (document order) = draw order / z-index.

## Fidelity limits to accept

- Text rendering differs between SVG renderers, browsers and native toolkits (hinting, kerning).
  Judge text by position and size, not pixels; that is why visual_diff has `--tol`.
- egui/immediate-mode UIs add their own default spacing and rounding — zero them in the theme
  first, or the whole screen will drift by a few px.
