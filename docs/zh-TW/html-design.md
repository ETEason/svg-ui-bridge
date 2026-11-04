# 靜態 HTML/CSS 設計路線

[English](../../skills/svg-ui-bridge/references/html-design.md)

用於網頁 UI：任何最後會做成 HTML/CSS 的介面，包括表單、長文字和響應式頁面。流程和 SVG 路線相同（預覽、Quick Edit、元件清單、token、逐元件視覺比對），只是指令換成 HTML 專用的。新增設計系統前，先沿用專案既有的。檢查時需要 Python、Playwright 和 Chromium 系瀏覽器；撰寫不需要 npm 或伺服器。

## 撰寫與比較

把 `templates/html-design/` 複製到設計資料夾（例如 `design/html/`），`review.html` 和 `theme.css` 要放在一起。設計稿可以直接用瀏覽器開啟（`file://`）。不要用腳本、遠端字型、CDN 或函式庫；預覽時會移除腳本，檢查時也會關閉 JavaScript。請使用本機資源和共用的 CSS 變數；版面交給 Grid/Flex，圖形用內嵌 SVG。重複的標記可以由 TSX 產生（見[元件化撰寫](component-authoring.md)），但不要修改產生出來的檔案。

每個要單獨審閱的介面是一個畫面：一個帶有唯一 PascalCase `id`、`data-screen` 名稱和 `data-state` 的元素。畫面不能巢狀。元件要加上 `data-component="Kind"` 和唯一的 PascalCase `id`，並在修改之間保持 id 不變。同一份文件中的 id 必須唯一，重複的元件請加上狀態前綴。隱藏的元件不會列入報告。

決策所依據的各種狀態，各自做成一個畫面並排顯示，窄視窗時改成上下排列。標題、理由和說明文字放在 `[data-screen]` 之外；畫面裡的文字會被當成真正的 UI 文案。不要為了展示狀態而實作導覽、事件或網路請求。使用真實文案，包括實際會出現的長字串。

## 預覽與 Quick Edit

```text
python <skill>/scripts/svg_preview.py design/html --serve     # local：即時預覽頁，把網址告訴使用者
python <skill>/scripts/svg_preview.py design/html --no-open   # sandbox：要發佈的靜態頁
```

預覽頁把每個畫面放在各自的卡片中，用設計稿自己的 HTML 和本機 CSS 呈現，並移除腳本。「寬度」選單設定視窗寬度（1280、768、390，或卡片寬度），media query 會生效、文字會重新換行。選取、Alt 拖曳框選、breadcrumb 和 Quick Edit 面板的用法都和 SVG 路線相同。修改請求以 `file.html#Id?state=…&width=…` 指出位置；區域座標是相對於畫面的 CSS 像素。處理方式照 SKILL.md：先執行 `svg_render.py --job` 並看圖，它會在同樣的寬度下算出同一個畫面。

## 請人審閱前先檢查

```text
python <skill>/scripts/html_review.py design/html/review.html --size 1280x800 --out shots/html-desktop
python <skill>/scripts/html_review.py design/html/review.html --size 390x844 --out shots/html-mobile
```

每種視窗尺寸或每次修改都用不同的輸出資料夾。這個工具會在關閉頁面 JavaScript 的情況下開啟本機檔案、封鎖外部請求，並檢查畫面與元件 id、靜態內容、載入失敗的資源和基本溢出。結束碼：0 = 結構檢查通過，1 = 草稿有問題，2 = 輸入無效或擷取失敗。它是本機撰寫輔助工具，不是開啟不可信檔案用的沙盒。

通過時，每個畫面會寫出一張 PNG 和 `<id>.components.json`，另外寫出 `report.json`；未通過時只寫報告。只使用目前這份成功報告列出的檔案，舊檔案可能還留著。位置是相對於每個畫面左上角的 CSS 像素（DPR 1）。

分享前先看過所有 PNG，修正被裁切的文字、不自然的換行、對齊和間距。溢出檢查是推測性的：刻意設計的捲動也會被標出，也無法證明沒有重疊或文字被裁切。刻意的例外要記錄並用眼睛確認；報告未通過時絕不能說是 PASS。

## Token

```text
python <skill>/scripts/tokens_export.py design/html/review.html --format ts -o src/theme/tokens.ts
```

它會從設計稿的本機樣式表和 `<style>` 區塊讀取 CSS 變數；也可以直接傳入 `.css` 檔。

## 驗證實作

先擷取核准的基準：每個畫面單獨在目標視窗寬度下呈現，這就是實作截圖會呈現的樣子。

```text
python <skill>/scripts/html_review.py design/html/review.html --size 1280x800 --out shots/baseline-1280 --standalone
```

在相同寬度下截取實作畫面並裁切到該畫面（網頁可用 `screenshot_web.py`），再比對：

```text
python <skill>/scripts/visual_diff.py shots/baseline-1280/SettingsDefault.png shots/app-settings.png --manifest shots/baseline-1280/SettingsDefault.components.json
```

門檻和 SVG 路線相同：整體 ≤ 2%，且沒有元件超過 10%。內容、狀態和字型必須與基準一致；實作中的動態資料會被算成差異。

## 兩條路線的對照

| | SVG 路線 | HTML 路線 |
|---|---|---|
| 預覽與 Quick Edit | `svg_preview.py` | `svg_preview.py`，多一個「寬度」選單 |
| 重現 Quick Edit 的畫面 | `svg_render.py --job` | `svg_render.py --job`（`format: html`） |
| 設計稿檢查 | `svg_lint.py` | `html_review.py` |
| 元件清單 | `svg_manifest.py` | `html_review.py`（`<id>.components.json`） |
| Token 匯出 | 對 SVG 執行 `tokens_export.py` | 對 HTML 或 CSS 執行 `tokens_export.py` |
| 逐元件視覺比對 | `visual_diff.py design.svg …` | `visual_diff.py baseline.png …` 加上元件清單 |
| 狀態 | 同一檔案中的 `data-state` 圖層 | 每個狀態一個畫面 |
