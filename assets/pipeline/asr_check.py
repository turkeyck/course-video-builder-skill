"""回聽檢查：用語音辨識（SenseVoice，sherpa-onnx，離線）把每一段旁白的合成音檔轉回文字，
和「送給 TTS 的文字」比對，特別檢查英文、縮寫和專有名詞有沒有唸對。

用法：python asr_check.py [0 1 2 ...]     （不給檔號＝全部）
輸出：out/ASR_REPORT.md（每段一列：字幕、送給 TTS 的文字、辨識結果、疑似唸錯的英文詞）
"""
import difflib, importlib, pathlib, re, sys
import numpy as np, soundfile as sf, sherpa_onnx

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from lib import tts  # noqa: E402

MODEL = pathlib.Path.home() / "tts_models_2025" / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09"
rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(
    model=str(MODEL / "model.int8.onnx"), tokens=str(MODEL / "tokens.txt"),
    num_threads=4, use_itn=False, language="auto")


def recognize(mp3):
    x, sr = sf.read(str(mp3), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    st = rec.create_stream()
    st.accept_waveform(sr, x)
    rec.decode_stream(st)
    return st.result.text


def english_terms(spoken):
    """送給 TTS 的英文詞。同一段英文裡連續的單一字母（F D T D）合成一個縮寫，中文隔開的不合併。"""
    out = []
    for chunk in re.findall(r"[A-Za-z][A-Za-z0-9+ ]*", spoken):
        run = []
        for w in chunk.split() + [""]:
            if len(w) == 1:
                run.append(w); continue
            if run:
                out.append("".join(run)); run = []
            if w:
                out.append(w)
    return out


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def heard_ok(term, heard):
    """辨識結果的英文片段裡，有沒有和 term 相似度 ≥ 0.6 的子字串（辨識常把字母拼錯一兩個）。"""
    t = norm(term)
    if not t:
        return True
    for c in (norm(x) for x in re.findall(r"[A-Za-z0-9][A-Za-z0-9 ]*", heard)):
        for L in range(max(1, len(t) - 2), len(t) + 3):
            for i in range(0, max(1, len(c) - L + 1)):
                if difflib.SequenceMatcher(None, t, c[i:i + L]).ratio() >= 0.6:
                    return True
    return False


nos = [int(a) for a in sys.argv[1:]] or list(range(15))
lines = ["# 回聽檢查報告（SenseVoice 語音辨識）", "",
         "「疑似」＝送給 TTS 的英文詞（兩個字母以上）在辨識結果的英文片段裡找不到相似的拼法（相似度 < 0.6）。辨識常把唸對的英文寫成中文同音字（CUDA → 酷的、pi → 派、Yee → 一），這些也會被列為疑似。辨識本身也會出錯，所以這只是篩選，要再人工判斷。", ""]
total = flagged = 0
for no in nos:
    lec = importlib.import_module(f"lectures.L{no:02d}").LEC
    says = [b.say for s in lec.slides for b in s.beats]
    lines += [f"## L{no:02d} {lec.title}", "", "| 段 | 送給 TTS 的文字 | 辨識結果 | 疑似 |", "|---|---|---|---|"]
    for i, say in enumerate(says, 1):
        sp = tts.spoken(say)
        mp3 = tts.CACHE / f"{tts._key(sp, '-6%')}.mp3"
        if not mp3.exists():
            lines.append(f"| {i} | {sp} | （找不到音檔） | — |"); continue
        heard = recognize(mp3)
        miss = [t for t in english_terms(sp) if len(t) > 1 and not heard_ok(t, heard)]
        total += 1; flagged += bool(miss)
        lines.append(f"| {i} | {sp} | {heard} | {'、'.join(miss) if miss else ''} |")
    lines.append("")
    print(f"L{no:02d} done", flush=True)
lines.insert(4, f"共 {total} 段，{flagged} 段有疑似。")
(ROOT / "out" / "ASR_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
print("wrote out/ASR_REPORT.md", total, flagged)
