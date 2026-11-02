"""掼蛋离线桌面入口；对局逻辑位于可供移动界面复用的 play_game.py。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, font as tkfont

from gameplay.offline import PlayGame
from game_engine.card import Card, Suit, single_card_power
from presentation.cards import CardFace
from presentation.play_display import PlayStrip


class GuandanPlay:
    BG = "#123c35"
    PANEL = "#0d2d29"
    GOLD = "#e9c46a"
    TEAM_YELLOW = "#ffe66d"
    TEAM_BLUE = "#72c7ff"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("掼蛋 · Play")
        self.root.geometry("1200x850")
        self.root.minsize(1000, 680)
        self.root.configure(bg=self.BG)
        self.game = PlayGame()
        self.closed = False
        self.running = False
        self.after_id: str | None = None
        self.action_flash_id: str | None = None
        self.action_flash_on = False
        self.action_highlights = {}
        self.failed = False
        self.selected_cards: list[Card] = []
        self._build_ui()
        self.new_game()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    @property
    def match(self):
        return self.game.match

    @property
    def human_mode(self):
        return self.game.human_mode

    @property
    def human_index(self):
        return self.game.human_index

    @property
    def round_number(self):
        return self.game.round_number

    @property
    def turns(self):
        return self.game.turns

    @property
    def series_finished(self):
        return self.game.series_finished

    @property
    def team_levels(self):
        return self.game.team_levels

    @property
    def leading_team(self):
        return self.game.leading_team

    @property
    def player_cards(self):
        return self.game.player_cards

    @property
    def player_plays(self):
        return self.game.player_plays

    @property
    def seed(self):
        return self.game.seed

    @seed.setter
    def seed(self, value):
        self.game.seed = value

    def _selected_indices(self):
        if self.match is None:
            return []
        hand = self.match.hands[self.human_index]
        return [next(i for i, card in enumerate(hand) if card is selected)
                for selected in self.selected_cards]

    def _sync_game(self):
        for message in self.game.drain_events():
            self._log(message)
        if self.match is not None:
            self.level_a.configure(text=f"本局打 {self.match.level_rank.name}（全桌）　 A队进度：{self.team_levels['A'].name}", fg=self._team_color("A"))
            self.level_b.configure(text=f"B队进度：{self.team_levels['B'].name}", fg=self._team_color("B"))
        if self.series_finished:
            self._pause()
            self.status.configure(text="A级双下，比赛结束")
        self._draw_table()

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
                              ("看AI对战", self.toggle_auto), ("人机对战", self.start_human_game)):
            button = ttk.Button(controls, text=text, command=command, width=8)
            button.pack(side="left", padx=2)
            self.control_buttons[text] = button
        self.auto_button = self.control_buttons["看AI对战"]
        self.table = tk.Frame(self.root, bg=self.BG)
        self.table.pack(fill="both", expand=True, padx=12, pady=10)
        self.table.columnconfigure(0, minsize=125)
        self.table.columnconfigure(1, weight=1)
        self.table.columnconfigure(2, minsize=125)
        self.table.rowconfigure(1, weight=1)
        self.seats = {}
        for index, row, col in ((2, 0, 1), (3, 1, 0), (1, 1, 2), (0, 2, 0)):
            panel = tk.Frame(self.table, bg=self.PANEL, padx=6, pady=6)
            panel.grid(row=row, column=col, columnspan=3 if index == 0 else 1,
                       sticky="nsew", padx=4, pady=4)
            self.seats[index] = panel
        self.center = tk.Frame(self.table, bg=self.PANEL)
        self.center.grid(row=1, column=1, sticky="nsew", padx=6, pady=4)
        self.center.columnconfigure(0, weight=1)
        self.center.rowconfigure(0, weight=3, uniform="center")
        self.center.rowconfigure(1, weight=2, uniform="center")
        self.play_area = tk.Frame(self.center, bg="#1b5b4d")
        self.play_area.grid(row=0, column=0, sticky="nsew")
        self.play_area.grid_propagate(False)
        self.play_area.columnconfigure(0, weight=1)
        self.play_area.rowconfigure(1, weight=1)
        tk.Label(self.play_area, text="当前出牌区", bg="#1b5b4d", fg=self.GOLD,
                 font=("Arial", 12, "bold")).grid(row=0, column=0, pady=5)
        slots = tk.Frame(self.play_area, bg="#1b5b4d")
        slots.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        for row in range(3):
            slots.rowconfigure(row, weight=1, uniform="plays")
        for col in range(3):
            slots.columnconfigure(col, weight=1, uniform="plays")
        self.play_labels = {}
        self.play_faces = {}
        for index, row, col in ((2, 0, 1), (3, 1, 0), (1, 1, 2), (0, 2, 1)):
            slot = tk.Frame(slots, bg="#164d42")
            slot.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
            slot.grid_propagate(False)
            slot.columnconfigure(0, weight=1)
            slot.rowconfigure(1, weight=1)
            label = tk.Label(slot, bg="#164d42", fg="white",
                             anchor="e" if index == 1 else "w",
                             justify="right" if index == 1 else "left",
                             font=("Arial", 10, "bold"))
            label.grid(row=0, column=0, sticky="ew")
            faces = PlayStrip(slot)
            faces.grid(row=1, column=0, sticky="nsew")
            self.play_labels[index] = label
            self.play_faces[index] = faces
        record = tk.Frame(self.center, bg=self.PANEL)
        record.grid(row=1, column=0, sticky="nsew")
        record.grid_propagate(False)
        record.columnconfigure(0, weight=1)
        record.rowconfigure(1, weight=1)
        tk.Label(record, text="出牌记录", bg=self.PANEL, fg=self.GOLD,
                 font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(18, 8))
        self.log = tk.Text(record, width=1, height=1, bg="#08211e", fg="#d8eee8",
                           relief="flat", wrap="word", state="disabled", font=("Consolas", 11))
        self.log.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
        scroll = ttk.Scrollbar(record, command=self.log.yview)
        scroll.grid(row=1, column=1, sticky="ns", pady=(0, 8))
        self.log.configure(yscrollcommand=scroll.set)
        self.log.tag_configure("team_a", foreground=self.TEAM_YELLOW)
        self.log.tag_configure("team_b", foreground=self.TEAM_BLUE)

    def _resize_play_cards(self, event):
        # Hand cells use 27 columns, 2px horizontal and 5px vertical padding.
        hand_width = min(max(1, event.width / 27 - 6), (82 - 5 - 4) / 2)
        target = hand_width * 2 / 3
        for faces in self.play_faces.values():
            faces.set_card_width(target)
        # Keep the configured 3:2 split; PlayStrip fits cards to available space.

    def _resize_play_label(self, event: tk.Event) -> None:
        widget = event.widget
        if isinstance(widget, tk.Label):
            widget.configure(wraplength=max(60, event.width - 10))

    def _pending_exchange_kind(self) -> str | None:
        return self.game.pending_exchange_kind

    def new_game(self, human_mode=False):
        self._pause()
        self.failed = False
        for name in ("单步", "看AI对战"):
            self.control_buttons[name].configure(state="disabled" if human_mode else "normal")
        self._clear_log()
        self.selected_cards = []
        self.game.new_game(human_mode)
        self._sync_game()
        self.status.configure(text="AI观察 · 已暂停" if not human_mode else "人机对战")
        if human_mode:
            self._continue_human()

    def start_human_game(self):
        self.new_game(human_mode=True)

    def _label(self, parent, text, size=11, color="white", bold=False):
        return tk.Label(parent, text=text, fg=color, bg=self.BG, font=("Microsoft YaHei UI", size, "bold" if bold else "normal"))

    def _team_color(self, team):
        return self.TEAM_YELLOW if team == self.leading_team else self.TEAM_BLUE

    def _draw_table(self):
        m = self.match
        if not m:
            return
        for index, panel in self.seats.items():
            for child in panel.winfo_children():
                child.destroy()
            team = "A" if index % 2 == 0 else "B"
            active = index == m.current_player and not m.is_finished(index)
            text = f"{'▶ ' if active else ''}AI{index+1} · {team}队 · 剩余 {len(m.hands[index])} 张"
            if index in m.finish_order:
                text += f" · 第{m.finish_order.index(index)+1}名"
            tk.Label(panel, text=text, bg=self.PANEL, fg=self._team_color(team),
                     wraplength=115 if index in (1, 3) else 900,
                     font=("Arial", 11, "bold")).pack(pady=4)
            if index != 0:
                tk.Label(panel, text="对手" if index in (1, 3) else "队友", bg=self.PANEL,
                         fg="#9bbcb4", font=("Arial", 10)).pack(pady=4)
            play_status, shown_cards = self._play_display_state(index)
            caption_status = '' if play_status == 'PASS' else play_status
            caption = f"{caption_status}  AI2" if index == 1 else f"AI{index+1}  {caption_status}"
            self.play_labels[index].configure(text=caption, fg=self._team_color(team))
            if shown_cards:
                self.play_faces[index].set_cards([(c.suit.value, int(c.rank)) for c in shown_cards], int(m.level_rank))
            else:
                self.play_faces[index].set_status('PASS' if play_status == 'PASS' else '')
        self._draw_hand()

    def _play_display_state(self, index):
        m = self.match
        if m is None:
            return '', []
        if index in m.finish_order:
            return ('头游', '二游', '三游', '末游')[m.finish_order.index(index)], []
        if self.turns == 0 or index == m.current_player:
            return '等待出牌', []
        if self.player_cards[index]:
            return '', self.player_cards[index]
        # 本局尚未行动的座位在首个动作后留空，不继续显示等待。
        return ('PASS' if self.player_plays[index] == '过牌' else ''), []

    def _draw_hand(self):
        self._stop_action_flash()
        m = self.match
        if m is None:
            return
        frame = self.seats[0]
        self.hand_row = tk.Frame(frame, bg=self.PANEL, height=82)
        self.hand_row.pack(fill="x", padx=2, pady=5)
        self.hand_row.grid_propagate(False)
        self.hand_row.bind("<Configure>", self._resize_play_cards)
        for col in range(max(27, len(m.hands[0]))):
            self.hand_row.columnconfigure(col, weight=1, uniform="cards")
        self.hand_row.rowconfigure(0, weight=1)
        for col, card in enumerate(sorted(m.hands[0], key=lambda c: single_card_power(c, m.level_rank))):
            selected = any(card is item for item in self.selected_cards)
            tile = CardFace(self.hand_row, card.suit.value, int(card.rank), background=self.PANEL,
                            wildcard=card.suit == Suit.HEART and card.rank == m.level_rank,
                            selected=selected)
            tile.configure(cursor="hand2")
            tile.grid(row=0, column=col, sticky="nsew", padx=1, pady=(0, 5) if selected else (5, 0))
            tile.bind("<Button-1>", lambda event, c=card: self._toggle_card(c))
        actions = tk.Frame(frame, bg=self.PANEL)
        actions.pack(pady=3)
        can_act = self._human_can_play()
        pending = self._pending_exchange_kind()
        states = {
            "出牌": can_act,
            "过牌": can_act and m.last_play is not None,
            "进贡": self.human_mode and pending == "tribute",
            "还贡": self.human_mode and pending == "return",
        }
        self.action_buttons = {}
        commands = {"出牌": self._play_selected, "过牌": self._pass_human,
                    "进贡": lambda: self._submit_exchange("tribute"),
                    "还贡": lambda: self._submit_exchange("return")}
        for name in ("出牌", "过牌", "进贡", "还贡"):
            highlight = tk.Frame(actions, bg=self.PANEL)
            highlight.pack(side="left", padx=4, pady=(10, 0))
            button = ttk.Button(highlight, text=name, command=commands[name],
                                style="GameAction.TButton", width=7,
                                state="normal" if states[name] and not self.failed else "disabled")
            button.pack(padx=3, pady=3)
            self.action_buttons[name] = button
            self.action_highlights[name] = highlight
        hint = "点击手牌选择，再点击对应动作" if self.human_mode else "AI观察模式 · AI1由程序控制"
        tk.Label(actions, text=hint, bg=self.PANEL, fg="#b9d6ce",
                 font=("Arial", 10)).pack(side="left", padx=12)
        self._flash_action_buttons()

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
                                if active else self.PANEL)
            self.action_buttons[name].configure(
                style=("PromptOn.GameAction.TButton" if self.action_flash_on else
                       "PromptOff.GameAction.TButton") if active else "GameAction.TButton")
        if enabled:
            self.action_flash_id = self.root.after(550, self._flash_action_buttons)

    def _human_can_play(self):
        return not self.failed and self.game.human_can_play

    def _await_human(self):
        m = self.match
        if m is None:
            return False
        if not self.human_mode:
            return False
        if m.tribute_pending:
            kind = self._pending_exchange_kind()
            self._pause()
            self.status.configure(text="请选择最大可贡牌并点击进贡" if kind == "tribute" else "请选择2～10的一张牌并点击还贡")
            self._draw_table()
            return True
        if self._human_can_play():
            # 与 Match 的最后一名玩家自由领出规则一致。
            self.game.prepare_human_turn()
            self._pause()
            self.status.configure(text="轮到AI1：请选择出牌或过牌")
            self._draw_table()
            return True
        return False

    def _continue_human(self):
        self._pause()
        if self.series_finished or self.failed or self._await_human():
            return
        self.running = True
        self.status.configure(text="人机对战 · 其他玩家行动中")
        self.after_id = self.root.after(650, self.step)

    def _submit_exchange(self, kind):
        if self.failed or self._pending_exchange_kind() != kind:
            return
        if len(self.selected_cards) != 1:
            self.status.configure(text="请选择一张牌")
            return
        try:
            self.game.exchange(self._selected_indices()[0])
        except ValueError as exc:
            self.status.configure(text=str(exc))
            return
        self.selected_cards = []
        self._sync_game()
        self._continue_human()

    def _toggle_card(self, card: Card) -> None:
        m = self.match
        if m is None:
            return
        if not self.human_mode or self.failed or not (self._human_can_play() or m.tribute_pending):
            return
        for index, selected in enumerate(self.selected_cards):
            if selected is card:
                self.selected_cards.pop(index)
                self._draw_table()
                return
        self.selected_cards.append(card)
        self._draw_table()

    def _play_selected(self):
        if not self._human_can_play():
            return
        try:
            self.game.play(self._selected_indices())
        except Exception as exc:
            self.status.configure(text=f"出牌不合法：{exc}")
            return
        self.selected_cards = []
        self._sync_game()
        self._continue_human()

    def _pass_human(self):
        if not self._human_can_play():
            return
        try:
            self.game.pass_turn()
        except Exception as exc:
            self.status.configure(text=f"不能过牌：{exc}")
            return
        self.selected_cards = []
        self._sync_game()
        self._continue_human()

    def _log(self, message):
        self.log.configure(state="normal")
        tag = "team_a" if message.startswith(("AI1", "AI3")) else "team_b" if message.startswith(("AI2", "AI4")) else ""
        self.log.insert("end", message + "\n", (tag,) if tag else ())
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _pause(self):
        self.running = False
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        if hasattr(self, "auto_button"):
            self.auto_button.configure(text="看AI对战")

    def _advance_one(self):
        if not self.match or self.series_finished or self.failed:
            self._pause()
            return
        try:
            if self._await_human():
                return
            self.game.step()
            self._sync_game()
            if not self.series_finished and not self._await_human():
                self.status.configure(text=f"第{self.turns}步 · 轮到AI{self.match.current_player+1}")
        except Exception as exc:
            self._pause()
            self.failed = True
            self._log(f"错误：{exc}")
            self.status.configure(text="对局出现错误，请新建对局")
            self._draw_table()

    def step(self):
        self.after_id = None
        if not self.running:
            return
        self._advance_one()
        if self.running:
            self.after_id = self.root.after(650, self.step)

    def single_step(self):
        if self.human_mode:
            return
        if self.running:
            self._pause()
            self.status.configure(text="已暂停（再次按单步执行下一动作）")
            return
        self._advance_one()

    def toggle_auto(self):
        if self.human_mode:
            return
        if self.running:
            self._pause()
            self.status.configure(text="已暂停")
        elif not self.series_finished and not self.failed:
            self.running = True
            self.auto_button.configure(text="暂停")
            self.step()

    def close(self):
        self.closed = True
        self._stop_action_flash()
        self._pause()
        self.root.destroy()


def main():
    root = tk.Tk()
    GuandanPlay(root)
    root.mainloop()


if __name__ == "__main__":
    main()
