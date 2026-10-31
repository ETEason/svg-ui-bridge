# SVG 到框架的對照

[English](../../skills/svg-ui-bridge/references/framework-mapping.md)

專案 CLAUDE.md 會說明目標技術棧；這份文件提供預設的轉換方式，避免 agent 自行發揮。專案可以在自己的 CLAUDE.md 覆寫任何一列。

## 通用規則

1. `id` → 元件、widget 或 struct 名稱。名稱保持相同，兩邊都能用 grep 找到。
2. CSS 變數 token → 框架的主題物件，從 `<name>.components.json → tokens` **一次**產生到單一主題檔；元件引用 token，絕不用字面值。
3. `data-layout` → 框架的版面基本元件（見下表）。SVG 的絕對 x/y 只用來檢查；除非是 `data-layout="absolute"`，否則絕不寫死。
4. `data-state` → 同一元件上的狀態 enum、props 或樣式變體，不是分開的元件。
5. `data-note` → 要實作並測試的行為。
6. `data-bind` / `data-repeat` → props 與列表渲染。

## data-layout 轉換

| data-layout | Web (React + CSS/Tailwind) | Rust egui | Rust iced | Bevy UI | Qt / QML |
|---|---|---|---|---|---|
| `row gap-8` | `display:flex; gap:8px` / `flex gap-2` | `ui.horizontal(\|ui\| …)` + `ui.spacing_mut().item_spacing.x = 8.0` | `row![…].spacing(8)` | `Node{flex_direction: Row, column_gap: Val::Px(8.)}` | `RowLayout { spacing: 8 }` |
| `col gap-16` | `flex-direction:column; gap:16px` | `ui.vertical(…)` | `column![…].spacing(16)` | `flex_direction: Column, row_gap` | `ColumnLayout` |
| `center` | `align-items:center; justify-content:center` | `ui.centered_and_justified` / `Layout::centered_and_justified` | `.align_x(Center)` / `center(…)` | `align_items/justify_content: Center` | `Layout.alignment: Qt.AlignCenter` |
| `between` | `justify-content:space-between` | 尾端項目加上 `ui.with_layout(Layout::right_to_left(..))` | 中間放 `horizontal_space()` | `JustifyContent::SpaceBetween` | `Item { Layout.fillWidth: true }` 作為間隔 |
| `pad-16` | `padding:16px` | `Frame::new().inner_margin(16.0)` | `.padding(16)` | `padding: UiRect::all(Val::Px(16.))` | `anchors.margins / padding` |
| `grid cols-3 gap-12` | `display:grid; grid-template-columns:repeat(3,1fr)` | `egui::Grid::new(id).num_columns(3)` | `grid` widget / 巢狀 row | `display: Display::Grid, grid_template_columns` | `GridLayout { columns: 3 }` |
| `stack` | `position:relative` + 絕對定位的子元素 | 分層 `ui.put(rect, …)` | `stack![…]` | 子元素用 `PositionType::Absolute` | 子元素重疊的 `Item` |
| `scroll-y` | `overflow-y:auto` | `ScrollArea::vertical()` | `scrollable(…)` | `Overflow::scroll_y()` | `ScrollView` |
| `fill` | `flex:1` / `w-full` | `ui.add_sized(ui.available_size(), …)` | `Length::Fill` | `flex_grow: 1.0` | `Layout.fillWidth: true` |

## Token

| 目標 | token 放在哪裡 |
|---|---|
| Web | `src/styles/tokens.css`（`:root{--color-primary:…}`）或 `tailwind.config` 的 theme extend |
| egui | `theme.rs`：`pub const PRIMARY: Color32 = …;`，並套用到 `ctx.style_mut()` visuals |
| iced | 自訂 `Theme` 或 palette 模組 |
| Bevy | `Resource` struct `UiTheme { primary: Color, … }` |
| Qt/QML | `Theme.qml` singleton |

## 遊戲素材

- 帶圖集註記的 `data-component="Sprite"` → 從圖集載入區域，依註記設定錨點。
- 代表美術圖層的群組 → 只有引擎需要時才匯出成獨立 PNG；agent 可用 `svg_render.py --component <Id> --scale 2` 切出來。
- SVG 的 z-order（文件順序）= 繪製順序或 z-index。

## 可接受的還原度限制

- SVG 算圖器、瀏覽器和原生 UI 工具的文字渲染都不同（hinting、字距）。文字請看位置和大小，不要比像素，這就是 visual_diff 有 `--tol` 的原因。
- egui 這類 immediate-mode UI 會加上自己的預設間距和圓角。請先在主題裡歸零，否則整個畫面會偏移幾個 px。
