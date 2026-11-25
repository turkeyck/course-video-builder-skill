# 生成與驗收指南

## 管線檔案

| 檔案 | 用途 |
|---|---|
| [make.py](../assets/pipeline/make.py) | `python make.py N` 建一支影片；擋 LaTeX 控制字元 |
| [verify_videos.py](../assets/pipeline/verify_videos.py) | 旁白 vs 腳本、QA、總長 → `out/VERIFY_REPORT.md` |
| [asr_check.py](../assets/pipeline/asr_check.py) | SenseVoice 回聽 → `out/ASR_REPORT.md` |
| [lib/spec.py](../assets/pipeline/lib/spec.py) | lecture 檔的詞彙：`Lecture`、`S`、`B`、`T`、`LI`、`EQ`、`CODE`、`TBL`、`BOX`、`IMG`、`RAW` |
| [lib/render.py](../assets/pipeline/lib/render.py) | 投影片 HTML＋KaTeX → 每個 beat 一張 PNG（Playwright＋Edge）；`COURSE`、`CSS` 在這裡 |
| [lib/tts.py](../assets/pipeline/lib/tts.py) | edge-tts 曉臻、快取、`LEX` 讀音表、`{字幕|唸法}` |
| [lib/assemble.py](../assets/pipeline/lib/assemble.py) | 時間軸、ffmpeg 片段與淡入、字幕、響度、QA 與縮圖 |
| [lib/handout.py](../assets/pipeline/lib/handout.py) | 從講義抽 LaTeX 的掛鉤（預設回傳空清單，公式直接寫在 `EQ(r"…")`） |
| [lib/__init__.py](../assets/pipeline/lib/__init__.py)、[lectures/__init__.py](../assets/pipeline/lectures/__init__.py) | 套件標記（空檔） |
| [tools/package.json](../assets/pipeline/tools/package.json) | KaTeX 依賴，`npm i` 後放在 `tools/node_modules` |

## 一次性設置（每門課）

1. 把 `assets/pipeline/` 整個複製成 `<課程>/course_videos/`（`lib/`、`lectures/__init__.py`、`make.py`、`verify_videos.py`、`asr_check.py`、`tools/package.json`）。
2. 改 `lib/render.py` 的 `COURSE`（頁首課程名）。需要不同配色時改同檔的 `CSS` `:root` 變數。
3. `cd tools && npm i`（安裝 KaTeX 到 `tools/node_modules`）。
4. Python 套件：`edge-tts playwright av numpy pillow imageio-ffmpeg soundfile sherpa-onnx`；Playwright 用系統 Edge。
5. 建 `scripts/`、`build/figs/`（講義的圖複製進來給 `IMG(name)` 用）。

選完整版時，資料夾用 `course_videos_full/`，再把 `assets/pipeline_full/` 疊上去（蓋過 `lib/render.py`），見 [影片篇幅](video-scope.md)。

## 派 Sonnet 生成（主線版）

- 用 Agent 工具，`model: "sonnet"`、`effort: "high"`，在同一則訊息平行派 3–5 個，每個負責 3–4 支（不要兩個 agent 同時寫同一支 `Lxx.py`；`lib/` 誰都不准改，有需要回報給主 agent）。
- brief 內容：
  - 課程資料夾、負責的檔號、腳本路徑。
  - 「把 `scripts/Vxx_*.md` 逐字轉成 `lectures/Lxx.py`：`from lib.spec import *`、`LEC = Lecture(no, slug, title, subtitle, [], code=…)`、`LEC.slides = [S(..., beats=[B(旁白, 畫面...)])]`；旁白必須和腳本逐字一致。」
  - 「LaTeX 一律用 raw string `r"…"`（否則 `\f`、`\t` 變控制字元，make.py 會擋）。」
  - 「執行 `python make.py N`；若 overflow 警告，縮小 `cls`、拆頁或改兩欄，但不改旁白。看 `out/qa/Lxx_*_slides.png` 確認版面。」
  - 「完成標準：`qa.pass` 為 true；回報每支長度、beats 數、改過什麼版面。」
- 用量用完被中斷時，用 SendMessage 讓同一個 agent 接續，不要重派。

## 驗收

- `make.py` 印出的 QA：h264＋aac、1 條字幕、音畫差 ≤ 500 ms、沒有 overflow → `pass`。
- `verify_videos.py`：每支旁白逐段等於腳本、QA 通過、彙整總長；輸出 `out/VERIFY_REPORT.md`，有問題 exit 1。
- overflow 檢查量不到手寫 `RAW(...)` 區塊，那些頁要人工看 `qa/*_slides.png`。
- 每支輸出：`.mp4`（內嵌字幕＋AI 聲音揭露）、`_script.md`（含時間碼）、`_qa.json`、`_tts_manifest.json`。

## 常見問題

| 症狀 | 原因 | 修法 |
|---|---|---|
| `control characters in lecture source` | LaTeX 沒用 raw string | 改 `r"…"` |
| verify 顯示「N 段不同」 | lectures 和腳本的旁白不一致（含全形標點） | 以腳本為準改 lectures，或兩邊一起改 |
| TTS 卡住或 empty audio | edge-tts 網路 | 內建重試 5 次；仍失敗就稍後重跑（有快取，不會重合成已完成段落） |
| 半途中斷的影片讓 verify 崩潰 | 缺 `_qa.json` | verify 會標「未建置」，重跑 `make.py N` |
