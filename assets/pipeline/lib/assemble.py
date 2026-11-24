"""Lecture spec -> frames + 曉臻 narration -> timed MP4 with soft captions, script and QA report."""
import json, math, pathlib, re, subprocess, wave, datetime
from concurrent.futures import ThreadPoolExecutor
import av, numpy as np
import imageio_ffmpeg
from PIL import Image

from . import render, tts

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILD, OUT = ROOT / "build", ROOT / "out"
FF = imageio_ffmpeg.get_ffmpeg_exe()
FPS, SR = 30, 48000
FADE = 0.30
LEAD_FIRST, LEAD, TAIL, TAIL_SLIDE, TAIL_END = 0.55, 0.30, 0.50, 1.00, 2.20


def _decode(mp3):
    c = av.open(str(mp3))
    rs = av.AudioResampler(format="fltp", layout="mono", rate=SR)
    chunks = []
    for fr in c.decode(audio=0):
        for o in rs.resample(fr):
            chunks.append(o.to_ndarray()[0])
    for o in rs.resample(None):
        chunks.append(o.to_ndarray()[0])
    c.close()
    return np.concatenate(chunks).astype(np.float32)


def _split_caption(text):
    sents = [s for s in re.findall(r"[^。！？；]+[。！？；]?", tts.caption(text)) if s.strip()]
    return sents


def _chunks(sentence, maxlen=34):
    """Split a sentence into on-screen caption chunks (<= 2 lines of ~17 chars)."""
    s = sentence.strip()
    if len(s) <= maxlen:
        return [s]
    parts = re.findall(r"[^，、：]+[，、：]?", s)
    out, cur = [], ""
    for p in parts:
        if cur and len(cur) + len(p) > maxlen:
            out.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        out.append(cur)
    return out


def _wrap2(s):
    if len(s) <= 20:
        return s
    h = len(s) // 2
    def ok(i):  # never split inside an ASCII word
        return not (s[i - 1].isascii() and s[i - 1].isalnum() and s[i].isascii() and s[i].isalnum())
    cand = [i for i in range(max(6, h - 7), min(len(s) - 5, h + 8)) if ok(i)] or [h]
    best = min(cand, key=lambda i: (0 if s[i - 1] in "，、：" else 1, abs(i - h)))
    return s[:best].rstrip() + "\n" + s[best:].lstrip()


