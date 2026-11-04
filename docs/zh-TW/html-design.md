# 靜態 HTML/CSS 設計路線

[English](../../skills/svg-ui-bridge/references/html-design.md)

適用於大量文字、表單和響應式版面。這條路線取代 SVG 專用的流程；不要把 HTML 交給 `svg_lint.py`、`svg_manifest.py`、`svg_preview.py` 或 `visual_diff.py`。檢查時需要 Python、Playwright 和支援的 Chromium 系瀏覽器，但撰寫或開啟內附草稿不需要 npm 或伺服器。新增設計系統前，先沿用專案既有的。

## 撰寫與比較

把 `templates/html-design/` 複製到設計資料夾，`review.html` 和 `theme.css` 要放在一起，直接用瀏覽器開啟 HTML（`file://`）。在沙盒裡請交付整個資料夾或 zip，或連同 CSS 一起做成 artifact；只傳 HTML 會失去樣式。範本刻意不用腳本、遠端字型、CDN 或函式庫。請使用本機資源和共用的 CSS 變數；版面交給 Grid/Flex，圖形用內嵌 SVG。重複的標記可沿用既有的範本系統，JSX 是選用的，產生的 HTML 仍是靜態的。不要修改產生出來的檔案。

每個要單獨擷取的畫面，都要有唯一的 PascalCase `id`、`data-screen` 名稱和 `data-state`。畫面根元素不能巢狀。元件要加上 `data-component="Kind"` 和唯一的 PascalCase `id`，並在修改之間保持 id 不變。同一份 HTML 裡的 id 必須唯一，重複出現的元件請加上狀態前綴。隱藏的元件不會列入位置報告。

並排顯示影響決策的狀態，窄視窗時改成上下排列。標題、理由和說明文字放在 `[data-screen]` 之外；畫面裡的文字會被當成真正的 UI 文案。不要為了展示狀態而實作導覽、事件或網路請求。使用真實文案，包括實際會出現的長字串。各變體使用一致的 token 和元件 class。

## 請人審閱前先檢查

在使用這份設計的專案根目錄執行（把 `<skill>` 換成 skill 的安裝資料夾）：

```text
python <skill>/scripts/html_review.py design/html/review.html --size 1280x800 --out shots/html-desktop
python <skill>/scripts/html_review.py design/html/review.html --size 390x844 --out shots/html-mobile
```

每種視窗尺寸或每次修改都用不同的輸出資料夾。這個工具會在關閉頁面 JavaScript 的情況下開啟本機檔案、封鎖外部請求，並檢查畫面與元件識別、靜態內容、載入失敗的資源和基本溢出。結束碼：0 = 結構檢查通過，1 = 草稿有問題，2 = 輸入無效或擷取失敗。它是本機撰寫輔助工具，不是開啟不可信檔案用的沙盒。

通過時會為每個畫面寫出一張 PNG 和 `report.json`；未通過時只寫報告，不產生新的 PNG。只使用目前這份成功報告列出的截圖，舊檔案可能還留著。報告記錄瀏覽器視窗大小、畫面的實際大小，以及可見元件相對於畫面左上角的位置（CSS 像素，DPR 1）。PNG 邊緣會把小數的 CSS 座標取整為像素。比較用的頁面裡，畫面會比瀏覽器視窗窄；需要完整視窗大小的基準時，請用沒有審閱邊距的獨立畫面。不要拿整頁審閱頁和裁切過的產品截圖比較。

分享前先看過所有 PNG，修正被裁切的文字、不自然的換行、對齊和間距。溢出檢查是推測性的：刻意設計的捲動也會被標出，而且無法證明沒有重疊或文字被裁切。刻意的例外要記錄下來並人工檢查；報告未通過時不要說是 PASS。可捲動的介面請擷取並標示相關的可見狀態。這項檢查不提供自動化的無障礙或產品視覺還原度認證。

## 審閱與交接

分享算圖後的審閱頁，詢問外觀上的意見。處理回饋時以 `file.html#Id`、狀態和視窗尺寸指出位置；修改來源或主題後，重新擷取所有受影響的畫面並檢查結果。這個版本的 HTML 不支援 SVG 的 Quick Edit 選取面板和 snapshot job 語法。

記錄核准的來源版本、檔案、畫面 id 與狀態、視窗尺寸、畫面實際大小和 PNG。提交 HTML/CSS 和本機資源（產生的設計則提交來源與建置設定）；截圖放在專案存放證據的位置。只要求設計時到此結束，不要建立產品應用程式。

要求實作時，交接相關元件的位置與裁切圖、共用的 CSS token、行為說明和核准的截圖。`report.json` 是 HTML 審閱報告，不是 SVG 元件清單的格式，也不是實作順序計畫，不能送進 SVG 的比對流程。請用目標專案的瀏覽器截圖比對工具，在相同的尺寸、內容和狀態下比較。沒有這類工具時，要明確回報是人工比對並缺少自動化證據；不能宣稱這條路線提供 SVG 路線的 2%／10% 自動驗收。

## 這個版本的功能範圍

| 功能 | SVG 路線 | HTML 路線 |
|---|---|---|
| 靜態審閱與算圖截圖 | 既有的預覽與算圖 | 本機 HTML 與 `html_review.py` |
| 元件識別 | SVG 群組與元件清單 | DOM id 與量測報告 |
| Quick Edit 與 snapshot job | 支援 | 不支援 |
| Token 匯出 | `tokens_export.py` | 直接維護共用的 CSS 變數 |
| 實作的自動像素比對 | `visual_diff.py` | 使用專案自己的工具；未內建 |

選用的流程整合也要遵守這個範圍：在設計規格中連結 HTML、報告和核准的 PNG；HTML 草稿不要求 SVG 元件清單或 SVG 比對。
