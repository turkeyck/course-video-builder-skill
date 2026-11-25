"""scripts/Vxx_*.md → lectures/Lxx.py（機械轉換，旁白逐字相同）；並檢查講義單位全部上了畫面。
用法：python compile.py [檔號…]      python compile.py --coverage

旁白下一行起（縮排兩格）是畫面：
  > 12-15, 94:1-7     引用講義單位（預設該支影片的週次；W3#12 指定別週）
  r> 94               放到右欄
  eq: li: t: ts: h: key: note: warn: todo:    自寫元素（前面加 r 放右欄）
  img: 檔名 高度
"""
import functools, pathlib, re, sys
import units as U

ROOT = pathlib.Path(__file__).resolve().parent
get = functools.lru_cache(None)(U.units)
used = {w: {} for w in U.WEEKS}     # week -> id -> set(行) 或 True
SEC_HEADS = re.compile(r"^\*\*(命題|定理|引理|定義|推論|例|坑)")


def inline(s):
    """講義 markdown → 投影片 HTML；$…$ 內原樣（只跳脫 < &）。"""
    parts = re.split(r"(\$[^$]+\$|`[^`]+`)", s)
    out = []
    for k, p in enumerate(parts):
        nxt = parts[k + 1] if k + 1 < len(parts) else ""
        if p.startswith("$") and len(p) < 34 and len(p) > 1 and nxt[:1] in tuple("，。；：、）」"):   # 標點不落到行首
            m = re.match("[，。；：、）」]+", nxt)
            parts[k + 1] = nxt[m.end():]
            out.append('<span style="white-space:nowrap">' + p.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + m[0] + "</span>")
            continue
        e = p.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if p.startswith("$") and p.endswith("$") and len(p) > 1:
            out.append(e)
        elif p.startswith("`") and p.endswith("`") and len(p) > 1:
            out.append("<code>" + e[1:-1] + "</code>")
        else:
            e = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", e)
            out.append(e)
    e = "".join(out)
    # 粗體、斜體可能跨過公式，所以在合併後處理；公式裡沒有 *
    keep = []
    def hide(m):
        keep.append(m[0]); return f"\x01{len(keep) - 1}\x02"
    e = re.sub(r"\$[^$]+\$|<code>.*?</code>", hide, e)
    e = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", e)
    e = re.sub(r"\*(.+?)\*", r"<i>\1</i>", e)
    return re.sub("\x01(\\d+)\x02", lambda m: keep[int(m[1])], e)


def emit(fn, *a, col=0, **k):
    s = f"{fn}(" + ", ".join([repr(x) for x in a] + [f"{q}={v!r}" for q, v in k.items()]) + ")"
    return s + (f".c({col})" if col else "")


def pull(spec, week, col):
    items = []      # (kind, para, payload)
    for part in re.split(r"[,，]\s*", spec.strip()):
        m = re.fullmatch(r"(?:W(\d)#)?(\d+)(?:-(\d+))?(?::(\d+)-(\d+))?", part)
        assert m, f"看不懂的引用 {part!r}"
        w = int(m[1]) if m[1] else week
        for i in range(int(m[2]), int(m[3] or m[2]) + 1):
            us = get(w)
            assert 1 <= i <= len(us), f"W{w} 沒有單位 {i}"
            u = us[i - 1]
            if m[4]:
                ls = u["text"].split("\n")
                a, b = int(m[4]), int(m[5])
                assert u["kind"] in ("code", "out") and b <= len(ls), f"W{w}#{i} 只有 {len(ls)} 行"
                seen = used[w].setdefault(i, set())
                if seen is not True:
                    seen |= set(range(a, b + 1))
                items.append((u["kind"], (w, i), "\n".join(ls[a - 1:b]), u))
            else:
                used[w][i] = True
                items.append((u["kind"], (w, u["para"]), u["text"], u))
    # 合併
    groups = []
    for it in items:
        if groups and groups[-1][0] == it[0] and groups[-1][1] == it[1] and it[0] in ("t", "quote", "li", "todo"):
            groups[-1][2].append(it[2])
        elif groups and it[0] == "row" and groups[-1][0] == "row" and groups[-1][3]["head"] == it[3]["head"]:
            groups[-1][2].append(it[2])
        else:
            groups.append([it[0], it[1], [it[2]], it[3]])
    out = []
    for kind, _, pay, u in groups:
        if kind == "t":
            s = inline("".join(pay))
            out.append(emit("BOX", s, "thm", col=col) if SEC_HEADS.match(pay[0]) else emit("T", s, "m", col=col))
        elif kind == "quote":
            out.append(emit("BOX", inline("".join(pay)), "key", col=col))
        elif kind == "li":
            out.append(emit("LI", inline("".join(pay)), col=col))
        elif kind == "todo":
            out.append(emit("LI", "☐ " + inline("".join(pay)), col=col))
        elif kind == "row":
            out.append(emit("TBL", [[inline(c) for c in u["head"]]] + [[inline(c) for c in r] for r in pay], cls="m", col=col))
        elif kind == "eq":
            out.append(emit("EQ", pay[0], cls="sm", col=col))
        elif kind == "img":
            out.append(emit("IMG", pay[0], h=620, col=col))
        elif kind == "code":
            out.append(emit("CODE", pay[0], cls="", col=col))
        elif kind in ("out", "cmd"):
            out.append(emit("CODE", pay[0], cls=kind if kind == "out" else "sm cmd", col=col))
        elif kind == "ex":
            s = inline(pay[0])
            out.append(emit("T", f"<b>解答 {u['n']}</b>　" + s, "m", col=col) if u.get("sol")
                       else emit("BOX", f"<b>{'坑' if u['sec'].startswith('4') else '第'} {u['n']}{'' if u['sec'].startswith('4') else ' 步' if u['sec'].startswith('2') else ' 題'}</b>　" + s, "ex", col=col))
    return out