def _ts(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError(" ".join(map(str, cmd[:6])) + "\n" + r.stderr[-1500:])


def build_lecture(lec, force_video=False):
    tag = f"L{lec.no:02d}_{lec.slug}"
    wd = BUILD / tag
    wd.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)

    # 1) frames ----------------------------------------------------------------
    frames, warns = render.render_lecture(lec)
    for w in warns:
        print(f"  !! overflow  slide {w[0]} 「{w[1]}」: {w[2]}")

    # 2) narration -------------------------------------------------------------
    flat = [(si, bi, b.say) for si, s in enumerate(lec.slides) for bi, b in enumerate(s.beats)]
    res, ncalls = tts.synth_all([t for _, _, t in flat], rate=lec.rate)
    print(f"  TTS: {len(flat)} passages, {ncalls} new synthesis calls (rest cached)")

    # 3) timeline --------------------------------------------------------------
    segs, t_cursor = [], 0.0
    for idx, ((si, bi, say), (mp3, meta, sp)) in enumerate(zip(flat, res)):
        wav = _decode(mp3)
        d = len(wav) / SR
        last_of_slide = bi == len(lec.slides[si].beats) - 1
        last_all = last_of_slide and si == len(lec.slides) - 1
        lead = LEAD_FIRST if bi == 0 else LEAD
        tail = TAIL_END if last_all else (TAIL_SLIDE if last_of_slide else TAIL)
        n = math.ceil((lead + d + tail) * FPS)
        segs.append(dict(si=si, bi=bi, say=say, spoken=sp, wav=wav, d=d, lead=lead, n=n, t0=t_cursor, meta=meta,
                         png=frames[(si, bi)]))
        t_cursor += n / FPS
    total = t_cursor

    # 4) video segments --------------------------------------------------------
    prev = None
    jobs = []
    for k, sg in enumerate(segs):
        prev_png = segs[k - 1]["png"] if k else sg["png"]
        sg["seg"] = wd / f"seg_{k:03d}_{sg['png'].stem[-10:]}_{prev_png.stem[-10:]}_{sg['n']}.mp4"
        jobs.append((prev_png, sg))

    def mk(job):
        pp, sg = job
        if sg["seg"].exists() and not force_video:
            return
        T = sg["n"] / FPS
        common = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p",
                  "-g", "60", "-r", str(FPS), "-frames:v", str(sg["n"]), "-an"]
        if pp == sg["png"]:
            cmd = [FF, "-y", "-hide_banner", "-loglevel", "error", "-framerate", str(FPS), "-loop", "1",
                   "-t", f"{T:.4f}", "-i", str(sg["png"]), *common, str(sg["seg"])]
        else:
            cmd = [FF, "-y", "-hide_banner", "-loglevel", "error",
                   "-framerate", str(FPS), "-loop", "1", "-t", f"{FADE}", "-i", str(pp),
                   "-framerate", str(FPS), "-loop", "1", "-t", f"{T:.4f}", "-i", str(sg["png"]),
                   "-filter_complex", f"[0:v][1:v]xfade=transition=fade:duration={FADE}:offset=0,format=yuv420p[v]",
                   "-map", "[v]", *common, str(sg["seg"])]
        _run(cmd)

    with ThreadPoolExecutor(4) as ex:
        list(ex.map(mk, jobs))
    lst = wd / "concat.txt"
    lst.write_text("".join(f"file '{sg['seg'].as_posix()}'\n" for sg in segs), encoding="utf-8")
    vid = wd / "video_only.mp4"
    _run([FF, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(vid)])

    # 5) audio track (sample-exact with the video) -----------------------------
    parts = []
    for sg in segs:
        nsamp = sg["n"] * SR // FPS
        buf = np.zeros(nsamp, np.float32)
        a = int(sg["lead"] * SR)
        w = sg["wav"][: max(0, nsamp - a)]
        buf[a:a + len(w)] = w
        parts.append(buf)
    audio = np.concatenate(parts)
    peak = float(np.abs(audio).max())
    if peak > 0.97:
        audio *= 0.97 / peak
    wavf = wd / "audio.wav"
    with wave.open(str(wavf), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())

    # 6) captions + script -----------------------------------------------------
    cues = []
    for sg in segs:
        sents = _split_caption(sg["say"])
        bounds = sg["meta"]["sents"]
        base = sg["t0"] + sg["lead"]
        if len(bounds) == len(sents):
            win = [(base + b["t0"], base + b["t0"] + b["d"]) for b in bounds]
        else:
            wts = np.array([max(1, len(tts.spoken(s))) for s in sents], float)
            edges = np.concatenate([[0], np.cumsum(wts) / wts.sum()]) * sg["d"]
            win = [(base + edges[i], base + edges[i + 1]) for i in range(len(sents))]
        for s, (a, b) in zip(sents, win):
            ch = _chunks(s)
            w = np.array([len(c) for c in ch], float)
            e = np.concatenate([[0], np.cumsum(w) / w.sum()]) * (b - a)
            for i, c in enumerate(ch):
                cues.append((a + e[i], a + e[i + 1] - 0.02, _wrap2(c)))
    fixed, last = [], 0.0
    for a, b, t in cues:           # no overlapping cues
        a = max(a, last)
        b = max(b, a + 0.3)
        fixed.append((a, b, t)); last = b
    cues = fixed
    srt = wd / "captions.srt"
    srt.write_text("".join(f"{i + 1}\n{_ts(a)} --> {_ts(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(cues)), encoding="utf-8")

    # 7) mux -------------------------------------------------------------------
    final = OUT / f"{tag}.mp4"
    _run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", str(vid), "-i", str(wavf), "-i", str(srt),
          "-map", "0:v", "-map", "1:a", "-map", "2:s", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
          "-c:s", "mov_text", "-metadata:s:s:0", "language=zho", "-metadata:s:a:0", "language=zho",
          "-metadata", f"title={lec.code or lec.no}：{lec.title}", "-metadata", f"comment=旁白：Microsoft 曉臻（zh-TW-HsiaoChenNeural），AI 合成語音",
          "-movflags", "+faststart", str(final)])
    (OUT / f"{tag}.srt").write_text(srt.read_text(encoding="utf-8"), encoding="utf-8")

    script = [f"# {lec.code or lec.no}：{lec.title}\n", f"{lec.subtitle}\n", "旁白：Microsoft 曉臻（AI 合成語音）\n"]
    cur = -1
    for sg in segs:
        if sg["si"] != cur:
            cur = sg["si"]
            script.append(f"\n## {cur + 1}. {re.sub('<[^>]+>', '', lec.slides[cur].title)}\n")
        script.append(f"[{int(sg['t0'] // 60):02d}:{sg['t0'] % 60:04.1f}] {tts.caption(sg['say'])}\n")
    (OUT / f"{tag}_script.md").write_text("\n".join(script), encoding="utf-8")

    # 8) QA --------------------------------------------------------------------
    qa = qa_video(final, total, segs, lec, tag, warns)
    qa["peak_before_limit"] = peak
    (OUT / f"{tag}_qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    man = dict(voice=tts.VOICE, rate=lec.rate, passages=len(flat), new_tts_calls=ncalls,
               sent_to_tts=[sg["spoken"] for sg in segs],
               excluded_from_tts="版面文字、公式 LaTeX、程式碼、檔案路徑、任何個人／雇主資訊",
               ai_voice_disclosure="每頁頁腳 + MP4 metadata comment + 講稿標頭")
    (OUT / f"{tag}_tts_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return qa


def qa_video(final, planned_total, segs, lec, tag, warns):
    c = av.open(str(final))
    vs, as_ = c.streams.video[0], c.streams.audio[0]
    vdur = float(vs.duration * vs.time_base) if vs.duration else c.duration / 1e6
    adur = float(as_.duration * as_.time_base) if as_.duration else c.duration / 1e6
    info = dict(file=final.name, container_duration_s=c.duration / 1e6, video=dict(codec=vs.codec_context.name, w=vs.width, h=vs.height,
                fps=float(vs.average_rate), duration_s=vdur), audio=dict(codec=as_.codec_context.name, rate=as_.rate, duration_s=adur),
                subtitle_streams=len(c.streams.subtitles), planned_total_s=planned_total,
                av_diff_ms=abs(vdur - adur) * 1000, overflow_warnings=[(w[0], w[2]) for w in warns],
                slides=len(lec.slides), beats=len(segs))
    # sample frames at 5 positions -> contact sheet
    sheet = []
    for fr in (0.04, 0.25, 0.5, 0.75, 0.97):
        t = planned_total * fr
        c.seek(int(t * 1e6))
        for f in c.decode(video=0):
            if f.pts * f.time_base >= t - 0.5 or True:
                sheet.append(f.to_image().resize((640, 360)))
                break
    nvp = sum(1 for p in c.demux(vs) if p.size) if False else None
    c.close()
    W = Image.new("RGB", (640 * 3, 360 * 2), "white")
    for i, im in enumerate(sheet):
        W.paste(im, ((i % 3) * 640, (i // 3) * 360))
    (OUT / "qa").mkdir(exist_ok=True)
    W.save(OUT / "qa" / f"{tag}_samples.png")
    # slide-final contact sheet
    ends = {}
    for sg in segs:
        ends[sg["si"]] = sg["png"]
    thumbs = [Image.open(p).convert("RGB").resize((480, 270)) for _, p in sorted(ends.items())]
    cols = 4
    rows = math.ceil(len(thumbs) / cols)
    S = Image.new("RGB", (480 * cols, 270 * rows), "white")
    for i, im in enumerate(thumbs):
        S.paste(im, ((i % cols) * 480, (i // cols) * 270))
    S.save(OUT / "qa" / f"{tag}_slides.png")
    info["pass"] = (info["video"]["codec"] == "h264" and info["audio"]["codec"] == "aac" and info["subtitle_streams"] == 1
                    and info["av_diff_ms"] <= 500 and not warns)
    return info
