# 讀音回聽指南

## 工具

- `asr_check.py`：用離線 SenseVoice（sherpa-onnx int8，模型放在 `~/tts_models_2025/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09/`）把每段快取的 mp3（`build/audio/{sha1(VOICE|rate|spoken)[:20]}.mp3`）轉回文字，抽出送給 TTS 的英文詞（同一段英文裡的單一字母合併成縮寫），在辨識結果的英文片段裡找相似度 ≥ 0.6 的拼法，找不到就列為「疑似」。
- 模型不在時：從 sherpa-onnx 的 GitHub releases 下載同名模型（先問使用者，下載屬於需要同意的動作）。
- 用法：`python asr_check.py`（全部）或 `python asr_check.py 1 6`；報告 `out/ASR_REPORT.md`。

## 判讀

疑似項分三類：

1. **同音字寫法（唸對了）**：辨識器把英文寫成中文，例如 CUDA → 酷的、pi → 派、kappa → 卡吧、Yee → 一。不用改。
2. **真的唸錯**：要修。過去實際遇到的：
   - 讀音表的縮寫比對到單字內部（`TF` 比對到 `PYTHONUTF8`）→ `_LEX_RE` 對純英數的鍵加了單字邊界，保留這個寫法。
   - 小寫程式名照拼音唸：numpy → 南比。加 `LEX`：`"numpy": "Num Pie"`、`"rcwa": "R C W A"`、`"memcpy": "mem copy"`、`"dim3": "dim three"`。
   - 單位縮寫：eV → `e V`、KB → `kilobytes`。
   - 帶重音符號的名字：Ampère → `Ampere`。
   - 中文數字＋英文量詞被聽成別的數：「四 byte」→ 四百 → 改 `四個 byte`；「sine 平方」→ 三平方 → 改 `sine squared`；「乘 sine theta」→ `sine of theta`。
3. **辨識器偏差、無法確定**：短的人名（Mur、Fourier）在中文句子裡常被寫成中文。試過幾種拼法沒變好就不改，列給使用者親耳聽。

## 修法的選擇

- 整門課都會出現的詞 → 加到 `lib/tts.py` 的 `LEX`（只影響送 TTS 的文字，字幕不變）。改完 `LEX` 會改變快取 key，**所有含這個詞的影片都要重建**：用 `grep` 找出哪些 `lectures/Lxx.py` 含該詞，再 `python make.py …`。
- 只有一處 → 在腳本和 lectures 同時寫 `{字幕|唸法}`。
- 想先試聽：寫小程式只呼叫 `tts.synth_all([文字])` 再用 `asr_check.recognize()` 看結果，比重建整支快。
- 改完一定再跑 `verify_videos.py`（確保字幕沒變）和 `asr_check.py`（確認已修好）。

## 回報

列出：檢查段數、疑似段數、修了哪些詞（原本聽成什麼 → 現在怎麼唸）、重建了哪幾支、仍不確定而建議親耳聽的段落（給影片檔號）。