def own(kw, txt, col):
    if kw in ("t", "ts", "h"):
        return emit("T", inline(txt), {"t": "m", "ts": "s", "h": "h"}[kw], col=col)
    if kw == "li":
        return emit("LI", inline(txt), col=col)
    if kw == "eq":
        return emit("EQ", txt, cls="sm", col=col)
    if kw in ("key", "note", "warn", "todo"):
        return emit("BOX", inline(txt), kw, col=col)
    if kw == "img":
        n, h = txt.split()
        return emit("IMG", n, h=int(h), col=col)
    raise SystemExit(f"未知關鍵字 {kw}")


def compile_one(path, write=True):
    L = path.read_text(encoding="utf-8").split("\n")
    m = re.match(r"# V(\d\d) (\S+)｜(.+)$", L[0])
    no, code, title = int(m[1]), m[2], m[3].strip()
    slug = re.search(r"slug `([^`]+)`", L[1])[1]
    sub = re.search(r"副標「([^」]+)」", L[1])[1]
    week = no // 10 or 1
    slides, cur, beat = [], None, None
    for k, ln in enumerate(L[2:], 3):
        try:
            m = re.match(r"### 投影片 (\d+)｜(.+)（((?:title|summary|kicker).*)）$", ln)
            if m:
                opt = m[3]
                kick = re.search(r"kicker「([^」]*)」", opt)
                cols = re.search(r"兩欄 ([\d.:]+)", opt)
                kind = "title" if "title" in opt else "summary" if "summary" in opt else ""
                cur = dict(title=m[2], kick=kick[1] if kick else "", cols=cols[1] if cols else "", kind=kind, beats=[])
                slides.append(cur); beat = None
                assert int(m[1]) == len(slides), "投影片編號不連續"
                continue
            m = re.match(r"- 旁白：(.+)$", ln)
            if m:
                beat = [m[1].strip(), []]; cur["beats"].append(beat); continue
            m = re.match(r"  (r?)(>|[a-z]+:)\s*(.+)$", ln)
            if m and beat is not None:
                col = 1 if m[1] else 0
                beat[1] += pull(m[3], week, col) if m[2] == ">" else [own(m[2][:-1], m[3], col)]
                continue
            # "r" 開頭的關鍵字（例如 rt:）
            assert not ln.strip() or ln.startswith("檔號") or ln.startswith("#"), f"看不懂：{ln[:60]}"
        except AssertionError as e:
            raise SystemExit(f"{path.name}:{k}: {e}")
    if not write:
        return
    o = ["# 由 compile.py 產生；改腳本，不要改這個檔", "from lib.spec import *", "",
         f"LEC = Lecture({no}, {slug!r}, {title!r}, {sub!r}, [], code={code!r})", "LEC.slides = ["]
    for s in slides:
        assert s["beats"], s["title"]
        o.append(f"    S({inline(re.sub('√([0-9])', lambda m: '$' + chr(92) + 'sqrt{' + m[1] + '}$', s['title']))!r}, kicker={s['kick']!r}, cols={s['cols']!r}, kind={s['kind']!r}, beats=[")
        for say, its in s["beats"]:
            o.append(f"        B({say!r}," + "".join(f"\n          {x}," for x in its) + "),")
        o.append("    ]),")
    o.append("]")
    (ROOT / "lectures" / f"L{no:02d}.py").write_text("\n".join(o) + "\n", encoding="utf-8")
    nch = sum(len(b[0]) for s in slides for b in s["beats"])
    print(f"L{no:02d} {len(slides)} 頁 {sum(len(s['beats']) for s in slides)} 段 旁白 {nch} 字")


def coverage():
    if not U.WEEKS:
        print("找不到 講義/W*_*.md"); return 1
    bad = 0
    for w in U.WEEKS:
        miss = []
        for u in get(w):
            got = used[w].get(u["id"])
            if got is True:
                continue
            if isinstance(got, set) and len(got) == len(u["text"].split("\n")):
                continue
            miss.append(f"{u['id']}" + (f"(缺行 {sorted(set(range(1, len(u['text'].split(chr(10))) + 1)) - got)})" if got else ""))
        print(f"W{w}: {len(get(w))} 個單位，缺 {len(miss)}", miss[:60] if miss else "")
        bad += len(miss)
    return bad


if __name__ == "__main__":
    nums = [int(a) for a in sys.argv[1:] if a.isdigit()]
    for p in sorted((ROOT / "scripts").glob("V[0-9][0-9]_*.md")):
        compile_one(p, write=not nums and "--coverage" not in sys.argv or int(p.name[1:3]) in nums)
    if "--coverage" in sys.argv or not nums:
        sys.exit(1 if coverage() else 0)
