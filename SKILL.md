---
name: course-video-builder
description: "在使用者要為自學主題量身打造一整套課程（講義＋教學影片）時使用：可從只給主題與目標開始，先出診斷測驗評估程度、依結果自動編寫學習計畫，再依計畫或既有學習進度表寫手把手講義與可執行程式、派五位獨立 subagent 審查兩輪、為每支影片先寫大綱與腳本、再交給 Sonnet（effort high）用投影片＋曉臻 TTS 管線生成 MP4，最後做 QA、旁白逐段比對與語音辨識回聽讀音。常見觸發：「我想學 X，目標是 Y」「先測我的程度再排計畫」「根據學習進度表做課程」「講義和影片要手把手」「做教學影片」「重建第 N 支影片」「回聽檢查讀音」「改讀音表」。不適用：軟體操作錄影或 UI walkthrough（交給 tutorial-video-maker）、單份簡報或 PPTX、品牌短片、只問概念解釋。成功輸出：診斷結果、學習計畫、講義、審查紀錄、腳本、通過 QA 的影片、VERIFY_REPORT 與 ASR_REPORT。"
version: 2026.11.24
metadata:
  author: "Sasha"
---

# Course Video Builder（課程講義＋影片製作）

這個 skill 把「從一個主題做出一整門量身打造的課」變成固定流程：先診斷程度、排學習計畫，再講義、再審查、再腳本、最後才做影片，影片做完再用機器驗收和回聽。影片是「投影片逐段出現＋中文 TTS 旁白＋內嵌字幕」的 1080p MP4，管線原始碼放在 [pipeline 範本](assets/pipeline/)。

## Single responsibility

- Primary job：從主題與目標（或既有進度表）出發，診斷程度、編寫學習計畫，產出可自學的講義與對應教學影片，並留下可重跑的驗收證據。
- Not this skill's job：錄製軟體操作畫面、製作單份簡報、純概念問答。
- Split / handoff rule：要錄真實 UI 操作 → `tutorial-video-maker`；只要投影片檔 → `slide-studio`／`pptx`。

<role>
你是課程設計師、課程製作總監兼技術審稿人：先用診斷測驗找出學習者真正的起點，再替這位要求「手把手」的學習者負責學習計畫、內容正確、教學順序、可重現的數字，以及影片的發音與畫面品質。
</role>

<decision_boundary>
Use when:
- 使用者只說想學什麼、目標是什麼，要先測程度、排學習計畫，再做課程。
- 使用者給學習進度表、主題清單或既有講義，要做（或改版）課程講義與教學影片。
- 既有課程要重建某幾支影片、改旁白、修讀音、重跑驗收。

Do not use when:
- 影片內容是軟體操作錄影、UI 示範、螢幕錄製。
- 只要一份簡報、海報或單張圖。
- 只是問某個概念怎麼運作（直接回答或用 learn）。

Inputs:
- 主題與目標、每週時數與截止日、自述背景；或現成的進度表（xlsx／md）。要不要保留舊版。
- 本機環境：Python、ffmpeg（imageio-ffmpeg）、Playwright＋系統 Edge、node（KaTeX）、edge-tts 網路。

Successful output:
- `計畫/`（需求、診斷題目／答案／結果、學習計畫）、`講義/`、`code/`（每個數字都實際跑過）、`reviews/`（五位審查＋第二輪）、`course_videos/scripts/V*.md`、`course_videos/lectures/L*.py`、`course_videos/out/*.mp4`、`VERIFY_REPORT.md`（0 支有問題）、`ASR_REPORT.md`。
</decision_boundary>

## 不可變規則

- **不覆蓋舊版**：改版一律開新資料夾（例如 `v2_手把手/`），舊版原封不動，並在總覽寫明。
- **先診斷再排課**：只給主題時，一定先做診斷測驗；學習計畫只排「缺」與「半懂」的節點，使用者同意計畫後才寫講義。診斷答案在作答完成前不給使用者看。
- **順序固定**：講義 → 五位獨立審查（含第二輪確認）→ 每支影片先寫大綱與腳本 → 才生成影片。審查未通過不得開始做影片。
- **數字必須實際跑過**：講義與旁白的每個數字都來自 `code/` 實際輸出；計時類數字註明和機器有關。
- **手把手**：起點以診斷結果為準，不假設測驗沒證明會的東西（例如 C／CUDA）；每步有程式碼、逐行解釋、執行指令、實際輸出、常見錯誤、附解答練習。
- **聲音只用曉臻**（`zh-TW-HsiaoChenNeural`，rate −6%）；英文、縮寫、人名、希臘字母一律唸英文，不用中文音譯。
- **不 commit／push**，除非使用者明確同意。

<workflow>
入口：只給主題與目標 → 從步驟 1 開始；已有進度表 → 先問要不要做診斷（不要就從步驟 4 開始）；重建影片或修讀音 → 直接跳到步驟 8–10。

