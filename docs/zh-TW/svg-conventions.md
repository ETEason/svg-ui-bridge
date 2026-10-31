# SVG 設計規格規範

[English](../../skills/svg-ui-bridge/references/svg-conventions.md)

這份 SVG 是**規格**，不是插圖。下列每條規則都是為了讓 agent 能直接從標記讀出結構，也讓 `svg_lint.py`、`svg_manifest.py`、`visual_diff.py` 能運作。

## 1. 根元素

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

- `viewBox` 是以 CSS px 為單位的邏輯畫布（1 倍）。每個畫面一份 SVG；版面會隨斷點改變時，每個斷點也各一份（`settings.desktop.svg`、`settings.mobile.svg`）。
- `data-screen` 命名畫面；`data-target` 說明代表哪個視窗尺寸。
- **所有顏色、圓角、間距都以 CSS 變數放在 `<style>`**，並用 `fill="var(--color-primary)"` 的方式引用。它們會成為程式裡的設計 token。
- 字型堆疊只宣告一次。重要的文字（標籤、數字）用真實文案，不用 lorem。

## 2. 元件

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

| 屬性 | 意義 |
|---|---|
| `id` | **PascalCase 且唯一。** 會成為程式裡的元件或 widget 名稱。子部分可用 `Parent-Part`（例如 `NavBar-Item`）。 |
| `data-component` | 種類：`Button`、`Card`、`List`、`ListItem`、`Input`、`Toggle`、`Panel`、`Icon`、`Sprite`、`HUD`…。標記這個群組是元件（腳本只把 `<g data-component>` 視為元件）。 |
| `data-layout` | 子元素如何排列，這是 SVG 本身表達不了的部分。語法：`row|col|stack|grid|absolute|wrap`，再加修飾詞：`gap-<n>`、`pad-<n>` / `pad-<y>-<x>`、`center`、`start`、`end`、`between`、`fill`（撐滿父層）、`fixed-<w>x<h>`、`scroll-y`。元件有 2 個以上子元件時必填。 |
| `data-state` | 元件內的變體圖層：`default`（可見），再加 `hover`、`pressed`、`disabled`、`selected`、`error`、`empty`、`loading`…。非預設狀態要帶 `display="none"`。 |
| `data-token` | 選用，用於非顏色的語意 token（例如 `data-token="type.title"`）。 |
| `data-note` | 畫面表達不了的行為：「搜尋有 debounce」、「超長時以省略號截斷」、「可拖曳排序」。保持一行。 |
| `data-bind` | 選用：動態內容的資料來源（`data-bind="user.name"`、`data-bind="items[]"`）。列表畫 2–3 個項目，並在第一個標上 `data-repeat="items"`。 |

巢狀規則：**`<g>` 樹就是元件樹。** 包含 `Button` 的 `Card`，就包含該按鈕的 `<g>`。純裝飾的群組不需要 `data-component`。

## 3. 繪製規則

- 盡量用基本圖形（`rect`、`circle`、`line`、`text`）；`path` 只用於圖示或特殊形狀。
- 不要匯出的大量路徑、不要把文字轉成外框、不要內嵌 base64 圖片。圖示要小（`<g data-component="Icon" id="Icon-Search">`），或引用素材（`<use href="icons.svg#search">`）。
- 座標使用絕對值，盡量是整數（讓 diff 穩定）。
- 檔案維持在約 60 KB 以下。再大就省不到 token 了。

## 4. 遊戲與畫布 UI

- 每個場景或 HUD 版面一份 SVG。精靈圖與圖集區域寫成 `<g data-component="Sprite" id="Player-Idle">`，並加上 `data-note="atlas: chars.png 0,0,64,64; anchor bottom-center"`。
- 動畫部分：把關鍵影格畫成狀態（`data-state="frame-1"`…），並在 `data-note` 註明時間。
- SVG 裡的圖層順序就是引擎裡的 z-order；請在專案 CLAUDE.md 的對照表註明。

## 5. Quick Edit reference

從預覽頁複製的修改請求，用下列語法指出設計稿的位置。路徑相對於執行 `svg_preview.py` 的資料夾，加 `--absolute-paths` 時為絕對路徑。

| 形式 | 意義 |
|---|---|
| `design/login.svg#SignInButton` | 一個元件 |
| `design/login.svg#SignInButton,RememberMe` | 一起選取的多個元件；`#` 後面以逗號拆分（id 不含逗號） |
| `design/login.svg#SignInButton?state=hover` | 不是預設狀態；`?state=` 放最後，套用到整行 |
| `design/login.svg#region(480,600,320,40)@LoginCard` | 區域的 SVG 座標（四捨五入成整數）與所在元件。每個區域獨立一行 |

跨檔案選取時，每個檔案一行。`Snapshot JSON (svg_render.py --job)` 區塊可重現使用者看到的畫面：`view.visible` 是 SVG 座標的 `[x, y, w, h]`，`selection` 含 `ref`、`kind`、`path`、`bbox`。跨檔案時它是清單，每個檔案一個 job。

## 6. Agent 讀什麼、人看什麼

- 人審閱的是**渲染結果**，絕不是 XML。
- 實作元件的 agent **只讀該元件**：它在 `<name>.components.md` 的那一列，加上 `svg_render.py --component <Id>` 的輸出或 `<g>` 子樹。絕不要把整份 SVG 貼進每個 subagent 的提示，token 就是這樣省下來的。
