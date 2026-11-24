"""Microsoft Edge neural TTS (zh-TW-HsiaoChenNeural = 曉臻), cached, with sentence timings."""
import asyncio, hashlib, json, pathlib, re
import edge_tts

VOICE = "zh-TW-HsiaoChenNeural"
assert VOICE == "zh-TW-HsiaoChenNeural", "policy: narration must use 曉臻 (HsiaoChen) only"
ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "build" / "audio"

# Spoken forms: applied to the TTS text only (captions / slides keep the original characters).
# Policy: every foreign name, proper noun, unit name and Greek letter is SPOKEN IN ENGLISH
# (never a Chinese transliteration such as 貝瑞 / 歐米加 / 傅立葉). The voice stays 曉臻 (HsiaoChen) only.
LEX = {
    # greek letters -> English names
    "ω": "omega", "Ω": "Omega", "ε": "epsilon", "μ": "mu", "Θ": "Theta", "θ": "theta", "κ": "kappa",
    "λ": "lambda", "Λ": "Lambda", "ν": "nu", "φ": "phi", "σ": "sigma", "Σ": "Sigma", "τ": "tau",
    "δ": "delta", "Δ": "Delta", "η": "eta", "∇": "nabla", "Γ": "Gamma", "π": "pi", "ρ": "rho",
    "ψ": "psi", "χ": "chi", "α": "alpha", "β": "beta", "γ": "gamma", "ℏ": "h bar",
    # math symbols (translations, not transliterations)
    "∞": "無窮大",
    "→": "趨近", "≈": "約等於", "≤": "小於等於", "≥": "大於等於", "≠": "不等於", "×": "乘", "±": "正負",
    "⟦": "", "⟧": "", "·": "", "−": "負", "–": "到", "—": "，",
    # acronyms (letter by letter, English letter names)
    "RCWA": "R C W A", "PWE": "P W E", "FDTD": "F D T D", "GPU": "G P U", "CPU": "C P U",
    "CPML": "C P M L", "PML": "P M L", "MPB": "M P B", "CFL": "C F L", "FFT": "F F T",
    "FHS": "F H S", "QWZ": "Q W Z", "YIG": "Y I G", "EDA": "E D A", "ADE": "A D E", "DFT": "D F T",
    "TE": "T E", "TM": "T M", "BZ": "B Z", "CI": "C I", "LU": "L U", "TF/SF": "T F S F",
    "ABJ": "A B J", "SoA": "S o A", "CMake": "C Make", "pytest": "pie test", "NumPy": "Num Pie",
    "pybind11": "pie bind eleven", "S4": "S 4", "PyTorch": "Pie Torch", "CuPy": "Q Pie",
    "Mcells/s": "百萬格每秒", "_core": "core",
    # --- C++ × ILT 課程 ---
    "ILT": "I L T", "OPC": "O P C", "SOCS": "S O C S", "TCC": "T C C", "SRAF": "S R A F", "RAII": "R A I I",
    "STL": "S T L", "NILS": "N I L S", "GDSII": "G D S two", "GDS": "G D S", "MRC": "M R C", "EUV": "E U V",
    "ArF": "A R F", "KrF": "K R F", "PSM": "P S M", "OAI": "O A I", "SMO": "S M O", "EPE": "E P E",
    "SVD": "S V D", "IFFT": "I F F T", "DOF": "D O F", "PEB": "P E B", "PAB": "P A B", "CTR": "C T R",
    "VTR": "V T R", "RET": "R E T", "MSVC": "M S V C", "ASan": "A San", "UBSan": "U B San", "GIL": "G I L",
    "NRVO": "N R V O", "API": "A P I", "SEM": "S E M", "DRC": "D R C",
    "C++20": "C plus plus twenty", "C++17": "C plus plus seventeen", "C++11": "C plus plus eleven", "C++": "C plus plus",
    "Catch2": "Catch two", "cuFFT": "C U F F T", "nvcc": "N V C C", "Clipper2": "Clipper two", "gdstk": "G D S T K",
    "learncpp": "learn C P P", "k₁": "k one", "k₂": "k two", "noexcept": "no except", "constexpr": "const expr",
    "unique_ptr": "unique pointer", "shared_ptr": "shared pointer", "weak_ptr": "weak pointer",
    "std::": "std ", "autograd": "auto grad", "Köhler": "Kohler", "∂": "partial", "²": " 平方", "√": "根號",
    # --- FDTD 課程 ---
    "TMz": "T M z", "TEz": "T E z", "TMM": "T M M", "ABC": "A B C", "PEC": "P E C", "PMC": "P M C",
    "CFS": "C F S", "UPML": "U P M L", "PLRC": "P L R C", "RC": "R C", "AI": "A I", "AoS": "A o S",
    "CW": "C W", "Q": "Q", "SF": "S F", "TF": "T F", "dB": "decibels", "FLOP": "flop", "SM": "S M",
    "Colab": "Colab", "CUDA": "CUDA", "kernel": "kernel", "Harminv": "harm inv",
    # --- FDTD 手把手版：程式裡的小寫名稱、單位（回聽檢查後加入）---
    "PYTHONUTF8": "Python U T F 8", "numpy": "Num Pie", "matplotlib": "mat plot lib", "Ampère": "Ampere",
    "eV": "e V", "rcwa": "R C W A", "pec": "P E C", "np": "N P", "ts": "T S", "hy": "H y", "ez": "E z",
    "src": "source", "cosw": "cos w", "memcpy": "mem copy", "dim3": "dim three", "sm": "S M",
    "w0": "w zero", "w1": "w one", "v2": "v two", "te": "T E", "README": "read me", "KB": "kilobytes",
    "arccosh": "arc cosh", "四 byte": "四個 byte", "七十二 byte": "七十二個 byte", "拿 sine 測試": "拿正弦函數來測試", "sine 平方": "sine squared", "乘 sine theta": "乘 sine of theta",
    # Chinese transliterations that appear in the narration -> English name
    "馬克士威": "Maxwell", "厄米": "Hermitian", "布里淵": "Brillouin", "傅立葉": "Fourier",
    "法拉第": "Faraday", "安培": "Ampere", "貝索": "Bessel", "拉普拉斯": "Laplacian",
    "拉格朗日": "Lagrange", "布拉格": "Bragg", "瑞利": "Rayleigh", "高斯脈衝": "Gaussian 脈衝",
    "高斯": "Gauss", "吉赫茲": "gigahertz", "赫茲": "hertz", "奈米": "nanometers",
    "分貝": "decibels", "吉位元組每秒": "gigabytes per second", "吉位元組": "gigabytes",
    "費米子": "fermion", "霍爾": "Hall", "微軟": "Microsoft",
}
# Latin-script names (Berry, Chern, Bloch, Fukui, Joannopoulos, Meep, CUDA, ...) are deliberately NOT mapped:
# they are sent as written so the voice reads them with English pronunciation.
_LEX_KEYS = sorted(LEX, key=len, reverse=True)
# 純英數的鍵只比對完整的詞（否則 "TF" 會比對到 "PYTHONUTF8" 裡面）
_LEX_RE = re.compile("|".join(
    (r"(?<![A-Za-z0-9])" + re.escape(k) + r"(?![A-Za-z0-9])") if re.fullmatch(r"[A-Za-z0-9]+", k) else re.escape(k)
    for k in _LEX_KEYS))


