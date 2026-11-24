"""Slide / lecture spec: the vocabulary lecture files are written in.

A Slide is a sequence of Beats. A Beat = one narration passage (`say`) plus the items that
appear while it is spoken. Items accumulate; the items of the current beat are highlighted.
"""
from dataclasses import dataclass, field
from .handout import blocks

_BLOCKS = None


def _hb(i):
    global _BLOCKS
    if _BLOCKS is None:
        _BLOCKS = blocks()
    return _BLOCKS[i]


class Item:
    def __init__(self, kind, **kw):
        self.kind, self.kw, self.col = kind, kw, 0

    def c(self, col=1):
        self.col = col
        return self


def T(html, cls=""):          # paragraph (inline math with $...$)
    return Item("t", html=html, cls=cls)


def LI(html):                  # bullet
    return Item("li", html=html)


def EQ(tex=None, h=None, cls="", size=None):   # display equation; h=index of handout latex block
    return Item("eq", tex=_hb(h) if tex is None else tex, cls=cls, size=size)


def IMG(name, h=None, w=None, cap=None):       # figure from build/figs/<name>.png
    return Item("img", name=name, h=h, w=w, cap=cap)


def BOX(html, kind="note"):    # callout: note | key | warn | todo
    return Item("box", html=html, k=kind)


def CODE(text, cls=""):
    return Item("code", text=text, cls=cls)


def TBL(rows, head=True, cls=""):
    return Item("tbl", rows=rows, head=head, cls=cls)


def RAW(html, cls=""):         # escape hatch for hand-made diagrams
    return Item("raw", html=html, cls=cls)


@dataclass
class Beat:
    say: str
    items: list = field(default_factory=list)


def B(say, *items):
    return Beat(say, list(items))


@dataclass
class Slide:
    title: str
    beats: list
    cols: str = ""            # e.g. "1:1" / "3:2" for two columns
    kind: str = ""            # "" | "title" | "summary"
    kicker: str = ""          # small label above the title, e.g. "1.1"


def S(title, beats, cols="", kind="", kicker=""):
    return Slide(title, beats, cols, kind, kicker)


@dataclass
class Lecture:
    no: int
    slug: str
    title: str
    subtitle: str
    slides: list
    rate: str = "-6%"
    code: str = ""            # 顯示用代號，例如 "C3"、"L4"、"總覽"
