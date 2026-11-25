"""Slides -> HTML (KaTeX) -> PNG per beat, via Playwright + system Edge."""
import hashlib, html as H, pathlib, re, json
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
KATEX = (ROOT / "tools" / "node_modules" / "katex" / "dist").as_posix()
FIGS = ROOT / "build" / "figs"
HTMLD = ROOT / "build" / "html"
FRAMES = ROOT / "build" / "frames"
COURSE = "（課程名稱）"  # TODO: 每門課改成自己的名稱，顯示在每頁頁首

CSS = r"""
@font-face{font-family:"LatExt";font-weight:400;src:local("Segoe UI");unicode-range:U+0100-017F}
@font-face{font-family:"LatExt";font-weight:700;src:local("Segoe UI Bold"),local("Segoe UI-Bold"),local("Segoe UI");unicode-range:U+0100-017F}
:root{--bg:#FAF8F3;--ink:#1B2A41;--mut:#5B6678;--acc:#C0472F;--blue:#2B59C3;--grn:#23795C;--rule:#D9D3C7;--card:#F1EDE3}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;background:var(--bg);color:var(--ink);overflow:hidden;
 font-family:"LatExt","Noto Sans TC","Microsoft JhengHei",sans-serif;font-size:40px;line-height:1.5}
.top{position:absolute;left:96px;right:96px;top:34px;height:44px;display:flex;justify-content:space-between;
 font-size:25px;color:var(--mut);letter-spacing:.04em;border-bottom:2px solid var(--rule)}
.top b{color:var(--acc);font-weight:700}
.head{position:absolute;left:96px;right:96px;top:96px;height:112px}
.kick{font-size:28px;color:var(--acc);font-weight:700;letter-spacing:.08em;height:34px}
.title{font-size:58px;font-weight:700;line-height:1.15;color:var(--ink);white-space:nowrap}
.content{position:absolute;left:96px;right:96px;top:236px;bottom:92px;display:flex;gap:64px}
.col{display:flex;flex-direction:column;gap:20px;min-width:0;overflow:visible}
.foot{position:absolute;left:96px;right:96px;bottom:26px;height:34px;display:flex;justify-content:space-between;
 font-size:21px;color:var(--mut)}
.prog{position:absolute;left:0;bottom:0;height:8px;background:var(--acc)}
.item{visibility:hidden;border-radius:10px;padding:2px 14px;margin-left:-14px;border-left:6px solid transparent;
 transition:none}
.item.vis{visibility:visible}
.item.cur{background:rgba(192,71,47,.075);border-left-color:var(--acc)}
.item.cur.code{background:#1E2635}
.t{font-size:40px}.t.s{font-size:33px;color:var(--mut)}.t.c{text-align:center}.t.h{font-size:46px;font-weight:700;color:var(--blue)}
.li{font-size:40px;padding-left:46px;position:relative}
.li:before{content:"";position:absolute;left:12px;top:.62em;width:14px;height:14px;border-radius:50%;background:var(--acc)}
.eq{text-align:center;font-size:40px;padding:8px 14px}
.eq .katex{font-size:1.3em}.eq.sm .katex{font-size:1.05em}.eq.xs .katex{font-size:.9em}.eq.lg .katex{font-size:1.55em}
.eq.l{text-align:left}
.box{padding:16px 26px;border-radius:12px;font-size:36px;background:var(--card);border:2px solid var(--rule)}
.box.key{border-color:var(--blue);background:#EAF0FB}.box.key:before{content:"核心結論　";color:var(--blue);font-weight:700}
.box.warn{border-color:var(--acc);background:#FBEDE8}.box.warn:before{content:"注意　";color:var(--acc);font-weight:700}
.box.todo{border-color:var(--grn);background:#E6F3EE}.box.todo:before{content:"驗收標準　";color:var(--grn);font-weight:700}
.box.note{}
.img{text-align:center}.img img{max-width:100%;border-radius:8px;border:1px solid var(--rule);background:#fff}
.img .cap{font-size:26px;color:var(--mut);margin-top:6px}
.code{font-family:"Cascadia Mono",Consolas,"Noto Sans TC","Microsoft JhengHei",monospace;font-size:29px;line-height:1.45;background:#1E2635;color:#E6EAF2;
 padding:14px 24px;border-radius:12px;white-space:pre}
.code.sm{font-size:26px}.code.xs{font-size:21px}
.tbl{border-collapse:collapse;font-size:33px;width:100%}
.tbl th{background:var(--ink);color:#fff;font-weight:700;text-align:left;padding:8px 16px}
.tbl td{padding:8px 16px;border-bottom:2px solid var(--rule);vertical-align:top}
.tbl.sm{font-size:28px}
.title-slide .head{top:280px;height:auto}.title-slide .title{font-size:84px;white-space:normal;line-height:1.2}
.title-slide .kick{font-size:36px}.title-slide .content{top:560px}
.title-slide .t{font-size:44px}
.summary .t,.summary .li{font-size:40px}
.t.m{font-size:36px;line-height:1.55}
.box.thm{background:#FFF8E6;border-color:#C9A227}.box.ex{background:#F3ECFA;border-color:#8257B8}
.fit{display:flex;flex-direction:column;gap:18px}
code{font-family:"Cascadia Mono",Consolas,"Noto Sans TC","Microsoft JhengHei",monospace;font-size:.86em;background:#E9E3D6;border-radius:6px;padding:0 8px}
.code{white-space:pre-wrap;word-break:break-word}
.item.code.out,.item.cur.code.out{background:#10312A}.item.code.cmd,.item.cur.code.cmd{background:#2A2340}
.tbl.m{font-size:32px}
.katex{color:var(--ink)}
"""