def spoken(text: str) -> str:
    """Caption text -> text actually sent to the TTS engine."""
    t = text.replace("\n", " ")
    t = re.sub(r"\{([^|{}]+)\|([^{}]+)\}", r"\2", t)          # {caption|spoken} override
    t = _LEX_RE.sub(lambda m: " " + LEX[m.group(0)] + " " if LEX[m.group(0)] else "", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def caption(text: str) -> str:
    return re.sub(r"\{([^|{}]+)\|([^{}]+)\}", r"\1", text.replace("\n", " "))


def _key(sp, rate):
    return hashlib.sha1(f"{VOICE}|{rate}|{sp}".encode("utf-8")).hexdigest()[:20]


async def _one(sp, rate, sem, stats):
    assert VOICE == "zh-TW-HsiaoChenNeural"
    k = _key(sp, rate)
    mp3, js = CACHE / f"{k}.mp3", CACHE / f"{k}.json"
    if mp3.exists() and js.exists():
        return k
    async with sem:
        for attempt in range(5):
            try:
                com = edge_tts.Communicate(sp, VOICE, rate=rate, boundary="SentenceBoundary")
                audio, sents = bytearray(), []
                async for ch in com.stream():
                    if ch["type"] == "audio":
                        audio += ch["data"]
                    elif ch["type"] == "SentenceBoundary":
                        sents.append({"t0": ch["offset"] / 1e7, "d": ch["duration"] / 1e7, "text": ch["text"]})
                if not audio:
                    raise RuntimeError("empty audio")
                mp3.write_bytes(bytes(audio))
                js.write_text(json.dumps({"voice": VOICE, "rate": rate, "text": sp, "sents": sents},
                                         ensure_ascii=False), encoding="utf-8")
                stats["calls"] += 1
                return k
            except Exception as e:  # network hiccup -> retry with backoff
                if attempt == 4:
                    raise
                await asyncio.sleep(1.5 * (attempt + 1))


def synth_all(texts, rate="-6%", concurrency=4):
    """texts: list of caption-form strings. Returns list of (mp3_path, sentences_json) aligned to texts."""
    CACHE.mkdir(parents=True, exist_ok=True)
    stats = {"calls": 0}

    async def run():
        sem = asyncio.Semaphore(concurrency)
        sps = [spoken(t) for t in texts]
        keys = await asyncio.gather(*[_one(sp, rate, sem, stats) for sp in sps])
        return sps, keys

    sps, keys = asyncio.run(run())
    out = []
    for t, sp, k in zip(texts, sps, keys):
        out.append((CACHE / f"{k}.mp3", json.loads((CACHE / f"{k}.json").read_text(encoding="utf-8")), sp))
    return out, stats["calls"]
