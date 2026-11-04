# 執行環境：local 與 sandbox

[English](../../skills/svg-ui-bridge/references/environments.md)

同一份 skill 會在兩種地方執行。`scripts/env_check.py` 最後一行會印出目前的環境：`MODE=local` 或 `MODE=sandbox`。`SVG_UI_MODE=local|sandbox` 可以覆寫偵測結果；偵測不準時可以由使用者設定，例如用 SSH 連到 Linux 主機並做了 port forwarding。

| | `MODE=local` | `MODE=sandbox` |
|---|---|---|
| 位置 | 使用者的電腦：終端機、VS Code、桌面 app 的 Claude Code 分頁 | 桌面 app 或 claude.ai 對話的雲端沙盒，或任何沒有顯示器的 Linux |
| Skill 名稱 | plugin 版 `/svg-ui-bridge:svg-ui-bridge` | 上傳版 `svg-ui-bridge` |
| 人工審閱 | `svg_preview.py design --serve`，把網址告訴使用者 | 靜態頁，發佈或傳送 |
| 驗證 | 截取使用者電腦上執行中的 app | 網頁：沙盒內啟動的頁面。原生 app：使用者上傳的截圖 |
| superpowers、pstack | 有安裝就使用 | 通常沒有 |

## 預覽

**local：** 照[工作流程](workflow.md)第 2 步。在背景啟動一次伺服器，把網址告訴使用者。

**sandbox：** localhost 無法連接使用者與沙盒（雙向都不行），這裡也開不了瀏覽器，所以即時伺服器沒有人看得到。

1. 執行 `python <skill>/scripts/svg_preview.py design --no-open`，它會寫出 `design/_preview.html`。
2. 修正印出的每一行 `warn:`。靜態頁載入不了引用的檔案，請把素材內嵌，或用基本圖形畫出來。
3. 能用 artifact 時就發佈成 artifact，否則傳送檔案。
4. 每次編輯 SVG 後都重新產生頁面，並更新同一個 artifact 或重新傳送，避免使用者審閱到舊設計。

sandbox 模式下的 `--serve` 會印出提醒，寫出同一份靜態頁後結束。資料夾裡的 HTML 設計稿會連同本機 CSS 一起內嵌，所以靜態頁仍不需要其他檔案。

artifact 內也能用 Quick Edit。iframe 擋住剪貼簿時，面板會顯示全文讓使用者手動複製。artifact 的留言功能仍可用。「送給 Agent」需要 `--serve`，靜態頁不會顯示這個按鈕。

關卡和 local 模式一樣由使用者的核准決定。使用者看過頁面並核准前，不寫產品程式。

## 驗證

兩種模式都要有 `visual_diff.py` 的輸出才能宣稱完成，差別只在截圖的來源。

**local：** 截取執行中的 app。網頁應用：

```
python <skill>/scripts/screenshot_web.py http://localhost:5173/settings -o shots/settings.png --size 1280x800
```

**sandbox，網頁專案：** 在沙盒內啟動 app 或建置成 HTML，再截圖。這裡連不到使用者自己執行中的 app。

```
python <skill>/scripts/screenshot_web.py build/index.html -o shots/settings.png --size 1280x800
```

**sandbox，原生 app 與遊戲：** 沙盒無法在有畫面的狀態下執行它們。依 SVG 的 `data-target` 和畫布，告訴使用者要截取的確切尺寸，以及要顯示哪個畫面和狀態，再對使用者上傳的檔案跑 `visual_diff.py`。使用者無法提供時，要回報視覺檢查尚未完成。沒有驗證的實作不算完成。

`screenshot_web.py` 會封鎖對其他來源的請求，並列為 `blocked …`。如果列出的資源會影響頁面外觀（例如網頁字型），請改由同一來源提供，否則比對時會顯示為缺少。

網頁請優先使用 `screenshot_web.py`。它會關閉 LCD 文字，與設計參考圖的算圖方式一致。其他截圖工具通常保持開啟，彩色邊緣可能讓小型文字元件超標。

## 缺少工具時

`env_check.py` 會實際算一張小 SVG 來測試每個算圖器。全部不能用時：

1. 嘗試 `python -m pip install pillow playwright`，再跑一次 `env_check.py`。沙盒必須允許安裝套件才行。
2. Playwright 需要瀏覽器，有 Chrome 或 Edge 就會使用。否則在允許下載時執行 `python -m playwright install chromium`。
3. 仍然無法算圖時，這些還能用：`svg_lint.py`、`svg_preview.py`、`tokens_export.py`、`svg_manifest.py --no-bbox`。沒有算圖器時，agent 看不到自己的畫稿，`visual_diff.py` 也無法處理 SVG，請告訴使用者哪一步卡住了。

## 搭配的 skill

superpowers 和 pstack 都是選用的。[整合說明](workflow-integration.md)只在它們出現於可用 skill 清單時才適用。沒有它們時，單獨照工作流程的 6 個步驟走，不要回報錯誤，也不要建議安裝。
