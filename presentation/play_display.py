"""牌桌动作展示：沿用共享牌面，PASS 与工具栏按钮保持相同尺寸和字体。"""
from tkinter import ttk, font as tkfont

from presentation.cards import CardStrip, WHITE, BLACK, draw_card


class PlayStrip(CardStrip):
    def __init__(self, master, *, alignment="center", status_button=None, status_width_chars=None, fixed_card_size=False, **kwargs):
        self.fixed_card_size = fixed_card_size
        self.status_width_chars = status_width_chars
        self.status_button = status_button
        self.alignment = alignment
        self.status_text = ''
        self.finished = False
        self.finished_color = None
        self.target_card_width = None
        super().__init__(master, **kwargs)

    def set_status(self, text):
        self.status_text = text
        self.set_cards([])

    def set_cards(self, cards, level_rank=None):
        if cards:
            self.status_text = ''
        super().set_cards(cards, level_rank)

    def set_finished(self, finished, color=None):
        self.finished = bool(finished)
        self.finished_color = color if self.finished else None
        self._paint()

    def set_card_width(self, width):
        self.target_card_width = max(1, width)
        self._paint()

    def _paint(self):
        if self.cards and self.target_card_width is not None:
            self.delete('all')
            width, height = self.winfo_width(), self.winfo_height()
            # Overlap multi-card plays while keeping the whole group visible.
            count = len(self.cards)
            face_width = min(self.target_card_width, max(0, (height-4)/2),
                             max(0, (width-4)/(1 + (count-1)*.35)))
            if self.fixed_card_size:
                face_width = self.target_card_width
            cell = face_width + 4
            step = min(face_width*.5, max(face_width*.35,
                       (width-cell)/max(1, count-1)))
            if self.fixed_card_size:
                step = min(face_width * .5, max(0, (width-cell)/max(1, count-1)))
            group_width = cell + step * (count-1)
            offset = width - group_width if self.alignment == 'right' else 0 if self.alignment == 'left' else (width-group_width)/2
            face_height = face_width * 2 + 4
            top = 0 if self.alignment == 'top' else height-face_height if self.alignment == 'bottom' else (height-face_height)/2
            for index, (suit, rank) in enumerate(self.cards):
                draw_card(self, suit, rank, offset+index*step, top, cell, face_height,
                          wildcard=suit == 'heart' and rank == self.level_rank,
                          finished_color=self.finished_color)
            return
        super()._paint()
        if self.cards or not self.status_text:
            return
        width, height = self.winfo_width(), self.winfo_height()
        button = self.status_button
        if button is not None:
            w, h = button.winfo_width(), button.winfo_height()
            if w <= 1 or h <= 1:
                w, h = button.winfo_reqwidth(), button.winfo_reqheight()
            style_name = button.cget('style') or 'TButton'
        else:
            w, h, style_name = 65, 28, 'TButton'
        font = ttk.Style(self).lookup(style_name, 'font') or 'TkDefaultFont'
        if self.status_width_chars is not None:
            w = tkfont.Font(root=self, font=font).measure('M' * self.status_width_chars)
        left = width-w if self.alignment == 'right' else 0 if self.alignment == 'left' else (width-w)/2
        top = 0 if self.alignment == 'top' else height-h if self.alignment == 'bottom' else (height-h)/2
        self.create_rectangle(left+.5, top+.5, left+w-.5, top+h-.5,
                              fill=WHITE, outline=BLACK, width=1, tags='status_box')
        self.create_text(left+w/2, top+h/2, text=self.status_text,
                         fill=BLACK, font=font, tags='status_text')