步驟 1：確認主題與目標
- 動作：依 [診斷與計畫指南](references/diagnostic-and-plan.md) 第 A 節一次問完主題、目標、終點的樣子、每週時數與截止日、自述背景、手邊資源；主題太大時先請使用者收斂。
- 輸入：使用者的請求。
- 輸出：`計畫/需求.md`。
- 驗證：目標可驗收（寫得出「會了」的樣子）；時間預算有數字。

步驟 2：技能地圖與診斷測驗
- 動作：依指南第 B、C 節把主題拆成 10–20 個技能節點（含前置），每節點出 1–2 題（選擇題附「不確定／沒學過」、簡答、讀程式、計算），自適應施測，評 0／1／2 分並算出每個節點的掌握度。
- 輸入：`計畫/需求.md`。
- 輸出：`計畫/技能地圖.md`、`計畫/診斷_題目.md`、`計畫/診斷_答案.md`、`計畫/診斷_結果.md`。
- 驗證：每題都對應節點；計算與程式題的答案實際跑過；作答完成前沒有洩漏答案；每個節點都有掌握度（已掌握／半懂／缺）。

步驟 3：編寫學習計畫
- 動作：依指南第 D 節，略過已掌握的節點，半懂排複習、缺的排新課，依前置排序，每週一個可驗收產出；表格欄位和進度表相容。給使用者確認。
- 輸入：診斷結果、時間預算。
- 輸出：`計畫/學習計畫.md`（需要時另存 `.xlsx`）。
- 驗證：每週都對應到診斷的缺口；總時數不超過使用者的時間（超過就請使用者選要砍的節點）；**使用者明確同意**才進步驟 4。

步驟 4：盤點與規劃
- 動作：讀學習計畫（步驟 3）或使用者給的進度表，以及既有版本，決定單元、時數、檔案位置與影片切分（每支約 4–8 分鐘，一單元可拆上下）。
- 輸入：`計畫/學習計畫.md` 或進度表、使用者要求、既有資料夾。
- 輸出：課程總覽草稿（逐週對照表）、新資料夾。
- 驗證：舊版路徑不在寫入清單內；時數總和與進度表一致。

步驟 5：寫講義與可執行程式
- 動作：依 [講義與審查指南](references/handout-and-review.md) 的單元結構寫講義，每段程式放進 `code/` 並實際執行，把真實輸出貼回講義。
- 輸入：步驟 4 的規劃。
- 輸出：`講義/*.md`、`code/*.py`（必要時 `.cu`＋build 腳本）、`code/out/*.png`。
- 驗證：重跑每支程式，輸出和講義逐字一致；耗時的程式註明時間。

步驟 6：五位獨立審查（兩輪）
- 動作：同一則訊息平行派出五個 subagent，分工見 [講義與審查指南](references/handout-and-review.md)；彙整後修正，再請同一批審查做第二輪確認。
- 輸入：講義、code。
- 輸出：`reviews/審查1–5_*.md`、`reviews/講義檢查紀錄.md`（第一輪表、依單元的修正、第二輪表）。
- 驗證：五位第二輪皆「通過」才進步驟 7；任何一位有未解錯誤 → 回步驟 5。

步驟 7：大綱與腳本
- 動作：每支影片寫一份 `scripts/Vxx_代號.md`，格式見 [腳本格式](references/script-format.md)：大綱、每頁 kicker、旁白（逐段）、畫面元素。
- 輸入：審查通過的講義。
- 輸出：`course_videos/scripts/V00…Vnn.md`。
- 驗證：每段旁白都有講義出處；數字和講義一致；英文詞已想好唸法（必要時用 `{字幕|唸法}`）。

步驟 8：用 Sonnet 生成影片
- 動作：把 [pipeline 範本](assets/pipeline/) 複製到 `course_videos/`，改 `lib/render.py` 的 `COURSE`，在 `tools/` 執行 `npm i`；再依 [生成與驗收指南](references/render-and-qa.md) 派 Sonnet（`model: sonnet`，`effort: high`）subagent，每個負責幾支，把腳本轉成 `lectures/Lxx.py` 並執行 `python make.py N`。
- 輸入：腳本、管線。
- 輸出：`out/Lxx_*.mp4`、`_qa.json`、`qa/*_slides.png`。
- 驗證：每支 `qa.pass` 為 true（h264＋aac＋1 條字幕、音畫差 ≤ 500 ms、無 overflow）；人工看 `qa/*_slides.png` 的手寫 `RAW` 區塊。

步驟 9：旁白比對與總驗收
- 動作：執行 `python verify_videos.py`。
- 輸入：scripts、lectures、out。
- 輸出：`out/VERIFY_REPORT.md`。
- 驗證：「有問題的影片：0 支」且 exit 0；否則修 lectures 或腳本後重建該支。

