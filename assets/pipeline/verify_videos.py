"""影片驗收：(1) 每支影片的旁白是否逐句等於腳本的「旁白」；(2) QA 是否通過；(3) 彙整長度。
用法：python verify_videos.py        → 輸出 out/VERIFY_REPORT.md，全部通過時 exit 0"""
import importlib, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from lib import tts  # noqa: E402

rows, bad = [], 0
for sp in sorted((ROOT / "scripts").glob("V[0-9][0-9]_*.md")):
    no = int(sp.name[1:3])
    txt = sp.read_text(encoding="utf-8")
    want = [m.strip() for m in re.findall(r"^- 旁白：(.+)$", txt, flags=re.M)]
    lp = ROOT / "lectures" / f"L{no:02d}.py"
    if not lp.exists():
        rows.append((no, sp.stem, "—", "—", "缺少 lectures 檔", "—")); bad += 1; continue
    lec = importlib.import_module(f"lectures.L{no:02d}").LEC
    got = [tts.caption(b.say).strip() for s in lec.slides for b in s.beats]
    diffs = []
    for i in range(max(len(want), len(got))):
        w = want[i] if i < len(want) else "（無）"
        g = got[i] if i < len(got) else "（無）"
        if w != g:
            diffs.append(i + 1)
    qa_files = list((ROOT / "out").glob(f"L{no:02d}_*_qa.json"))
    if qa_files:
        qa = json.loads(qa_files[0].read_text(encoding="utf-8"))
        dur, ok, ov = qa["container_duration_s"], qa["pass"], qa.get("overflow_warnings", [])
    else:
        dur, ok, ov = None, False, "未建置"
    narr = "一致" if not diffs else f"{len(diffs)} 段不同（第 {diffs[:8]} 段）；腳本 {len(want)} 段、影片 {len(got)} 段"
    if diffs or not ok:
        bad += 1
    rows.append((no, getattr(lec, "code", ""), f"{dur / 60:.1f} 分" if dur else "—", "通過" if ok else "未通過", narr,
                 f"{len(lec.slides)} 頁 / {len(got)} 段"))

total = sum(json.loads(p.read_text(encoding="utf-8"))["container_duration_s"] for p in (ROOT / "out").glob("L*_qa.json"))
lines = ["# 影片驗收報告", "", f"總長：{total / 60:.1f} 分鐘；有問題的影片：{bad} 支", "",
         "| 檔號 | 代號 | 長度 | QA | 旁白 vs 腳本 | 投影片／旁白段 |", "|---|---|---|---|---|---|"]
lines += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |" for r in rows]
(ROOT / "out" / "VERIFY_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
sys.exit(1 if bad else 0)
