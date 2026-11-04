# 把 svg-ui-bridge 放進 superpowers 與 pstack

[English](../../skills/svg-ui-bridge/references/workflow-integration.md)

svg-ui-bridge 是**設計階段**的 skill。它從不取代 superpowers 的任何階段，只決定 UI 任務的設計產物是什麼（SVG 加元件清單），以及什麼算視覺證據。

這份文件只在 superpowers 或 pstack 出現於可用 skill 清單時才適用。沒有它們時，照[工作流程](workflow.md)走，不需要安裝任何東西。在 sandbox 模式下，下文的「即時預覽」請理解為[執行環境](environments.md)說明的靜態頁。

## superpowers

下表列的是 SVG 的指令。HTML 路線的步驟相同，指令見 [HTML 設計路線](html-design.md)：元件清單由 `html_review.py` 產生，驗收時用 `visual_diff.py --manifest` 把實作截圖和 `--standalone` 基準比對。由 TSX 產生的設計，下文的「修改 SVG」指修改 TSX、主題或資料後重新建置（[元件化撰寫](component-authoring.md)）。兩條路線下，只要求設計時都以審閱過的草稿結束。

superpowers 的 brainstorming 把每個需求分類為 **spike**、**bounded** 或 **architectural**，而 architectural 路徑之後唯一交接的 skill 是 writing-plans。所以 svg-ui-bridge 必須在 brainstorming 的設計步驟*之內*執行，不能排在它之後。

| superpowers 階段 | svg-ui-bridge 增加的內容 |
|---|---|
| brainstorming — 分類 | 如果任務會改變使用者看到的東西，在路徑旁註明「UI 工作 → SVG 設計規格」。 |
| brainstorming — spike | 選用。回答「這個版面可行嗎？」時可以用拋棄式 SVG；請標明是拋棄式，不要放進 `design/`。 |
| brainstorming — bounded | UI 變更的「對話中簡短設計」＝只編輯受影響元件的 SVG，並在即時預覽中審閱。使用者核准在那裡看到的內容，就是關卡。 |
| brainstorming — architectural，「呈現設計」段落 | 每個畫面一段：寫 `design/<screen>.svg`、檢查，讓使用者在即時預覽中審閱（`svg_preview.py design --serve`，每次編輯自動重新載入）；**在 SVG 上**反覆修改直到核准。這取代 superpowers 的瀏覽器視覺輔助來處理 UI 問題：不用它，或只留給非 UI 圖表；`design/` 裡的檔案始終是依據。 |
| brainstorming — 撰寫規格 | `docs/superpowers/specs/…-design.md` 規格要有 **Visual design** 段落，連結每份 `design/*.svg`、對應的 `*.components.md` 和驗收門檻（預設整體 ≤ 2%，每個元件 ≤ 10%）。撰寫前先跑 `svg_manifest.py`。 |
| writing-plans | **每個元件一個任務**，從葉節點開始，依元件清單的實作順序。每個任務列出：元件 id、邊界框、token、狀態、data-note、要建立的檔案，以及驗收指令（`visual_diff.py … --manifest …` 與門檻）。每個畫面最後一個任務負責組裝並比對整個畫面。 |
| subagent-driven-development / executing-plans | 每個 subagent 只收到自己的清單列和 `svg_render.py --component <Id>` PNG（必要時加 `<g>` 子樹），絕不給整份 SVG。 |
| test-driven-development | 邏輯與狀態（啟用/停用規則、資料綁定、事件）用一般測試。像素還原度不是單元測試，由 visual_diff 檢查。 |
| verification-before-completion | 視覺宣稱（「符合設計」）需要 `visual_diff.py` 最新一次的 PASS 輸出，加上 `svg_lint.py` 通過。回報數字和差異圖路徑。 |
| systematic-debugging | 遇到「看起來不對」的 bug，差異熱度圖和各元件百分比是第一手證據。 |

### 實作之後的視覺變更

任何「卡片寬一點、換個顏色」這類需求都先改 SVG：
編輯 SVG → 檢查 → 算圖 → 使用者核准 → 重新產生元件清單 → 更新程式 → visual_diff。
只有純行為變更可以略過 SVG。

## pstack

pstack 的 `create-verification-skill` 會產生專案本地的 skill（例如 `.claude/skills/verify/` 或 `verify-<app>/`），用來啟動實際的 App、像使用者一樣操作並收集證據。這正是 visual_diff 需要的截圖來源。

1. 每個專案執行一次 `/create-verification-skill`。它詢問 repo 時，告訴它：
   *「證據必須包含 `design/` 裡每個畫面的截圖，視窗尺寸依 SVG 的 data-target，裁切到畫布範圍，存到 `shots/<screen>.png`，再用 `python <skill>/scripts/visual_diff.py design/<screen>.svg shots/<screen>.png --manifest design/<screen>.components.json` 比對。」*
2. 之後每個 UI 任務的驗證步驟 = 執行專案的驗證 skill。
3. 新增畫面或 App 啟動流程改變時，執行 `/maintain-verification-skill`，讓截圖步驟與 `design/` 資料夾保持一致。

## Claude Code hooks（選用，具確定性）

Skill 是依判斷載入的；hook 則一定會執行。要檢查 agent 寫到 `design/` 底下的每份 SVG，在 `.claude/settings.json`（專案）或 `~/.claude/settings.json` 加入：

```json
{
  "hooks": {
    "PostToolUse": [
      { "matcher": "Write|Edit",
        "hooks": [ { "type": "command",
                     "command": "python \"$CLAUDE_PROJECT_DIR/.claude/skills/svg-ui-bridge/scripts/lint_hook.py\"" } ] }
    ]
  }
}
```

`lint_hook.py` 從 stdin 讀取 hook JSON，忽略所有不是 `design/**/*.svg` 的檔案；SVG 違反規則時以結束碼 2 退出，並把檢查錯誤寫到 stderr，Claude Code 會回饋給 agent。上面的路徑假設 skill 已 commit 進專案。如果裝在 `~/.claude/skills/` 或以 plugin 安裝，請把指令指向該份的 `scripts/lint_hook.py`（skill 載入時 Claude Code 會顯示它的基底目錄；可請 agent 提供絕對路徑）。
plugin 刻意不自行註冊這個 hook，所以除非你自己加入，否則不會在你的電腦上執行任何東西。
