<h1 align="center">svg-ui-bridge</h1>

<p align="center">讓 Claude Code 先畫出 SVG 設計稿、經你核准再寫程式，最後用像素比對證明成品符合設計。</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="skills/svg-ui-bridge/SKILL.md">工作流程</a> ·
  <a href="skills/svg-ui-bridge/references/svg-conventions.md">SVG 規範</a> ·
  <a href="skills/svg-ui-bridge/references/framework-mapping.md">框架對照</a> ·
  <a href="skills/svg-ui-bridge/references/workflow-integration.md">整合 superpowers</a> ·
  <a href="CHANGELOG.md">更新紀錄</a>
</p>

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="Claude Code plugin" src="https://img.shields.io/badge/Claude%20Code-plugin-D97757">
  <a href="https://github.com/ETEason/svg-ui-bridge/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/ETEason/svg-ui-bridge/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-green"></a>
</p>

<p align="center">
  <img alt="瀏覽器預覽頁：左側元件樹選中 SearchButton，右側設計稿標出對應位置" src="docs/images/preview-page.png" width="800">
</p>

只用文字描述畫面時，人和 AI 很容易各想各的，等程式寫完才發現不對。這個 skill 把 SVG 當成共同語言：你看渲染出來的畫面，Claude 讀有命名、有分層的標記，所以修改發生在設計稿上，而不是反覆重寫程式。

## ✨ 功能

| 階段 | 做什麼 | 工具 |
|---|---|---|
| 1. 繪製 | 把畫面寫成結構化 SVG：每個元件有名稱，顏色與間距是設計 token，hover、disabled 等狀態是獨立圖層 | Claude 依 [SVG 規範](skills/svg-ui-bridge/references/svg-conventions.md) 撰寫 |
| 2. 檢查與核准 | 檢查規範，在瀏覽器即時預覽；**你核准前不寫產品程式** | `svg_lint.py`、`svg_preview.py`、`svg_render.py` |
| 3. 拆解 | 產生元件清單：樹狀結構、實測位置大小、token、狀態、建議實作順序 | `svg_manifest.py` |
| 4. 實作 | 從 SVG 匯出主題檔，再逐元件實作，每個任務只給該元件的資料以節省 token | `tokens_export.py` |
| 5. 驗證 | 把實際畫面截圖與設計稿比對，整體與每個元件都要過門檻（預設整體 ≤ 2%、單一元件 ≤ 10%） | `visual_diff.py` |
| 6. 後續修改 | 視覺調整一律先改 SVG，SVG 是外觀的唯一依據 | 回到階段 1 |

