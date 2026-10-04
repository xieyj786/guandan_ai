"""共享扑克牌视觉组件：白底圆角，花色在上、衬线点数在下。

只依赖标准库 tkinter；输入 suit 字符串和 rank 整数，不依赖任何项目的规则引擎。
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence

WHITE = "#ffffff"
BLACK = "#101010"
RED = "#c81018"
GOLD = "#e5b94e"
SELECTED = "#63c9ff"
STYLE_VERSION = "1.0"

# 花色路径采用0～100坐标，M=起点，C=三次贝塞尔曲线，L=直线。
HEART = [('M', 50, 96), ('C', 43, 83, 2, 57, 2, 29),
         ('C', 2, -2, 39, -8, 50, 24), ('C', 61, -8, 98, -2, 98, 29),
         ('C', 98, 57, 57, 83, 50, 96)]
SPADE = [('M', 50, 0), ('C', 39, 23, 8, 42, 8, 63),
         ('C', 8, 89, 36, 90, 47, 71), ('C', 47, 84, 40, 94, 31, 99),
         ('L', 69, 99), ('C', 60, 94, 53, 84, 53, 71),
         ('C', 64, 90, 92, 89, 92, 63), ('C', 92, 42, 61, 23, 50, 0)]
DIAMOND = [('M', 50, 0), ('C', 39, 20, 20, 39, 8, 50),
           ('C', 23, 63, 40, 82, 50, 100), ('C', 60, 82, 77, 63, 92, 50),
           ('C', 80, 39, 61, 20, 50, 0)]
STEM = [('M', 48, 59), ('C', 48, 80, 39, 94, 29, 100),
        ('L', 71, 100), ('C', 61, 94, 52, 80, 52, 59)]
PATHS = {'spade': SPADE, 'heart': HEART, 'diamond': DIAMOND}


def rank_text(rank: int) -> str:
    return {11: 'J', 12: 'Q', 13: 'K', 14: 'A', 15: '小王', 16: '大王'}.get(rank, str(rank))


def _points(path):
    points = []
    x = y = 0.0
    for command in path:
        if command[0] in ('M', 'L'):
            x, y = command[1:]
            points.append((x, y))
        else:
            x1, y1, x2, y2, end_x, end_y = command[1:]
            for step in range(1, 17):
                t = step / 16
                u = 1 - t
                points.append((u**3*x + 3*u*u*t*x1 + 3*u*t*t*x2 + t**3*end_x,
                               u**3*y + 3*u*u*t*y1 + 3*u*t*t*y2 + t**3*end_y))
            x, y = end_x, end_y
    return points


def draw_card(canvas: tk.Canvas, suit: str, rank: int, x: float, y: float,
              width: float, height: float, *, wildcard=False, selected=False) -> None:
    """在指定矩形内按1:2比例绘制牌面；高亮只加外框，保留白色牌面。"""
    w = min(width - 4, (height - 4) / 2)
    if w <= 0:
        return
    h = w * 2
    left, top = x + (width-w)/2, y + (height-h)/2
    right, bottom = left+w, top+h
    radius = w * .08
    outline = SELECTED if selected else GOLD if wildcard else BLACK
    coords = [left+radius, top, right-radius, top, right, top, right, top+radius,
              right, bottom-radius, right, bottom, right-radius, bottom, left+radius, bottom,
              left, bottom, left, bottom-radius, left, top+radius, left, top]
    canvas.create_polygon(coords, smooth=True, splinesteps=16, fill=WHITE,
                          outline=outline, width=2 if selected or wildcard else max(1, w*.012))
    color = RED if suit in ('heart', 'diamond') or rank == 16 else BLACK
    sx, sy, size = left+w*.14, top+h*.13, w*.72

    def path(shape):
        canvas.create_polygon([value for px, py in _points(shape)
                               for value in (sx+px*size/100, sy+py*size/100)], fill=color, outline='')

    if suit in PATHS:
        path(PATHS[suit])
    elif suit == 'club':
        for cx, cy, r in ((50, 26, 24), (24, 63, 23), (76, 63, 23), (50, 57, 16)):
            canvas.create_oval(sx+(cx-r)*size/100, sy+(cy-r)*size/100,
                               sx+(cx+r)*size/100, sy+(cy+r)*size/100, fill=color, outline='')
        path(STEM)
    else:
        # 原参考图未包含王：暂用同色星形，明确标出大小王。
        canvas.create_text(left+w/2, sy+size/2, text='★', fill=color,
                           font=('Arial', -max(8, round(size*.85))))
    font_size = w * (.42 if rank in (15, 16) else .74)
    family = 'Arial' if rank in (15, 16) else 'Times New Roman'
    canvas.create_text(left+w/2, top+h*.72, text=rank_text(rank), fill=color,
                       font=(family, -max(8, round(font_size)), 'bold'))


class CardFace(tk.Canvas):
    """单张可缩放的牌面，可直接绑定 <Button-1>，两副牌保留两个独立控件。"""
    def __init__(self, master, suit: str, rank: int, *, width=36, height=72,
                 background='#123c35', wildcard=False, selected=False):
        super().__init__(master, width=width, height=height, bg=background,
                         highlightthickness=0, bd=0)
        self.suit, self.rank = suit, rank
        self.wildcard, self.selected = wildcard, selected
        self.bind('<Configure>', self._redraw)
        self._paint(width, height)

    def _paint(self, width, height):
        self.delete('all')
        draw_card(self, self.suit, self.rank, 0, 0, width, height,
                  wildcard=self.wildcard, selected=self.selected)

    def _redraw(self, event):
        self._paint(event.width, event.height)


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
        cell = min(width / len(self.cards), height / 2 + 2)
        offset = (width-cell*len(self.cards))/2
        for index, (suit, rank) in enumerate(self.cards):
            draw_card(self, suit, rank, offset+index*cell, 0, cell, height,
                      wildcard=suit == 'heart' and rank == self.level_rank)
