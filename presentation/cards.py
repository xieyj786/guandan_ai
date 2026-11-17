"""Shared Tk card faces rendered from individual SVG assets."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence
from functools import lru_cache
from io import BytesIO
from math import ceil
from pathlib import Path

from PIL import Image, ImageTk
from resvg_py import svg_to_bytes

WHITE = "#ffffff"
BLACK = "#101010"
RED = "#c81018"
GOLD = "#e5b94e"
SELECTED = "#63c9ff"
FELT = "#115b4e"  # Center color of reference_fan.svg.
STYLE_VERSION = "1.4"

_SVG_DIR = Path(__file__).resolve().parents[1] / "assets" / "card_style" / "svg"
_RANK_FILES = {11: "J", 12: "Q", 13: "K", 14: "A"}
_JOKER_FILES = {15: "joker_small", 16: "joker_big"}


def rank_text(rank: int) -> str:
    return {11: 'J', 12: 'Q', 13: 'K', 14: 'A', 15: '小王', 16: '大王'}.get(rank, str(rank))


@lru_cache(maxsize=54)
def _card_svg(suit, rank):
    name = _JOKER_FILES.get(rank)
    if name is None:
        name = f"{suit}_{_RANK_FILES.get(rank, rank)}"
    return (_SVG_DIR / f"{name}.svg").read_text(encoding="utf-8")


@lru_cache(maxsize=512)
def _card_image(suit, rank, width, height):
    svg = _card_svg(suit, rank)
    if rank in _JOKER_FILES:
        # Jokers have wider masters. Match the regular card's displayed height
        # and keep the same slot width so overlapping hands still line up.
        face_height = min(height, ceil(width * 400 / 250))
        pixels = svg_to_bytes(svg_string=svg, height=face_height, skip_system_fonts=True)
    else:
        pixels = svg_to_bytes(svg_string=svg, width=width, height=height, skip_system_fonts=True)
    with Image.open(BytesIO(pixels)) as image:
        face = image.convert("RGBA")
    if rank in _JOKER_FILES:
        return face.resize((width, face_height), Image.Resampling.LANCZOS)
    return face


def draw_card(canvas: tk.Canvas, suit: str, rank: int, x: float, y: float,
              width: float, height: float, *, wildcard=False, selected=False, finished_color=None, align_top=False) -> None:
    """Fit the SVG inside the existing card slot, with outlines around the artwork."""
    w = int(min(width - 4, (height - 4) / 2))
    if w <= 0:
        return
    image = _card_image(suit, rank, w, w * 2)
    w, h = image.size
    left = x + (width-w)/2
    top = y + (0 if align_top else (height-h)/2)
    if not canvas.find_withtag("card_art"):
        canvas._card_photos = []
    photo = ImageTk.PhotoImage(image, master=canvas)
    canvas._card_photos.append(photo)
    canvas.create_image(left, top, anchor="nw", image=photo, tags="card_art")
    def outline(color, inset, line_width, tag):
        inset = min(inset, max(0, (w-2)/4))
        top_inset = max(inset, line_width / 2) if align_top else inset
        l, t, r, b = left+inset, top+top_inset, left+w-inset, top+h-inset
        radius = max(1, (r-l) * .10)
        coords = [l+radius,t, r-radius,t, r,t, r,t+radius,
                  r,b-radius, r,b, r-radius,b, l+radius,b,
                  l,b, l,b-radius, l,t+radius, l,t]
        canvas.create_polygon(coords, smooth=True, splinesteps=16, fill='',
                              outline=color, width=line_width, tags=tag)

    if wildcard or selected:
        outline(SELECTED if selected else GOLD, 3 if finished_color else 0, 2, 'card_highlight')
    if finished_color:
        outline(finished_color, 0, 2.5, 'last_hand_border')


class CardFace(tk.Canvas):
    """单张可缩放的牌面，可直接绑定 <Button-1>，两副牌保留两个独立控件。"""
    def __init__(self, master, suit: str, rank: int, *, width=36, height=72,
                 background='#123c35', wildcard=False, selected=False):
        super().__init__(master, width=width, height=height, bg=background,
                         highlightthickness=0, bd=0)
        self.suit, self.rank = suit, rank
        self.wildcard, self.selected = wildcard, selected
        self.align_top = False
        self.bind('<Configure>', self._redraw)
        self._paint(width, height)

    def _paint(self, width, height):
        self.delete('all')
        draw_card(self, self.suit, self.rank, 0, 0, width, height,
                  wildcard=self.wildcard, selected=self.selected, align_top=self.align_top)

    def _set_top_alignment(self, align_top):
        if self.align_top != align_top:
            self.align_top = align_top
            self._paint(self.winfo_width(), self.winfo_height())

    def _redraw(self, event):
        self._paint(event.width, event.height)


def layout_overlapping_hand(tiles: Sequence[CardFace], width: int, *,
                            max_face_width: int = 76) -> float:
    """Lay out a left-aligned hand with 35% to 50% of each covered card visible."""
    count = len(tiles)
    # Expose half of each card normally, and at least 35% on narrow windows.
    face_width = min(max_face_width, max(1, (width - 4) / (1 + max(0, count - 1) * .35)))
    step = min(face_width * .5, max(face_width * .35,
               (width - 4 - face_width) / max(1, count - 1)))
    for index, tile in enumerate(tiles):
        tile._set_top_alignment(False)
        tile.place(x=round(index * step), y=0 if tile.selected else 5,
                   width=round(face_width + 4), height=round(face_width * 2 + 4))
        tk.Misc.lift(tile)
    return face_width


def layout_rank_stacked_hand(tiles: Sequence[CardFace], width: int, height: int,
                             *, max_face_width: int = 64, fixed_face_width: int | None = None) -> float:
    """Group equal ranks in columns, exposing each covered card's corner index."""
    columns = {}
    for tile in tiles:
        columns.setdefault(tile.rank, []).append(tile)
    count = len(columns)
    depth = max((len(column) for column in columns.values()), default=1)
    # Keep the top rank and suit visible; reserve room for selection lift.
    face_width = max(1, min(max_face_width,
                          (width - 4 - max(0, count - 1) * 6) / max(1, count),
                          (height - 10) / (2 + (depth - 1) * .72)))
    if fixed_face_width is not None:
        face_width = max(1, fixed_face_width)
    cell_width = round(face_width + 4)
    step_x = min(face_width + 6, max(0, (width - cell_width) / max(1, count - 1)))
    step_y = min(face_width * .72,
                 max(0, (height - 10 - face_width * 2) / max(1, depth - 1)))
    for col, column in enumerate(columns.values()):
        for row, tile in enumerate(column):
            tile._set_top_alignment(True)
            tile.place(x=round(col * step_x),
                       y=round(row * step_y) + (0 if tile.selected else 6),
                       width=cell_width, height=round(face_width * 2 + 4))
            tk.Misc.lift(tile)
    return face_width


