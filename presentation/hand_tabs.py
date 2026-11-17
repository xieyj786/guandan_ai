"""GUI hand tabs and public played-card display; no game or strategy mutation."""
import tkinter as tk
from tkinter import ttk
from game_engine.card import Rank, Suit
from presentation.cards import CardFace


class HandTabsMixin:
    def _build_hand_header(self):
        self.hand_tab = 0
        header = tk.Frame(self.hand_panel, bg=self.PANEL)
        header.pack(fill='x', padx=10, pady=6)
        self.hand_header = header
        self.hand_tabs = []
        for seat, name in enumerate(('你的手牌', '对手E手牌', '队友N手牌', '对手W手牌')):
            button = tk.Button(header, text=name, command=lambda s=seat: self._select_hand_tab(s),
                               bg=self.PANEL, fg=self.GOLD, activebackground=self.BG,
                               activeforeground=self.GOLD, relief='flat', bd=0,
                               font=('Arial', 12, 'bold'), padx=5, pady=3)
            self.hand_tabs.append(button)
        self.hand_count = tk.Label(header, bg=self.PANEL, fg='white', font=('Arial', 10))
        self.wildcard_hint = tk.Label(header, text='金框：红心配', bg=self.PANEL,
                                      fg=self.GOLD, font=('Arial', 12, 'bold'))
        self.key_cards_tab = tk.Button(header, text='已出关键牌', command=lambda: self._select_hand_tab('key'),
                                      bg=self.PANEL, fg=self.GOLD, activebackground=self.BG,
                                      activeforeground=self.GOLD, relief='flat', bd=0,
                                      font=('Arial', 12, 'bold'), padx=5, pady=3)

    def _select_hand_tab(self, tab):
        if tab == 'key' and not self.human_mode:
            return
        self.hand_tab = tab
        self._draw_hand()

    def _hand_cards(self):
        seat = 0 if self.human_mode or self.hand_tab == 'key' else self.hand_tab
        return self.match.hands[seat]

    def _render_hand(self):
        # Repack only header children, keeping a fixed single-line header in both modes.
        for widget in self.hand_header.winfo_children():
            widget.pack_forget()
        for seat, button in enumerate(self.hand_tabs):
            if not self.human_mode or seat == 0:
                button.configure(fg='yellow' if self.hand_tab == seat else '#9eb7b1')
                button.pack(side='left', padx=(0, 4))
        cards = self._hand_cards()
        count = f'{len(cards)}张'
        if self.human_mode:
            count += f' · 已选{len(self.selected_cards)}张'
        self.hand_count.configure(text=count)
        self.hand_count.pack(side='left', padx=6)
        self.wildcard_hint.pack(side='right')
        if self.human_mode:
            self.key_cards_tab.configure(fg='yellow' if self.hand_tab == 'key' else '#9eb7b1')
            self.key_cards_tab.pack(side='right', padx=(8, 6))
        self.key_card_groups = []
        if self.human_mode and self.hand_tab == 'key':
            self._render_key_cards()
        else:
            super()._render_hand()
            if not self.human_mode:
                for tile in self.hand_tiles:
                    tile.unbind('<Button-1>')
                    tile.configure(cursor='')

    def _render_key_cards(self):
        level = self.match.level_rank
        ranks = (Rank.BIG_JOKER, Rank.SMALL_JOKER, level, Rank.ACE, Rank.TEN, Rank.FIVE)
        self.key_card_groups = [
            [c for c in self.match.played_cards if c.rank == rank] for rank in ranks]
        note = '本轮已出 · 按牌面统计'
        if level in (Rank.ACE, Rank.TEN, Rank.FIVE):
            note += ' · 级牌与同点数列重复显示'
        tk.Label(self.hand_row, text=note, bg=self.PANEL, fg=self.GOLD,
                 font=('Arial', 10)).pack(anchor='w', padx=8)
        body = tk.Frame(self.hand_row, bg=self.PANEL)
        body.pack(fill='both', expand=True)
        canvas = self.key_canvas = tk.Canvas(body, bg=self.PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient='vertical', command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        self.key_content = tk.Frame(canvas, bg=self.PANEL)
        self.key_window = canvas.create_window(0, 0, window=self.key_content, anchor='nw')
        self.key_columns = []
        for label, cards in zip(('大王', '小王', '级牌', 'A', '10', '5'), self.key_card_groups):
            title = tk.Label(self.key_content, text=f'{label} {len(cards)}张', bg=self.PANEL,
                             fg='white', font=('Arial', 11, 'bold'))
            tiles = [CardFace(self.key_content, c.suit.value, int(c.rank), background=self.PANEL,
                              wildcard=c.suit == Suit.HEART and c.rank == level) for c in cards]
            self.key_columns.append((title, tiles))
        canvas.bind('<Configure>', lambda event: self._layout_key_cards())
        def scroll(event):
            units = (-1 if event.num == 4 else 1) if event.num in (4, 5) else (-1 if event.delta > 0 else 1)
            canvas.yview_scroll(units, 'units')
            return 'break'
        for widget in (canvas, self.key_content, *(w for title, tiles in self.key_columns for w in (title, *tiles))):
            for event in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
                widget.bind(event, scroll)
        self._layout_key_cards()

    def _layout_hand(self, width=None):
        if self.human_mode and getattr(self, 'hand_tab', 0) == 'key':
            if hasattr(self, 'key_canvas') and self.key_canvas.winfo_exists():
                self._layout_key_cards()
            return
        super()._layout_hand(width)

    def _layout_key_cards(self):
        width = max(6, self.key_canvas.winfo_width())
        column_width = width / 6
        face_width = max(1, min(76, column_width - 10))
        height = face_width * 2 + 4
        step_y = face_width * .72
        depth = max((len(tiles) for _, tiles in self.key_columns), default=0)
        content_height = round(32 + height + max(0, depth - 1) * step_y)
        self.key_canvas.itemconfigure(self.key_window, width=width, height=content_height)
        for col, (title, tiles) in enumerate(self.key_columns):
            x = col * column_width
            title.place(x=round(x), y=0, width=round(column_width), height=24)
            for row, tile in enumerate(tiles):
                tile._set_top_alignment(True)
                tile.place(x=round(x + (column_width - face_width - 4) / 2),
                           y=round(28 + row * step_y), width=round(face_width + 4), height=round(height))
                tk.Misc.lift(tile)
        self.key_canvas.configure(scrollregion=(0, 0, width, content_height))
