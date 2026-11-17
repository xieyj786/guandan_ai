"""Shared desktop table view, independent of network clients and game controllers."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, font as tkfont
from game_engine.card import Suit, single_card_power
from presentation.cards import CardFace, FELT, layout_rank_stacked_hand
from presentation.play_display import PlayStrip


class GameTableView:
    def _extra_control_buttons(self):
        return ()

    def _build_extra_controls(self, controls):
        pass

    def _build_ui(self):
        self.action_font = tkfont.nametofont("TkDefaultFont").copy()
        self.action_font.configure(size=14, weight="bold")
        previous_line_height = self.action_font.metrics("linespace")
        self.action_font.configure(family="Arial", size=12, weight="bold")
        vertical_padding = max(0, 2 + (previous_line_height - self.action_font.metrics("linespace")) / 2)
        style = ttk.Style(self.root)
        style.configure("GameAction.TButton", font=self.action_font, foreground=self.GOLD,
                        padding=(10, vertical_padding))
        style.map("GameAction.TButton", foreground=[("disabled", "#888888"),
                                                   ("!disabled", self.GOLD)])
        # A coloured frame remains visible even when the native ttk theme ignores
        # button background colours (notably on macOS).
        for name, foreground in (("PromptOn", "#fff4b8"), ("PromptOff", self.GOLD)):
            style.configure(f"{name}.GameAction.TButton", font=self.action_font,
                            padding=(10, vertical_padding))
            style.map(f"{name}.GameAction.TButton",
                      foreground=[("disabled", "#888888"), ("!disabled", foreground)])
        top = tk.Frame(self.root, bg="#092521", height=82)
        top.pack(fill="x")
        tk.Label(top, text="掼蛋", font=("Microsoft YaHei UI", 19, "bold"), fg="white", bg="#092521").pack(side="left", padx=22)
        self.status = tk.Label(top, text="准备开始", font=("Microsoft YaHei UI", 11), fg=self.GOLD, bg="#092521")
        self.status.pack(side="left", padx=20)
        self.level_a = tk.Label(top, text="A队进度：-", font=("Microsoft YaHei UI", 10), fg="#f3d37a", bg="#092521")
        self.level_a.pack(side="left", padx=(6, 10))
        self.level_b = tk.Label(top, text="B队进度：-", font=("Microsoft YaHei UI", 10), fg="#9fd4ff", bg="#092521")
        self.level_b.pack(side="left", padx=6)
        controls = tk.Frame(self.root, bg=self.BG)
        controls.pack(fill="x", padx=14, pady=(4, 0))
        self.control_buttons = {}
        for text, command in (("新局", self.new_game), ("单步", self.single_step),
                              ("看AI对战", self.toggle_auto), ("人机对战", self.start_human_game)) + self._extra_control_buttons():
            button = ttk.Button(controls, text=text, command=command, width=8)
            button.pack(side="left", padx=2)
            self.control_buttons[text] = button
        self._build_extra_controls(controls)
        self.auto_button = self.control_buttons["看AI对战"]
        # Layout percentages use the whole window width and the height below New Game.
        self.table = tk.Frame(self.root, bg=self.BG)
        self.upper_area = tk.Frame(self.table, bg=self.BG)
        self.root.bind("<Configure>", self._schedule_region_layout, add="+")
        controls.bind("<Configure>", self._schedule_region_layout)
        self.control_buttons["新局"].bind("<Configure>", self._schedule_region_layout)
        self.root.after_idle(self._layout_regions)
        self.center = tk.Frame(self.upper_area, bg=FELT, highlightbackground="#7c925b",
                               highlightthickness=1)
        self.center.grid_propagate(False)
        self.center.columnconfigure(1, weight=1)
        self.center.rowconfigure(1, weight=1)
        self.seats = {}
        self.seat_labels = {}
        for index, row, col in ((2, 0, 1), (3, 1, 0), (1, 1, 2), (0, 2, 1)):
            panel = tk.Frame(self.center, bg=FELT)
            panel.grid(row=row, column=col, sticky="ns" if index in (1, 3) else "ew")
            label = tk.Label(panel, bg=FELT, font=("Arial", 11, "bold"))
            label.configure(width=4 if index in (1, 3) else 1, height=5 if index in (1, 3) else 1)
            label.pack(fill="x", expand=True, padx=6, pady=5)
            self.seats[index] = panel
            self.seat_labels[index] = label
        self.play_area = tk.Frame(self.center, bg=FELT)
        self.play_area.grid(row=1, column=1, sticky="nsew")
        self.play_area.bind("<Configure>", self._resize_table_cards)
        self.play_area.grid_propagate(False)
        self.play_area.columnconfigure(0, weight=1)
        self.play_area.rowconfigure(0, weight=1)
        slots = tk.Frame(self.play_area, bg=FELT)
        slots.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        for row in range(3):
            slots.rowconfigure(row, weight=1, uniform="plays")
        for col in range(3):
            slots.columnconfigure(col, weight=1, uniform="plays")
        self.play_prompt = tk.Label(slots, bg=FELT, fg="#d8eee8",
                                    font=("Microsoft YaHei UI", 11), wraplength=110)
        self.play_prompt.grid(row=1, column=1, sticky="nsew")
        self.play_prompt.bind("<Configure>", self._resize_play_label)
        self.hand_panel = tk.Frame(self.table, bg=self.PANEL)
        self.hand_panel.pack_propagate(False)
        self._build_hand_header()
        self.play_labels = {}
        self.play_faces = {}
        for index, row, col in ((2, 0, 1), (3, 1, 0), (1, 1, 2), (0, 2, 1)):
            slot = tk.Frame(slots, bg=FELT)
            slot.grid(row=row, column=col, sticky="nsew")
            slot.grid_propagate(False)
            slot.columnconfigure(0, weight=1)
            slot.rowconfigure(0, weight=1)
            label = tk.Label(slot, bg=FELT, anchor="e" if index == 1 else "w")
            faces = PlayStrip(slot, background=FELT, status_button=self.control_buttons["新局"], status_width_chars=5, fixed_card_size=True,
                              alignment={3: "right", 1: "left", 0: "top", 2: "bottom"}[index])
            faces.grid(row=0, column=0, sticky="nsew")
            self.play_labels[index] = label
            self.play_faces[index] = faces
        record = self.record_panel = tk.Frame(self.upper_area, bg=self.PANEL)
        record.grid_propagate(False)
        record.columnconfigure(0, weight=1)
        record.rowconfigure(1, weight=1)
        tk.Label(record, text="出牌记录 / 提示", bg=self.PANEL, fg=self.GOLD,
                 font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(2, 4))
        self.log = tk.Text(record, width=1, height=1, bg="#08211e", fg="#d8eee8",
                           relief="flat", wrap="word", state="disabled", font=("Consolas", 11))
        self.log.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
        scroll = ttk.Scrollbar(record, command=self.log.yview)
        scroll.grid(row=1, column=1, sticky="ns", pady=(0, 8))
        self.log.configure(yscrollcommand=scroll.set)
        self.log.tag_configure("team_a", foreground=self.TEAM_YELLOW)
        self.log.tag_configure("team_b", foreground=self.TEAM_BLUE)

    def _build_hand_header(self):
        hand_header = tk.Frame(self.hand_panel, bg=self.PANEL)
        hand_header.pack(fill="x", padx=10, pady=6)
        tk.Label(hand_header, text="AI1你的手牌", bg=self.PANEL,
                 fg=self.GOLD, font=("Arial", 12, "bold")).pack(side="left")
        tk.Label(hand_header, text="金框：红心配", bg=self.PANEL,
                 fg=self.GOLD, font=("Arial", 12, "bold")).pack(side="right")

    def _hand_cards(self):
        return self.match.hands[0]

    def _schedule_region_layout(self, event):
        if event.widget in (self.root, self.control_buttons["新局"],
                            self.control_buttons["新局"].master):
            self.root.after_idle(self._layout_regions)

    def _layout_regions(self):
        if self.closed:
            return
        button = self.control_buttons["新局"]
        top = button.master.winfo_y() + button.winfo_y() + button.winfo_height()
        width = self.root.winfo_width()
        height = max(1, self.root.winfo_height() - top)
        self.table.place(x=0, y=top, width=width, height=height)
        # Split the spare 5% equally between left/middle/right and top/middle/bottom.
        gap_x, gap_y = width * .05 / 3, height * .05 / 3
        table_width, table_height = round(width * .65), round(height * .60)
        self.upper_area.place(x=0, y=round(gap_y), width=width, height=table_height)
        self.center.place(x=round(gap_x), y=0, width=table_width, height=table_height)
        self.record_panel.place(x=round(2 * gap_x + width * .65), y=0,
                                width=round(width * .30), height=table_height)
        hand_y = round(2 * gap_y + height * .60)
        hand_width, hand_height = round(width * .78), round(height * .35)
        self.hand_panel.place(x=round(gap_x), y=hand_y,
                              width=hand_width, height=hand_height)
        if hasattr(self, "action_row"):
            action_x = round(gap_x) + hand_width
            self.action_row.place(x=action_x, y=hand_y,
                                  width=max(1, round(width - gap_x) - action_x),
                                  height=hand_height)

    def _resize_play_cards(self, event):
        self._layout_hand(event.width)

    def _layout_hand(self, width=None):
        if not hasattr(self, "hand_tiles"):
            return
        width = max(1, width if width is not None else self.hand_row.winfo_width())
        layout_rank_stacked_hand(
            self.hand_tiles, width, max(1, self.hand_row.winfo_height()),
            fixed_face_width=getattr(self, "hand_card_width", None),
            max_face_width=76)

    def _resize_table_cards(self, event):
        # Seat captions already occupy the two text lines outside play_area.
        # Reserve the slots' margins and leave 4px around each of three card rows.
        face_width = max(1, ((event.height - 8) // 3 - 8) // 2)
        self.table_card_width = face_width
        # Size follows the table geometry, never the remaining hand or stack depth.
        self.hand_card_width = max(1, round(face_width * 1.10))
        for faces in self.play_faces.values():
            faces.set_card_width(face_width)
        self._layout_hand()

    def _resize_play_label(self, event: tk.Event) -> None:
        widget = event.widget
        if isinstance(widget, tk.Label):
            widget.configure(wraplength=max(60, event.width - 10))

    def _label(self, parent, text, size=11, color="white", bold=False):
        return tk.Label(parent, text=text, fg=color, bg=self.BG, font=("Microsoft YaHei UI", size, "bold" if bold else "normal"))

    def _team_color(self, team):
        return self.TEAM_YELLOW if team == self.leading_team else self.TEAM_BLUE

    def _draw_table(self):
        m = self.match
        if not m:
            return
        self.play_prompt.configure(text="")
        for index, panel in self.seats.items():
            team = "A" if index % 2 == 0 else "B"
            # Pad with a digit-width figure space to keep the count aligned.
            count = str(len(m.hands[index])).rjust(2, '\u2007')
            remaining = f"剩余 {count} 张"
            if index in m.finish_order:
                remaining += f" · {('头游', '二游', '三游', '末游')[m.finish_order.index(index)]}"
            if index in (1, 3):
                # West's displayed AI3 follows the requested seat caption.
                name = "AI2" if index == 1 else "AI3"
                text = f"B队\n{name}\n剩余\n{len(m.hands[index])}\n张"
            else:
                text = f"A队- AI{index + 1}{' 你' if index == 0 else ''} {remaining}"
            self.seat_labels[index].configure(text=text, fg=self._team_color(team))
            play_status, shown_cards = self._play_display_state(index)
            self.play_labels[index].configure(text='')
            if shown_cards:
                self.play_faces[index].set_cards([(c.suit.value, int(c.rank)) for c in shown_cards], int(m.level_rank))
            else:
                self.play_faces[index].set_status('PASS' if play_status == 'PASS' else '')
            self.play_faces[index].set_finished(index in m.finish_order and bool(shown_cards), self._team_color(team))
        self._draw_hand()

    def _play_display_state(self, index):
        m = self.match
        if m is None:
            return '', []
        if index in m.finish_order:
            return ('头游', '二游', '三游', '末游')[m.finish_order.index(index)], self.player_cards[index]
        if self.turns == 0 or index == m.current_player:
            return '等待出牌', []
        if self.player_cards[index]:
            return '', self.player_cards[index]
        # 本局尚未行动的座位在首个动作后留空，不继续显示等待。
        return ('PASS' if self.player_plays[index] == '过牌' else ''), []

    def _draw_hand(self):
        self._stop_action_flash()
        if hasattr(self, "action_row"):
            self.action_highlights = {name: button.master for name, button in self.action_buttons.items()}
        m = self.match
        if m is None:
            return
        frame = self.hand_panel
        if not hasattr(self, 'hand_row'):
            self.hand_body = tk.Frame(frame, bg=self.PANEL)
            self.hand_body.pack(fill="both", expand=True, padx=2, pady=5)
            self.hand_body.columnconfigure(0, weight=1)
            self.hand_body.rowconfigure(0, weight=1)
            self.hand_row = tk.Frame(self.hand_body, bg=self.PANEL, width=1, height=238)
            self.hand_row.grid(row=0, column=0, sticky="nsew")
            self.hand_row.grid_propagate(False)
            self.hand_row.bind("<Configure>", self._resize_play_cards)
        for tile in self.hand_row.winfo_children():
            tile.destroy()
        self.hand_tiles = []
        self._render_hand()
        can_act = self._human_can_play()
        pending = self._pending_exchange_kind()
        states = {
            "出牌": can_act,
            "过牌": can_act and m.last_play is not None,
            "提示": can_act,
            "进还贡": self.human_mode and pending in ("tribute", "return"),
        }
        if not hasattr(self, 'action_row'):
            actions = self.action_row = tk.Frame(
                self.table, bg=self.BG, width=1, height=1,
                highlightthickness=0)
            actions.pack_propagate(False)
            actions.columnconfigure(0, weight=1)
            for row in range(5):
                actions.rowconfigure(row, weight=1, uniform="action_rows")
            self.root.after_idle(self._layout_regions)
            self.action_buttons = {}
            commands = {"出牌": self._play_selected, "过牌": self._pass_human,
                        "提示": self._hint_human,
                        "进还贡": self._submit_pending_exchange}
            button_width = max(1, round(self.action_font.measure("进还贡牌") /
                                        self.action_font.measure("0")))
            for row, name in enumerate(("出牌", "过牌", "提示", "进还贡")):
                highlight = tk.Frame(actions, bg=self.BG)
                highlight.grid(row=row, column=0)
                button = ttk.Button(highlight, text=name, command=commands[name],
                                    style="GameAction.TButton", width=button_width,
                                    state="normal" if states[name] and not self.failed else "disabled")
                button.pack(padx=3, pady=3)
                self.action_buttons[name] = button
                self.action_highlights[name] = highlight
            self.hand_hint = tk.Label(actions, bg=self.BG, fg="#b9d6ce", font=("Arial", 10),
                                      wraplength=138, justify="center")
            self.hand_hint.grid(row=4, column=0, sticky="ew", padx=6)
        self.hand_hint.configure(text="点击手牌选择，再点击对应动作" if self.human_mode else "AI观察模式 · AI1由程序控制")
        for name, button in self.action_buttons.items():
            button.configure(state="normal" if states[name] and not self.failed else "disabled")
        self.action_buttons["进还贡"].configure(
            text="进贡" if pending == "tribute" else "还贡" if pending == "return" else "进/还贡")
        self._flash_action_buttons()

    def _render_hand(self):
        m = self.match
        for col, card in enumerate(sorted(self._hand_cards(), key=lambda c: single_card_power(c, m.level_rank))):
            selected = any(card is item for item in self.selected_cards)
            tile = CardFace(self.hand_row, card.suit.value, int(card.rank), background=self.PANEL,
                            wildcard=card.suit == Suit.HEART and card.rank == m.level_rank,
                            selected=selected)
            tile.configure(cursor="hand2")
            tile.bind("<Button-1>", lambda event, c=card: self._toggle_card(c))
            self.hand_tiles.append(tile)
        self._layout_hand()

    def _stop_action_flash(self):
        """Cancel the previous timer before redrawing or destroying its widgets."""
        if self.action_flash_id is not None:
            self.root.after_cancel(self.action_flash_id)
            self.action_flash_id = None
        self.action_flash_on = False
        self.action_highlights = {}

    def _flash_action_buttons(self):
        """Pulse every enabled human action together; never hide the button text."""
        self.action_flash_id = None
        waiting = (not self.closed and self.human_mode and not self.failed
                   and not self.series_finished and self.match is not None
                   and (self._human_can_play() or self._pending_exchange_kind() is not None))
        enabled = [name for name, button in self.action_buttons.items()
                   if waiting and str(button.cget("state")) != "disabled"]
        self.action_flash_on = bool(enabled) and not self.action_flash_on
        for name, highlight in self.action_highlights.items():
            active = name in enabled
            highlight.configure(bg=("#ffe66d" if self.action_flash_on else "#92723c")
                                if active else self.BG)
            self.action_buttons[name].configure(
                style=("PromptOn.GameAction.TButton" if self.action_flash_on else
                       "PromptOff.GameAction.TButton") if active else "GameAction.TButton")
        if enabled:
            self.action_flash_id = self.root.after(550, self._flash_action_buttons)