class CardStrip(tk.Canvas):
    """出牌区整组牌自适应显示，不改变日志中的文本牌面。"""
    def __init__(self, master, *, background='#164d42', height=50):
        super().__init__(master, width=1, height=height, bg=background, highlightthickness=0)
        self.cards: list[tuple[str, int]] = []
        self.level_rank: int | None = None
        self.bind('<Configure>', self._redraw)

    def set_cards(self, cards: Sequence[tuple[str, int]], level_rank: int | None = None):
        self.cards = list(cards)
        self.level_rank = level_rank
        self._paint()

    def _redraw(self, event):
        self._paint()

    def _paint(self):
        self.delete('all')
        if not self.cards:
            return
        width, height = self.winfo_width(), self.winfo_height()
        count = len(self.cards)
        face_width = max(1, min((height - 4) / 2,
                               (width - 4) / (1 + (count - 1) * .35)))
        step = min(face_width * .5, max(face_width * .35,
                   (width - 4 - face_width) / max(1, count - 1)))
        cell = face_width + 4
        offset = max(0, (width - cell - (count - 1) * step) / 2)
        for index, (suit, rank) in enumerate(self.cards):
            draw_card(self, suit, rank, offset+index*step, 0, cell, height,
                      wildcard=suit == 'heart' and rank == self.level_rank)
