"""python make.py 1 [2 3 ...]   -> builds the given lectures into out/"""
import sys, importlib, json, time
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from lib import assemble

if __name__ == "__main__":
    force = "--force" in sys.argv
    nums = [int(a) for a in sys.argv[1:] if a.isdigit()]
    for n in nums:
        t0 = time.time()
        src = (__import__("pathlib").Path(__file__).parent / "lectures" / f"L{n:02d}.py").read_text(encoding="utf-8")
        bad = [(i + 1, repr(c)) for i, line in enumerate(src.split("\n")) for c in line if ord(c) < 32 and c != "\t" or c == "\t" and not line.startswith(" ")]
        assert not bad, f"control characters in lecture source (bad LaTeX escape?): {bad[:5]}"
        lec = importlib.import_module(f"lectures.L{n:02d}").LEC
        print(f"== Lecture {n}: {lec.title}")
        qa = assemble.build_lecture(lec, force_video=force)
        print(json.dumps({k: qa[k] for k in ("file", "container_duration_s", "av_diff_ms", "slides", "beats", "pass")}, ensure_ascii=False),
              f"({time.time() - t0:.0f}s)")
