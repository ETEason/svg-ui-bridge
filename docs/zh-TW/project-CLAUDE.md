<!-- 貼進專案的 CLAUDE.md 並填好 <…> 的部分，刪除不適用的列。英文版：skills/svg-ui-bridge/templates/project-CLAUDE.md.template -->

## 視覺設計（svg-ui-bridge）

- 設計規格：`design/<畫面>.svg`（以及產生的 `<畫面>.components.md/.json`）。截圖：`shots/`。
- 目標技術棧：<React 19 + Tailwind | Rust egui 0.3x | Bevy 0.1x UI | Qt 6 QML | …>
- 畫布尺寸：桌面 `<1280x800>`、手機 `<390x844>`，版面有變化的斷點各一份 SVG。
- Token 放在 `<src/styles/tokens.css | src/theme.rs | …>`，由 SVG `<style>` 的 token 產生。
  已有 token 的顏色和間距，程式裡一律不用字面值。
- 驗收：`visual_diff.py` 整體 ≤ <2>%，且沒有元件 > <10>%（預設；`--tol 24 --shift 1`）。網頁：`SVG_UI_RENDERER=playwright`。
- 截圖指令：<`/verify`（pstack 專案驗證 skill）| `npx playwright screenshot --viewport-size=1280,800 http://localhost:5173/settings shots/settings.png` | `cargo run --example screenshot -- settings`>

### 對照覆寫（SVG → 程式）
| SVG | 本專案 |
|---|---|
| `data-component="Button"` | <`components/ui/Button.tsx` 的 variant prop / `widgets::button()`> |
| `data-layout="row …"` | <Tailwind `flex gap-*` / `ui.horizontal`> |
| `data-state` | <`variant`/`state` prop / enum `ButtonState`> |
| 圖示 | <lucide-react / `assets/icons/*.svg`> |

### 搭配 superpowers
- brainstorming 中，UI 工作至少是 *bounded*；每個畫面的設計段落都是經核准的 SVG 渲染結果。
- 規格（`docs/superpowers/specs/…`）必須有「Visual design」段落，連結 SVG、元件清單和上述驗收門檻。
- writing-plans：每個清單元件一個任務（從葉節點開始），每個畫面一個組裝任務；每個任務的驗收是該畫面帶 `--manifest` 的 visual_diff 指令。
- verification-before-completion：視覺宣稱需要最新的 visual_diff PASS 輸出和差異圖路徑。

### 雜項
- Commit `design/*.svg` 和 `design/*.components.*`；忽略產生的圖片：
  `.gitignore` → `design/*.png`、`design/_preview.html`、`shots/*.diff.*`