JS = r"""
let PAGES=null;   // PAGES[k]={a,b,z}：第 a..b 段同頁、縮放 z
function pageOf(n){return PAGES?PAGES.find(p=>n>=p.a&&n<=p.b):null;}
function setStep(n){
  const pg=pageOf(n);
  document.querySelectorAll('.item').forEach(e=>{
    const b=+e.dataset.b; const on=!pg||(b>=pg.a&&b<=pg.b);
    e.style.display=on?'':'none';
    e.classList.toggle('vis', b<=n); e.classList.toggle('cur', b===n);
  });
  if(pg)document.querySelectorAll('.fit').forEach((f,i)=>{f.style.zoom=pg.z[i];});
}
function fits(f){const c=f.parentElement,r=f.getBoundingClientRect(),q=c.getBoundingClientRect();
  if(r.height>q.height+1)return false;
  for(const e of f.querySelectorAll('.item')){if(e.style.display==='none')continue;if(e.scrollWidth>e.clientWidth+2)return false;
    for(const k of e.querySelectorAll('.katex-html,table,img'))if(k.getBoundingClientRect().right>q.right+2)return false;}
  return true;}
function only(a,b){document.querySelectorAll('.item').forEach(e=>{const k=+e.dataset.b;e.style.display=(k>=a&&k<=b)?'':'none';});}
function bestZoom(f,t0){let z=t0;f.style.zoom=z;while(!fits(f)&&z>0.45){z=Math.round((z-0.04)*100)/100;f.style.zoom=z;}return z;}
function paginate(nb){
  const F=[...document.querySelectorAll('.fit')],t0=document.body.className==='title-slide'?1:1.3;
  const hasCode=!!document.querySelector('.item.code');
  const zmin=hasCode?0.92:0.84;
  PAGES=[];let a=0;
  while(a<nb){let b=nb-1,z;
    for(;;){only(a,b);z=F.map(f=>bestZoom(f,t0));if(Math.min(...z)>=zmin||b===a)break;b--;}
    PAGES.push({a,b,z});a=b+1;}
  window.__minz=Math.min(...PAGES.flatMap(p=>p.z));
}
window.__overflow=function(){
  const bad=[];(PAGES||[]).forEach((p,k)=>{setStep(p.b);document.querySelectorAll('.fit').forEach((f,i)=>{if(!fits(f))bad.push(['page'+k+'col'+i,1]);});
    if(Math.min(...p.z)<0.7)bad.push(['zoom'+k,Math.min(...p.z)]);});
  const t=document.querySelector('.title'); if(t.scrollWidth>t.clientWidth+2||t.getBoundingClientRect().right>1830)bad.push(['title',1]);
  return bad;
};
window.addEventListener('load',async()=>{
  renderMathInElement(document.body,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],throwOnError:false,trust:true,ignoredClasses:['code']});
  document.querySelectorAll('.eq').forEach(e=>{katex.render(e.dataset.tex,e.querySelector('.m'),{displayMode:true,throwOnError:false,trust:true,strict:false});});
  await document.fonts.ready;
  paginate(window.__nbeats);
  window.__ready=true;
});
"""


