"""把 講義/W*.md 切成有編號的單位（句子、公式、表格列、程式、輸出、練習……）。
腳本用 `> 12-15` 引用；compile.py 檢查每個單位都上了畫面。
python units.py 1        列出 W1 的單位"""
import pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parent
HAND = ROOT.parent / "講義"
WEEKS = sorted(int(re.match(r"W(\d+)", f.name)[1]) for f in HAND.glob("W[0-9]*_*.md"))
assert not WEEKS or max(WEEKS) <= 9, "檔號是週次×10＋第幾講，目前只支援 W1–W9"


def sentences(s):
    """在 $…$、`…` 與括號外的「。」切句；∎、右括號、引號黏在前一句。"""
    out, cur, math, tick, depth = [], "", False, False, 0
    for i, ch in enumerate(s):
        cur += ch
        if ch == "$":
            math = not math
        elif ch == "`":
            tick = not tick
        elif not math and not tick:
            if ch in "（(「":
                depth += 1
            elif ch in "）)」":
                depth = max(0, depth - 1)
            elif ch == "。" and depth == 0:
                rest = s[i + 1:]
                if cur.strip() in ("*證明。", "*證明（反證）。"):
                    continue
                if rest[:1] in "*∎" and rest[:1]:
                    continue
                out.append(cur); cur = ""
            elif ch == "∎":
                out.append(cur); cur = ""
    if cur.strip():
        if out and len(cur.strip()) <= 1:
            out[-1] += cur
        else:
            out.append(cur)
    return [x.strip() for x in out if x.strip()]


def units(week):
    f = next(HAND.glob(f"W{week}_*.md"))
    L = f.read_text(encoding="utf-8").split("\n")
    res, i, para, sec = [], 0, 0, ""

    def add(kind, text, **kw):
        res.append(dict(id=len(res) + 1, kind=kind, text=text, para=para, sec=sec, **kw))

    while i < len(L):
        ln = L[i]
        para += 1
        if not ln.strip():
            i += 1; continue
        if ln.startswith("#"):
            sec = ln.lstrip("# ").strip(); i += 1; continue
        if ln.startswith("```"):
            lang = ln[3:].strip(); j = i + 1
            while not L[j].startswith("```"):
                j += 1
            add({"python": "code", "py": "code", "c": "code", "cpp": "code", "cuda": "code", "text": "out", "": "out"}.get(lang, "cmd"), "\n".join(L[i + 1:j])); i = j + 1; continue
        if ln.startswith("$$"):
            j = i; buf = ln
            while buf.count("$$") < 2:
                j += 1; buf += "\n" + L[j]
            m = re.match(r"\$\$(.*?)\$\$(.*)$", buf, re.S)
            add("eq", m[1].strip())
            if m[2].strip():
                for s in sentences(m[2]):
                    add("t", s)
            i = j + 1; continue
        if ln.startswith("!["):
            add("img", pathlib.Path(re.search(r"\(([^)]+)\)", ln)[1]).stem); i += 1; continue
        if ln.startswith("|"):
            rows = []
            while i < len(L) and L[i].startswith("|"):
                rows.append(L[i]); i += 1
            split = lambda r: [c.strip() for c in re.split(r"(?<![\\])\|", re.sub(r"\$[^$]*\$", lambda m: m[0].replace("|", "\x01"), r))[1:-1]]
            rows = [[c.replace("\x01", "|").replace(chr(92) + "|", "|") for c in split(r)] for r in rows]
            for r in rows[2:]:
                add("row", r, head=rows[0])
            continue
        if ln.startswith(">"):
            for s in sentences(ln.lstrip("> ")):
                add("quote", s)
            i += 1; continue
        m = re.match(r"^\s*- (\[ \] )?(.*)$", ln)
        if m:
            for s in sentences(m[2]):
                add("todo" if m[1] else "li", s)
            i += 1; continue
        m = re.match(r"^(\d+)\. (.*)$", ln)
        if m:
            buf = m[2]
            while i + 1 < len(L) and L[i + 1].startswith("   "):
                i += 1; buf += " " + L[i].strip()
            sol = any(r["sec"] == sec and r["kind"] == "t" and r["text"].startswith("**解答") for r in res) or "答案" in sec
            add("ex", buf, n=int(m[1]), sol=sol); i += 1; continue
        buf = ln
        # 段落可能接 $$：另起
        for s in sentences(buf):
            add("t", s)
        i += 1
    return res


if __name__ == "__main__":
    sec = None
    for u in units(int(sys.argv[1])):
        if u["sec"] != sec:
            sec = u["sec"]; print(f"\n## {sec}")
        t = u["text"] if isinstance(u["text"], str) else " | ".join(u["text"])
        if u["kind"] in ("code", "out"):
            t = f"[{len(t.splitlines())} 行] " + t.splitlines()[0]
        print(f"{u['id']:>3} {u['kind']:<5} {t}")