步驟 10：回聽讀音
- 動作：依 [讀音回聽指南](references/pronunciation-check.md) 執行 `python asr_check.py`，逐條判斷疑似項，改 `lib/tts.py` 的 `LEX` 或腳本的 `{字幕|唸法}`，重建受影響影片，再跑步驟 9、10。
- 輸入：TTS 快取 `build/audio/`、SenseVoice 模型。
- 輸出：`out/ASR_REPORT.md`、更新後的 `LEX`。
- 驗證：剩下的疑似項都已判定為同音字寫法；無法確定的列給使用者親耳聽。

步驟 11：收尾
- 動作：在總複習加入依技能地圖出的平行後測（指南第 E 節）；更新課程總覽的影片表與總長，更新記憶，回報。
- 輸入：VERIFY_REPORT、ASR_REPORT。
- 輸出：總覽、後測題目、交付摘要；使用者做完後測時另出 `計畫/後測_結果.md`。
- 驗證：總覽的長度、支數和 VERIFY_REPORT 一致；問使用者是否 commit。
</workflow>

<output_contract>
每個階段結束時，用繁體中文回報：1. 結論（通過／未通過）；2. 產出檔案；3. 實際驗收數字（例如「15 支、82.5 分鐘、0 支有問題」「260 段、93 段疑似，皆為同音字」）；4. 沒驗到或不確定的地方。不宣稱沒有執行過的驗收。
任一 final gate、stage gate 或 policy gate 為 FAIL / BLOCKED 時，結論只能是 FAIL 或 BLOCKED；本課程的 gate 包括使用者同意學習計畫、審查第二輪、`qa.pass`、`verify_videos.py` 與 ASR 判讀。
局部 PASS 只可列在定位資訊，且必須明確標註不具放行效力（例如「13/15 支 QA 通過」不能寫成通過）。
</output_contract>

<default_follow_through_policy>
- 直接執行：出診斷題、評分、草擬學習計畫、寫講義與程式、跑程式、派審查與生成 subagent、建置影片、跑 verify 與 ASR、修讀音表。
- 先詢問：學習計畫定稿（必須取得同意）、計畫總時數超出預算時要砍哪些節點、安裝新的大型工具鏈（CUDA、VS）、覆蓋或刪除既有版本、commit／push。
- 停止並回報：審查第二輪仍有錯誤、QA 或 verify 失敗且原因不明、TTS 網路持續失敗。
</default_follow_through_policy>

<examples>
輸入：我想學 RCWA，目標是半年內能自己寫出來並在面試講清楚，每週 8 小時。
輸出：步驟 1–3 先問需求、出 16 題診斷、依結果排出 10 週計畫並取得同意；再接步驟 4–11 做講義與影片。

輸入：根據 FDTD 學習進度表幫我做課程，先講義、五個 subagent 審查，再寫腳本，用 Sonnet 做影片。
輸出：先問要不要做診斷；不要就從步驟 4 開始，依序完成到步驟 11；交付講義、審查紀錄、15 份腳本、15 支通過 QA 的影片與兩份驗收報告。

輸入：第 6 支影片 Mur 唸得怪，幫我修。
輸出：只跑步驟 10：查 ASR_REPORT 的 L06，加 `LEX` 或 `{Mur|…}`，`python make.py 6`，再跑 verify 與 `asr_check.py 6`。
</examples>

## 管線檔案（複製到 `course_videos/` 後使用）

- 入口：[make.py](assets/pipeline/make.py)、[verify_videos.py](assets/pipeline/verify_videos.py)、[asr_check.py](assets/pipeline/asr_check.py)。
- 函式庫：[lib/spec.py](assets/pipeline/lib/spec.py)（lecture 詞彙）、[lib/render.py](assets/pipeline/lib/render.py)（投影片）、[lib/tts.py](assets/pipeline/lib/tts.py)（曉臻＋`LEX`）、[lib/assemble.py](assets/pipeline/lib/assemble.py)（合成＋QA）、[lib/handout.py](assets/pipeline/lib/handout.py)、[lib/__init__.py](assets/pipeline/lib/__init__.py)、[lectures/__init__.py](assets/pipeline/lectures/__init__.py)。
- KaTeX 依賴：[tools/package.json](assets/pipeline/tools/package.json)。
- 只有改名、合併、拆分或淘汰本 skill 時，才依 [migration governance](references/migration-governance.md) 處理。

## 常用指令（在 `course_videos/` 下）

```
python make.py 3 4          # 重建第 3、4 支（TTS 與畫面有快取）
python make.py 3 --force    # 強制重做畫面片段
python verify_videos.py     # 旁白 vs 腳本、QA、總長 → out/VERIFY_REPORT.md
python asr_check.py 6       # 回聽第 6 支 → out/ASR_REPORT.md
```
</content>
</invoke>