def _item_html(it, i, beat, lec_dir):
    k, kw = it.kind, it.kw
    attr = f'class="item {{cls}}" data-b="{beat}" id="i{i}"'
    if k == "t":
        return f'<div {attr.format(cls="t " + kw["cls"])}>{kw["html"]}</div>'
    if k == "li":
        return f'<div {attr.format(cls="li")}>{kw["html"]}</div>'
    if k == "eq":
        size = kw["size"] or ""
        return (f'<div {attr.format(cls="eq " + size + " " + kw["cls"])} data-tex="{H.escape(kw["tex"], quote=True)}">'
                f'<span class="m"></span></div>')
    if k == "box":
        return f'<div {attr.format(cls="box " + kw["k"])}>{kw["html"]}</div>'
    if k == "code":
        return f'<div {attr.format(cls="code " + kw["cls"])}>{H.escape(kw["text"])}</div>'
    if k == "raw":
        return f'<div {attr.format(cls=kw["cls"])}>{kw["html"]}</div>'
    if k == "img":
        p = (FIGS / f'{kw["name"]}.png')
        assert p.exists(), f"missing figure {p}"
        style = ""
        if kw["h"]:
            style += f'max-height:{kw["h"]}px;'
        if kw["w"]:
            style += f'width:{kw["w"]}px;'
        cap = f'<div class="cap">{kw["cap"]}</div>' if kw["cap"] else ""
        sig = hashlib.md5(p.read_bytes()).hexdigest()[:10]   # figure content is part of the cache key
        return f'<!--fig:{sig}--><div {attr.format(cls="img")}><img src="{p.as_posix()}" style="{style}">{cap}</div>'
    if k == "tbl":
        rows = kw["rows"]
        h = ""
        if kw["head"]:
            h = "<tr>" + "".join(f"<th>{c}</th>" for c in rows[0]) + "</tr>"
            rows = rows[1:]
        body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
        return f'<div {attr.format(cls="")}><table class="tbl {kw["cls"]}">{h}{body}</table></div>'
    raise ValueError(k)


def slide_html(lec, slide, sidx, nslides, progress):
    flat = []  # (item, beat_index)
    for bi, b in enumerate(slide.beats):
        for it in b.items:
            flat.append((it, bi))
    ncol = 1 + max([it.col for it, _ in flat] + [0])
    widths = [1] * ncol
    if slide.cols:
        widths = [float(x) for x in slide.cols.split(":")]
    cols_html = []
    for c in range(ncol):
        inner = "".join(_item_html(it, i, bi, lec) for i, (it, bi) in enumerate(flat) if it.col == c)
        cols_html.append(f'<div class="col" style="flex:{widths[c]} 1 0"><div class="fit">{inner}</div></div>')
    kind = slide.kind
    kick = H.escape(slide.kicker) if slide.kicker else ""
    top = (f'<div class="top"><span>{COURSE}</span><span><b>{lec.code or lec.no}</b>　{H.escape(lec.title)}</span></div>'
           if kind != "title" else '<div class="top"><span>' + COURSE + '</span><span></span></div>')
    foot = (f'<div class="foot"><span>{sidx + 1} / {nslides}</span>'
            f'<span>旁白：Microsoft 神經語音「曉臻」（AI 合成語音）</span></div>')
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="file:///{KATEX}/katex.min.css"><style>{CSS}</style>
<script src="file:///{KATEX}/katex.min.js"></script><script src="file:///{KATEX}/contrib/auto-render.min.js"></script>
</head><body class="{'title-slide' if kind == 'title' else ('summary' if kind == 'summary' else '')}">
{top}<div class="head"><div class="kick">{kick}</div><div class="title">{slide.title}</div></div>
<div class="content">{''.join(cols_html)}</div>{foot}<div class="prog" style="width:{progress * 100:.1f}%"></div>
<script>window.__nbeats={len(slide.beats)};</script><script>{JS}</script></body></html>"""


def render_lecture(lec, only=None):
    """Returns dict[(slide_idx, beat_idx)] -> png path; also list of overflow warnings."""
    HTMLD.mkdir(parents=True, exist_ok=True)
    FRAMES.mkdir(parents=True, exist_ok=True)
    n = len(lec.slides)
    out, warns = {}, []
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel="msedge", headless=True)
        page = br.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        for si, s in enumerate(lec.slides):
            html = slide_html(lec, s, si, n, (si + 1) / n)
            sig = hashlib.sha1(html.encode("utf-8")).hexdigest()[:10]
            f = HTMLD / f"L{lec.no:02d}_s{si:02d}_{sig}.html"
            need = [bi for bi in range(len(s.beats)) if not (FRAMES / f"L{lec.no:02d}_s{si:02d}_b{bi:02d}_{sig}.png").exists()]
            for bi in range(len(s.beats)):
                out[(si, bi)] = FRAMES / f"L{lec.no:02d}_s{si:02d}_b{bi:02d}_{sig}.png"
            if not need:
                continue
            f.write_text(html, encoding="utf-8")
            page.goto("file:///" + f.as_posix())
            page.wait_for_function("window.__ready===true", timeout=20000)
            page.evaluate(f"setStep({len(s.beats) - 1})")
            bad = page.evaluate("window.__overflow()")
            if bad:
                warns.append((si, s.title, bad))
            for bi in need:
                page.evaluate(f"setStep({bi})")
                page.screenshot(path=str(out[(si, bi)]))
        br.close()
    return out, warns
