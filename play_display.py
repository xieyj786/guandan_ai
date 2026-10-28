"""牌桌动作展示：沿用共享牌面，PASS 使用约三张牌宽的醒目标识。"""
from card_ui import CardStrip, WHITE, BLACK, draw_card


class PlayStrip(CardStrip):
    def __init__(self, master, **kwargs):
        self.status_text = ''
        self.target_card_width = None
        super().__init__(master, **kwargs)

    def set_status(self, text):
        self.status_text = text
        self.set_cards([])

    def set_cards(self, cards, level_rank=None):
        if cards:
            self.status_text = ''
        super().set_cards(cards, level_rank)

    def set_card_width(self, width):
        self.target_card_width = max(1, width)
        self._paint()

    def _paint(self):
        if self.cards and self.target_card_width is not None:
            self.delete('all')
            width, height = self.winfo_width(), self.winfo_height()
            # Keep full cards visible; shrink only when the entire group cannot fit.
            face_width = min(self.target_card_width, max(0, (height-4)/2),
                             max(0, width/len(self.cards)-4))
            cell = face_width + 4
            offset = (width-cell*len(self.cards))/2
            for index, (suit, rank) in enumerate(self.cards):
                draw_card(self, suit, rank, offset+index*cell, 0, cell, height,
                          wildcard=suit == 'heart' and rank == self.level_rank)
            return
        super()._paint()
        if self.cards or not self.status_text:
            return
        width, height = self.winfo_width(), self.winfo_height()
        cell = min(width, height / 2 + 2)
        card_width = min(cell - 4, (height - 4) / 2)
        if card_width <= 0:
            return
        w = min(width - 4, card_width * 3)
        font_size = max(1, round(min(w*.29, card_width*1.2)))
        text_id = self.create_text(width/2, height/2, text=self.status_text, fill=BLACK,
                                   font=('Arial', -font_size, 'bold'))
        bounds = self.bbox(text_id)
        text_height = bounds[3] - bounds[1] if bounds else font_size
        h = min(height - 4, text_height + max(4, font_size * .12))
        left, top = (width - w) / 2, (height - h) / 2
        right, bottom, radius = left + w, top + h, card_width * .08
        background_id = self.create_polygon([left+radius, top, right-radius, top, right, top,
            right, top+radius, right, bottom-radius, right, bottom,
            right-radius, bottom, left+radius, bottom, left, bottom,
            left, bottom-radius, left, top+radius, left, top],
            smooth=True, splinesteps=16, fill=WHITE, outline=BLACK, width=max(1, card_width*.012))
        self.tag_lower(background_id, text_id)
