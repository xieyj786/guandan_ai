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
STYLE_VERSION = "1.1"

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


def _draw_joker(canvas: tk.Canvas, left: float, top: float, width: float,
                height: float, *, big: bool) -> None:
    """Scale the reference jester as vector paths, retaining detail at every card size."""
    scale = width * .86 / 100
    ox, oy = left + width * .07, top + height * .13
    red, yellow = '#e60012', '#ffd21f'
    stroke = max(.7, width * .012)

    def shape(commands, fill):
        canvas.create_polygon([v for px, py in _points(commands)
                               for v in (ox + px * scale, oy + py * scale)],
                              fill=fill, outline=BLACK, width=stroke)

    def oval(x1, y1, x2, y2, fill, outline=BLACK):
        canvas.create_oval(ox+x1*scale, oy+y1*scale, ox+x2*scale, oy+y2*scale,
                           fill=fill, outline=outline, width=stroke)

    # Three curved cap points; the black crown identifies the small joker.
    shape([('M', 28, 58), ('C', 28, 21, 15, 18, 6, 38),
           ('C', 5, 9, 30, 0, 43, 21), ('C', 43, -7, 76, -8, 83, 20),
           ('C', 65, 4, 62, 29, 69, 39), ('L', 51, 57)], red)
    shape([('M', 43, 49), ('C', 36, 26, 41, 3, 59, 0),
           ('C', 70, -2, 80, 7, 83, 20), ('C', 65, 4, 62, 29, 69, 39),
           ('L', 52, 58)], red if big else BLACK)
    shape([('M', 54, 44), ('C', 61, 15, 99, 22, 94, 61),
           ('C', 88, 36, 74, 39, 71, 64), ('L', 54, 64)], yellow)
    # Collar lobes and bells.
    shape([('M', 39, 65), ('C', 20, 61, 15, 72, 12, 82),
           ('C', 25, 75, 34, 77, 43, 85), ('L', 50, 74)], red if big else BLACK)
    shape([('M', 59, 65), ('C', 77, 62, 87, 71, 89, 82),
           ('C', 75, 75, 66, 77, 58, 85), ('L', 50, 74)], red if big else BLACK)
    shape([('M', 43, 73), ('C', 41, 87, 44, 94, 50, 100),
           ('C', 58, 90, 62, 82, 58, 73)], red if big else BLACK)
    shape([('M', 41, 69), ('C', 30, 75, 25, 85, 26, 101),
           ('C', 40, 91, 45, 82, 49, 75)], yellow if big else red)
    shape([('M', 58, 69), ('C', 71, 76, 77, 87, 75, 101),
           ('C', 62, 94, 56, 83, 51, 75)], yellow if big else red)
    # Heart-shaped face and smiling eyes.
    shape([('M', 50, 46), ('C', 30, 25, 17, 45, 30, 65),
           ('C', 38, 79, 61, 81, 70, 63),
           ('C', 83, 40, 64, 27, 50, 46)], WHITE)
    for cx in (39, 61):
        shape([('M', cx-6, 53), ('C', cx-4, 43, cx+4, 43, cx+6, 53),
               ('C', cx+1, 49, cx-1, 49, cx-6, 53)], BLACK)
    oval(46, 53, 54, 61, red, '')
    shape([('M', 39, 63), ('C', 44, 66, 56, 66, 61, 63),
           ('C', 57, 75, 44, 75, 39, 63)], red)
    for cx, cy in ((6, 38), (83, 20), (94, 61), (12, 82), (89, 82), (26, 101), (75, 101)):
        oval(cx-5, cy-5, cx+5, cy+5, yellow)
    canvas.create_text(left+width/2, top+height*.81, text='JOKER',
                       fill=red if big else BLACK,
                       font=('Times New Roman', -max(5, round(width*.24)), 'bold'))


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
    if rank in (15, 16):
        _draw_joker(canvas, left, top, w, h, big=rank == 16)
        return
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
    canvas.create_text(left+w/2, top+h*.72, text=rank_text(rank), fill=color,
                       font=('Times New Roman', -max(8, round(w*.74)), 'bold'))


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
