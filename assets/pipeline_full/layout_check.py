"""只算版面（不配音）：python layout_check.py 81 82 … → 溢位警告、縮放過小的頁、接觸表 build/sheet_Lxx.png"""
import importlib, math, sys
from PIL import Image
from lib import render
for n in map(int, sys.argv[1:]):
    lec = importlib.import_module(f"lectures.L{n:02d}").LEC
    fr, w = render.render_lecture(lec)
    print(n, w or "OK")
    last = [fr[(i, j)] for i, s in enumerate(lec.slides) for j in range(len(s.beats)) if j == len(s.beats) - 1 or j % 2 == 1]
    S = Image.new("RGB", (480 * 5, 270 * math.ceil(len(last) / 5)), "white")
    for i, p in enumerate(last):
        S.paste(Image.open(p).convert("RGB").resize((480, 270)), ((i % 5) * 480, (i // 5) * 270))
    S.save(f"build/sheet_L{n:02d}.png")
