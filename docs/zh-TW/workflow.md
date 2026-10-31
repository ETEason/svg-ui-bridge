# svg-ui-bridge 工作流程

[English](../../skills/svg-ui-bridge/SKILL.md)

SVG 是人的視覺意圖和 agent 程式碼之間的共同語言：人判斷渲染出來的畫面，agent 讀有命名、有分層、用 token 表示的標記。要反覆修改的是畫面，不是程式碼。

腳本放在 skill 資料夾的 `scripts/` 裡（需要 Python 3 與 Pillow，再加一種 SVG 算圖器：resvg、rsvg-convert、搭配系統 Chrome/Edge 的 Playwright，或 cairosvg）。下文以 `<skill>/scripts/…` 表示。

## 適用時機

- 適用：任何有視覺結果的工作，包含小調整（「移動按鈕」、「卡片加深」）。
- 略過：純邏輯或後端變更、只改文案，或使用者說「不用畫稿」。
- 搭配 superpowers：本流程在 **brainstorming 的設計步驟之內**執行，影響規格、計畫任務和驗證證據，不取代 superpowers 的任何階段。詳見[整合 superpowers 與 pstack](workflow-integration.md)（superpowers 或 pstack skill 啟用時請閱讀）。

## 流程

### 1. 繪製 SVG（設計階段，還沒有產品程式）

- 在一個 session 寫第一份 SVG 前，先讀 [SVG 規範](svg-conventions.md)。
- 寫出 `design/<畫面>.svg`（或專案 CLAUDE.md 指定的資料夾）。專案已有畫面或 token 時，沿用它們並延續既有外觀；使用者提供截圖或草圖時，描出它的結構。
- 每個元件都是 `<g id="PascalCase" data-component="Kind">`；子元件依 `data-layout` 排列；變體是 `data-state` 圖層；顏色與間距是 `<style>` 裡的 CSS 變數。

### 2. 檢查、預覽、人工關卡

```
python <skill>/scripts/svg_lint.py design/<screen>.svg
python <skill>/scripts/svg_preview.py design --serve        # 人：瀏覽器即時預覽頁
python <skill>/scripts/svg_render.py design/<screen>.svg     # agent：用 Read 查看的 PNG
```

- 修正所有 ERROR；warning 也要修，除非有明確理由。
- **人在瀏覽器上審閱**，不看 XML，也不看 PNG：`svg_preview.py --serve` 會開啟 http://localhost:8765 的頁面，`design/` 裡的 SVG 一變更就自動重新載入，並提供狀態切換（default/hover/disabled…）、滑過辨識元件（id、layout、note）和縮放。設計工作開始時在背景啟動一次，並把網址告訴使用者。
  不想讓程序長時間執行時：`svg_preview.py design` 會寫出 `design/_preview.html` 並開啟。
- **Agent 先檢查自己的畫稿**：請使用者看之前，先算出 PNG 並讀取（檢查重疊、文字被裁切、對不齊）。`--all-states` 會算出每種狀態。
- 用視覺語言徵求回饋。把回饋改進 SVG → 重新檢查 →（預覽自動更新）→ 重複。
- **關卡：** 使用者核准設計前，不寫產品程式（這就是 superpowers 所說的設計核准）。

### 3. 拆解

```
python <skill>/scripts/svg_manifest.py design/<screen>.svg
```

產生 `<screen>.components.md/.json`：元件樹、實測邊界框、token、狀態、註記，以及從葉節點開始的實作順序。在規格中加入「Visual design」段落，連結 SVG、元件清單和驗收門檻（預設：整體 ≤ 2%，單一元件都不超過 10%）。

如果元件清單顯示某元件的版面、狀態或行為不明確，那就是設計缺口：先詢問，再修正 SVG。視覺規格會迫使這些決定在程式出現前就定案。

### 4. 規劃並逐元件實作

- SVG 到程式的對應依專案 CLAUDE.md，沒有就依[框架對照](framework-mapping.md)。
- 從 SVG 產生 token 或主題檔，絕不手抄顏色：
  `python <skill>/scripts/tokens_export.py design/<screen>.svg --format css|ts|egui|bevy|json -o <file>`
- 每個元件一個計畫任務（從葉節點開始），每個畫面再一個組裝任務。
- 每位實作者（或 subagent）只拿到：該元件在清單中的那一列、`svg_render.py --component <Id>` 的 PNG，必要時加上 `<g>` 子樹。不要把整份 SVG 貼進每個提示。

### 5. 視覺驗證

- 以 SVG 的 `data-target` 尺寸截取執行中的實作，並裁切到畫布範圍（有專案驗證 skill 就用它，否則用 Playwright、瀏覽器工具或引擎的截圖功能）。
- 執行：
  ```
  python <skill>/scripts/visual_diff.py design/<screen>.svg shots/<screen>.png --manifest design/<screen>.components.json [--scale <dpr>]
  ```
  網頁應用請設定 `SVG_UI_RENDERER=playwright`，讓參考圖由和 App 相同的引擎算圖（文字雜訊少很多）。通過需要整體 ≤ `--max`，**而且**每個元件都 ≤ `--max-component`。做錯的按鈕在整個畫面可能不到 1%，但對按鈕本身可能約 40%，所以絕不能只看整體數字。
- 通過 → 回報數字和差異圖路徑作為證據。未通過 → 打開差異圖（設計 | 實作 | 熱度圖），修正超標的元件後重跑。要找偏移量時，比較元件在清單中的邊界框和元素的實際位置（例如瀏覽器的 getBoundingClientRect）。文字反鋸齒的殘留差異是正常的，低於門檻就不用追。

### 6. 後續變更

視覺變更需求先改 SVG（對受影響的元件走步驟 1 → 5）。SVG 始終是依據；程式和 SVG 不一致時，要嘛修程式，要嘛請使用者核准 SVG 更新，絕不能悄悄讓兩者分歧。

## 危險訊號

| 想法 | 應該改成 |
|---|---|
| 「只是小 UI 調整，直接改 CSS 就好」 | 改該元件的 `<g>`，算圖，請使用者點頭。兩分鐘的事。 |
| 「我用文字描述版面」 | 畫出來。這個 skill 要取代的就是文字描述。 |
| 「把整份 SVG 貼給每個 subagent」 | 只給清單列和單獨算圖的結果。 |
| 「我看起來沒問題」 | 跑 visual_diff，回報數字。 |
| 「整體差異才 1.8%，可以交了」 | 檢查每個元件的清單；任一元件超標就是未通過。 |
| 給使用者看 SVG 原始標記 | 給即時預覽頁（沒有瀏覽器時給 PNG）。 |
| 「SVG 過時了，現在以程式為準」 | 更新 SVG 並取得核准，或修正程式。 |
| 從 Figma/Illustrator 匯出、有數千個路徑點的 SVG | 用有 id 的基本圖形重畫，或請使用者匯出時保留圖層與 id。 |