適用網頁，也適用 Rust egui/iced/Bevy、Qt、遊戲 HUD 等非網頁介面。可以放進 [superpowers](https://github.com/obra/superpowers) 的 brainstorming 設計步驟裡使用。

## 🚀 快速開始

安裝 plugin：

```
claude plugin install svg-ui-bridge --marketplace ETEason/svg-ui-bridge
```

安裝腳本需要的 Python 套件與算圖器：

```
python -m pip install pillow playwright
python -m playwright install chromium
```

Windows 請把 `python` 換成 `py`。需要 Python 3.10 以上。

接著開新的 Claude Code session，直接提 UI 需求，Claude 會自行載入這個 skill；也可以用 `/svg-ui-bridge:svg-ui-bridge` 手動呼叫。

> **已經有 Chrome 也要裝 Chromium 嗎？** 目前要。腳本用 Playwright 自己管理的瀏覽器，不會去找系統的 Chrome。不想裝的話，改裝 resvg（`cargo install resvg`），它不需要瀏覽器，而且腳本會優先使用。但網頁專案仍建議用 Playwright，因為參考圖和你的 App 由同一種引擎算圖，文字誤差較小（設定 `SVG_UI_RENDERER=playwright`）。

<details>
<summary>其他安裝方式</summary>

舊版 Claude Code 用兩步驟安裝：

```
claude plugin marketplace add ETEason/svg-ui-bridge
claude plugin install svg-ui-bridge@svg-ui-bridge
```

固定在某個版本：

```
claude plugin marketplace add ETEason/svg-ui-bridge#v0.1.0
```

更新：

```
claude plugin update svg-ui-bridge@svg-ui-bridge
```

讓整個專案的人共用（也適用雲端 session），在該 repo 執行一次，再 commit `.claude/settings.json`：

```
claude plugin marketplace add ETEason/svg-ui-bridge --scope project
```

其他 agent 或沒有 plugin 系統時：

```
npx skills add ETEason/svg-ui-bridge
```

也可以手動把 `skills/svg-ui-bridge/` 複製到 `<專案>/.claude/skills/` 或 `~/.claude/skills/`。擇一安裝就好，不要重複。

</details>

<details>
<summary>安裝後的選用設定</summary>

1. 要讓所有專案的 UI 工作都走這個流程：把 `skills/svg-ui-bridge/templates/global-CLAUDE.md.snippet` 附加到 `~/.claude/CLAUDE.md`。這會讓小改動也要先畫 SVG。
2. 個別專案：把 `templates/project-CLAUDE.md.template` 貼進專案的 `CLAUDE.md` 並填好，再把 `templates/gitignore.snippet` 加進 `.gitignore`。

</details>

## 🔒 安全性

- plugin 不含 hooks、MCP server 或執行檔。lint hook 是選用的，要自己加才會執行。
- 腳本本身只讀寫本機檔案，執行時不會下載或上傳。`svg_preview.py --serve` 只綁定 `127.0.0.1`。
- **不要用預覽頁開來源不明的 SVG。** 預覽頁會把 SVG 內容直接放進網頁，惡意 SVG 可能在頁面裡執行 JS 或連到外部網址。
- 安裝任何 skill 前都建議先看過程式碼，也可以固定 tag，只在你決定時才更新。

## 🧪 開發

```
git clone https://github.com/ETEason/svg-ui-bridge.git
cd svg-ui-bridge
python tests/smoke_test.py
```

結尾應顯示 `ALL SMOKE TESTS PASSED`。沒有裝算圖器時可加 `--no-render` 跳過算圖檢查。CI 會在 Ubuntu 與 Windows 上用 Python 3.10、3.13 執行同一份測試。

<details>
<summary>專案結構</summary>

| 路徑 | 用途 |
|---|---|
| `.claude-plugin/` | plugin 與 marketplace 設定 |
| `skills/svg-ui-bridge/SKILL.md` | Claude 遵循的工作流程（6 個階段、關卡、常見錯誤想法） |
| `skills/svg-ui-bridge/references/` | SVG 規範、superpowers/pstack 整合、SVG 到各框架的對照 |
| `scripts/svg_lint.py` | 檢查 SVG 是否符合規範 |
| `scripts/svg_preview.py` | 瀏覽器預覽頁，`--serve` 會在 SVG 變更時自動重新載入 |
| `scripts/svg_render.py` | 輸出 PNG 給 Claude 自我檢查（可指定狀態或單一元件） |
| `scripts/svg_manifest.py` | 產生元件清單與實作順序 |
| `scripts/tokens_export.py` | 匯出 token 為 CSS、TS、egui、Bevy 或 JSON |
| `scripts/visual_diff.py` | 比對截圖與設計稿，輸出差異圖與結束碼 |
| `scripts/lint_hook.py` | 選用的 PostToolUse hook，自動檢查 Claude 寫出的 SVG |
| `tests/smoke_test.py` | 端對端冒煙測試 |

`scripts/` 都在 `skills/svg-ui-bridge/` 底下。

</details>

## 📚 文件

- [工作流程](skills/svg-ui-bridge/SKILL.md)：每個階段的完整步驟與關卡
- [SVG 規範](skills/svg-ui-bridge/references/svg-conventions.md)：設計稿該怎麼寫
- [框架對照](skills/svg-ui-bridge/references/framework-mapping.md)：SVG 屬性如何對應到各框架
- [整合 superpowers 與 pstack](skills/svg-ui-bridge/references/workflow-integration.md)：為什麼放在設計階段，以及各階段怎麼銜接

以上文件目前都是英文。

## ⚠️ 限制

- **Windows 不支援萬用字元**：PowerShell 和 cmd 不會展開 `design/*.svg`。`svg_lint.py` 請逐檔傳入，`svg_preview.py` 請傳資料夾，例如 `svg_preview.py design`。
- **文字不會完全一致**：不同算圖器與原生 UI 工具的字型渲染不同，所以 `visual_diff.py` 有容差設定，文字請看位置和大小，不要追求逐像素相同。
- **`visual_diff.py` 需要你提供截圖**：截圖要和 SVG 畫布是同一區域。

## 📄 授權

[MIT](LICENSE)
