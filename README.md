# course-video-builder-skill

A self-learning video builder tailored for each curious mind.

A Claude Code skill that turns "I want to learn X for goal Y" into a personal course: a diagnostic quiz, a learning plan built from the results, hand-holding handouts with runnable code, five independent reviewers, and narrated lecture videos (slides + Mandarin TTS + subtitles), all checked by machine before delivery.

> 以下為繁體中文說明。

## 它做什麼

告訴 Claude 你想學什麼、目標是什麼，這個 skill 會：

1. **測你的程度**：把主題拆成技能節點，出一份診斷測驗（選擇、簡答、讀程式、計算），依作答結果判斷每個節點是「已掌握／半懂／缺」。
2. **排學習計畫**：只排你缺的和半懂的，依前置關係排序、配合你每週的時間，每週一個可驗收的成果。你同意後才開始做課程。
3. **寫手把手講義**：每一步都有程式碼、逐行解釋、執行指令和**實際跑出來的輸出**，加上常見錯誤和附解答的練習。
4. **五位獨立審查**：數字、物理推導、程式、教學設計、引用一致性，各由一個 subagent 審查，修正後再確認一輪。
5. **做教學影片**：每支先寫大綱和腳本，再由 Sonnet subagent 轉成投影片影片（KaTeX 公式、逐段出現、曉臻 TTS 旁白、內嵌字幕）。
6. **機器驗收**：檢查每支影片的格式和音畫同步、旁白和腳本逐段一致、用語音辨識回聽英文與專有名詞的讀音。
7. **結業後測**：用同一份技能地圖出平行題，比較學習前後的掌握度。

## 觸發方式

在 Claude Code 裡直接說，例如：

- 「我想學 RCWA，目標是半年內能自己寫出來並在面試講清楚，每週 8 小時。」
- 「先測我的程度再排學習計畫，然後做講義和影片。」
- 「根據這份學習進度表做手把手課程。」（已有進度表時可跳過測驗）
- 「重建第 6 支影片」「回聽檢查讀音」（只跑後段流程）

不適用：軟體操作錄影／UI 教學、單份簡報、只問一個概念。

## 安裝

把這個 repo clone 到 Claude Code 的 skills 資料夾：

```bash
git clone https://github.com/turkeyck/course-video-builder-skill ~/.claude/skills/course-video-builder
```

### 影片管線的需求

| 需求 | 用途 |
|---|---|
| Python 3（以 3.14 測試過）：`pip install edge-tts playwright av numpy pillow imageio-ffmpeg soundfile sherpa-onnx` | TTS、投影片截圖、影片合成、回聽 |
| Microsoft Edge（Playwright 用系統 Edge） | 把投影片 HTML 截成 1920×1080 PNG |
| Node.js（在 `tools/` 執行 `npm i`） | KaTeX 公式 |
| 網路 | edge-tts 線上合成（有快取，重建不會重複合成） |
| SenseVoice 模型（sherpa-onnx int8，可選） | 讀音回聽檢查 |

## 流程與產出

| 步驟 | 內容 | 產出 |
|---|---|---|
| 1 | 確認主題、目標、時間 | `計畫/需求.md` |
| 2 | 技能地圖＋診斷測驗 | `計畫/技能地圖.md`、`診斷_題目／答案／結果.md` |
| 3 | 學習計畫（需你同意） | `計畫/學習計畫.md` |
| 4–5 | 規劃、寫講義與程式 | `講義/*.md`、`code/` |
| 6 | 五位審查兩輪 | `reviews/` |
| 7 | 影片大綱與腳本 | `course_videos/scripts/V*.md` |
| 8 | Sonnet 生成影片 | `course_videos/out/*.mp4` |
| 9 | 旁白 vs 腳本、QA | `out/VERIFY_REPORT.md` |
| 10 | 語音辨識回聽讀音 | `out/ASR_REPORT.md` |
| 11 | 收尾、後測 | 課程總覽、`計畫/後測_結果.md` |

管線常用指令（在 `course_videos/` 下）：

```bash
python make.py 3 4          # 建置第 3、4 支影片
python verify_videos.py     # 驗收：旁白一致、QA、總長
python asr_check.py 6       # 回聽第 6 支的讀音
```

## Repo 結構

```
SKILL.md                     # skill 本體：觸發條件、11 步流程、規則、輸出格式
references/
  diagnostic-and-plan.md     # 診斷測驗與學習計畫
  handout-and-review.md      # 講義結構與五位審查分工
  script-format.md           # 影片腳本格式
  render-and-qa.md           # 管線設置、派 Sonnet 生成、驗收
  pronunciation-check.md     # 讀音回聽與讀音表
  readiness_report.md        # skill 檢查紀錄
assets/
  pipeline/                  # 影片管線（複製到課程的 course_videos/ 使用）
  evals/                     # 觸發與功能測試案例
examples/ schemas/ policies/ skill_lifecycle.yaml   # skill 維護用的範例與規格
```

## 設計原則

- **先診斷再排課**：不假設學習者會什麼，起點由測驗決定。
- **數字都實際跑過**：講義和旁白裡的每個數字都來自實際執行的程式。
- **審查通過才做影片**；影片一律先有腳本。
- **英文唸英文**：專有名詞、縮寫、希臘字母不用中文音譯，並用語音辨識回聽確認。
- **不覆蓋舊版**：改版一律開新資料夾。

## 注意

- 影片旁白是 AI 合成語音（Microsoft Edge 曉臻），每頁頁腳與影片 metadata 都有標示。
- Claude Code 載入 skill 時只讀 `SKILL.md`；這份 README 是給 GitHub 讀者看的。
