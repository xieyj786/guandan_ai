"""Desktop observer for the local Match and RuleAgent implementations."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from agents.rule_agent import RuleAgent
from game_engine.card import Rank, Suit, card_display, single_card_power
from game_series import LEVELS
from match_runner import Match
from turn_log import format_turn_log
from card_ui import CardFace, CardStrip


class GuandanViewer:
    BG = "#123c35"
    PANEL = "#092a25"
    GOLD = "#eed08a"
    TEAM_YELLOW = "#ffe66d"
    TEAM_BLUE = "#72c7ff"

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("掼蛋 · AI 对局观察器")
        root.geometry("1180x820")
        root.minsize(1000, 740)
        root.configure(bg=self.BG)
        self.running = False
        self.after_id: str | None = None
        self.match: Match | None = None
        self.turns = 0
        self.failed = False
        self.round_number = 0
        self.team_levels = {"A": Rank.TWO, "B": Rank.TWO}
        self.leading_team = "A"
        self.seed = tk.StringVar(value="42")
        self.level = tk.StringVar(value="2")
        self.speed = tk.StringVar(value="650")
        self.status = tk.StringVar()
        self.center = tk.StringVar(value="等待领出")
        self._build_ui()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.new_game()

    def _build_ui(self):
        toolbar = tk.Frame(self.root, bg=self.PANEL, padx=14, pady=12)
        toolbar.pack(fill="x")
        tk.Label(toolbar, text="掼蛋 · AI 观察器", bg=self.PANEL, fg=self.GOLD,
                 font=("Microsoft YaHei UI", 16, "bold")).pack(side="left", padx=(0, 18))
        for label, variable, values in (
            ("起始级牌", self.level, [str(i) for i in range(2, 11)] + ["J", "Q", "K", "A"]),
            ("间隔(ms)", self.speed, ["100", "300", "650", "1000", "1500"]),
        ):
            tk.Label(toolbar, text=label, bg=self.PANEL, fg="white").pack(side="left", padx=4)
            ttk.Combobox(toolbar, textvariable=variable, values=values, state="readonly", width=5).pack(side="left")
        tk.Label(toolbar, text="种子", bg=self.PANEL, fg="white").pack(side="left", padx=4)
        ttk.Entry(toolbar, textvariable=self.seed, width=7).pack(side="left")
        ttk.Button(toolbar, text="新局", command=self.new_game).pack(side="left", padx=5)
        ttk.Button(toolbar, text="单步", command=self.single_step).pack(side="left", padx=5)
        self.auto_button = ttk.Button(toolbar, text="自动播放", command=self.toggle_auto)
        self.auto_button.pack(side="left", padx=5)
        tk.Label(self.root, textvariable=self.status, bg=self.BG, fg=self.GOLD,
                 anchor="w", font=("Microsoft YaHei UI", 11)).pack(fill="x", padx=18, pady=8)
        level_bar = tk.Frame(self.root, bg=self.BG)
        level_bar.pack(fill="x", padx=18, pady=(0, 8))
        self.level_a_status = tk.Label(level_bar, bg=self.BG, fg=self.TEAM_YELLOW, anchor="w", font=("Microsoft YaHei UI", 10, "bold"))
        self.level_a_status.pack(side="left", padx=(0, 24))
        self.level_b_status = tk.Label(level_bar, bg=self.BG, fg=self.TEAM_BLUE, anchor="w", font=("Microsoft YaHei UI", 10, "bold"))
        self.level_b_status.pack(side="left")
        body = tk.Frame(self.root, bg=self.BG)
        body.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        table = tk.Frame(body, bg=self.BG)
        table.pack(side="left", fill="both", expand=True)
        table.columnconfigure(0, weight=1)
        self.panels: dict[int, tuple[tk.Frame, tk.Label, tk.Frame]] = {}
        # Show all four hands in seat order; partners are 1&3 and 2&4.
        for i in range(4):
            panel = tk.Frame(table, bg=self.PANEL, padx=10, pady=6,
                             highlightthickness=2, highlightbackground=self.PANEL)
            panel.grid(row=i, column=0, sticky="nsew", pady=3)
            table.rowconfigure(i, weight=1)
            title = tk.Label(panel, bg=self.PANEL, fg="white", anchor="w",
                             font=("Microsoft YaHei UI", 11, "bold"))
            title.pack(fill="x")
            cards = tk.Frame(panel, bg=self.PANEL)
            cards.pack(anchor="w", pady=4)
            self.panels[i] = (panel, title, cards)
        sidebar = tk.Frame(body, bg=self.PANEL, width=290, padx=10, pady=10)
        sidebar.pack(side="right", fill="y", padx=(12, 0))
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="当前出牌", bg=self.PANEL, fg=self.GOLD,
                 font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        tk.Label(sidebar, textvariable=self.center, bg=self.PANEL, fg="white", justify="left",
                 wraplength=260, font=("Microsoft YaHei UI", 11)).pack(fill="x", pady=10)
        self.play_faces = CardStrip(sidebar, background=self.PANEL, height=94)
        self.play_faces.pack(fill="x", pady=(0, 10))
        tk.Label(sidebar, text="出牌记录", bg=self.PANEL, fg=self.GOLD).pack(anchor="w")
        log_frame = tk.Frame(sidebar)
        log_frame.pack(fill="both", expand=True, pady=(6, 0))
        scroll = ttk.Scrollbar(log_frame)
        scroll.pack(side="right", fill="y")
        self.log = tk.Text(log_frame, width=25, state="disabled", wrap="word", bg="#061d19",
                           fg="#e1eee9", relief="flat", yscrollcommand=scroll.set)
        self.log.pack(fill="both", expand=True)
        scroll.configure(command=self.log.yview)

    def _pause(self):
        self.running = False
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.auto_button.configure(text="自动播放")

    def new_game(self):
        self._pause()
        try:
            seed = int(self.seed.get())
        except ValueError:
            self.status.set("种子请输入整数，再点击新局。")
            return
        faces = {"J": 11, "Q": 12, "K": 13, "A": 14}
        level = Rank(faces[self.level.get()] if self.level.get() in faces else int(self.level.get()))
        self.round_number = 0
        self.team_levels = {"A": level, "B": level}
        self.leading_team = "A"
        self.turns = 0
        self.failed = False
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._log(f"新局：种子 {seed}，级牌 {self.level.get()}。每人 27 张。\nA队：AI1 / AI3；B队：AI2 / AI4。")
        self._start_round(seed)
        self._draw_table()

    def _start_round(self, seed, previous_result=None):
        self.round_number += 1
        self.turns = 0
        self.match = Match([RuleAgent(f"AI{i+1}") for i in range(4)], level_rank=self.team_levels[self.leading_team], seed=seed + self.round_number - 1, verbose=False, use_wildcards=True, team_levels=dict(self.team_levels), previous_result=previous_result)
        self._log(f"第 {self.round_number} 局发牌：每人 27 张")
        # viewer 自行记录逐手出牌，只在准备阶段接收进贡事件，避免重复日志。
        self.match.event_callback = self._log
        self.match.prepare()
        self.match.event_callback = None

    def _log(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _draw_table(self):
        m = self.match
        if m is None:
            return
        team_levels = m.team_levels
        if team_levels is None:
            raise RuntimeError("对局尚未初始化队伍级牌")
        for i, (panel, title, area) in self.panels.items():
            active = len(m.finish_order) < 4 and i == m.current_player
            team = "A" if i % 2 == 0 else "B"
            team_color = self.TEAM_YELLOW if team == self.leading_team else self.TEAM_BLUE
            panel.configure(highlightbackground=team_color if active else self.PANEL)
            rank = f" · 第{m.finish_order.index(i)+1}名" if i in m.finish_order else ""
            title.configure(text=f"{'▶ ' if active else ''}AI{i+1} · {team}队 · 剩余 {len(m.hands[i])} 张{rank}", fg=team_color)
            for widget in area.winfo_children():
                widget.destroy()
            for j, card in enumerate(sorted(m.hands[i], key=lambda c: single_card_power(c, m.level_rank))):
                CardFace(area, card.suit.value, int(card.rank), width=28, height=54,
                         background=self.PANEL,
                         wildcard=card.suit == Suit.HEART and card.rank == m.level_rank).grid(
                             row=j//14, column=j%14, padx=1, pady=1)
        if m.last_play is not None and m.last_player is not None:
            self.center.set(f"AI{m.last_player+1} · {m.last_play.category.name}")
            self.play_faces.set_cards([(c.suit.value, int(c.rank)) for c in m.last_play.cards], int(m.level_rank))
        else:
            self.center.set("等待领出")
            self.play_faces.set_cards([])
        if len(m.finish_order) == 4:
            result = m._build_round_result()
            order = " → ".join(p.player_id for p in result.finish_order)
            self.status.set(f"第 {self.round_number} 局结束 · {result.winning_team}队获胜，升 {result.upgrade_level} 级 · {order}")
        else:
            self.status.set(f"第 {self.turns} 步 · 轮到 AI{m.current_player+1} · {'自动播放中' if self.running else '已暂停'}")
        self.level_a_status.configure(text=f"本局级牌：{m.level_rank.name}（全桌）　 A队进度：{self.team_levels['A'].name}")
        self.level_b_status.configure(text=f"B队进度：{self.team_levels['B'].name}")

    def _advance_one(self):
        m = self.match
        if m is None or len(m.finish_order) == 4 or self.failed:
            self._pause()
            return
        idx = m.current_player
        before = len(m.hands[idx])
        try:
            if self.turns >= 3000:
                raise RuntimeError("超过 3000 步，请新建对局")
            m._take_turn()
            self.turns += 1
            for message in format_turn_log(m, idx, before, self.turns):
                self._log(message)
            was_running = self.running
            if len(m.finish_order) == 4:
                self._pause()
            self._draw_table()
            if len(m.finish_order) == 4:
                result = m._build_round_result()
                winner = result.winning_team
                old = self.team_levels[winner]
                self.leading_team = winner
                if old == Rank.ACE and result.upgrade_level == 3:
                    self._log(f"{winner}队A级双下，比赛结束。")
                else:
                    if old != Rank.ACE:
                        self.team_levels[winner] = LEVELS[min(LEVELS.index(old) + result.upgrade_level, len(LEVELS) - 1)]
                    self._log(f"下一局全桌打 {self.team_levels[winner].name}；升级进度：A队{self.team_levels['A'].name}级，B队{self.team_levels['B'].name}级。")
                    self._start_round(int(self.seed.get()), previous_result=result)
                    if was_running:
                        self.running = True
                        self.auto_button.configure(text="暂停")
                    self._draw_table()
        except Exception as exc:
            self._pause()
            self.failed = True
            self._log(f"错误：{type(exc).__name__}: {exc}")
            self.status.set("对局已停止，请查看记录并新建对局。")

    def single_step(self):
        if self.running:
            self._pause()
            self._draw_table()
            return
        self._advance_one()

    def toggle_auto(self):
        if self.running:
            self._pause()
            self._draw_table()
        elif self.match and len(self.match.finish_order) < 4 and not self.failed:
            self.running = True
            self.auto_button.configure(text="暂停")
            self.step()

    def step(self):
        self.after_id = None
        if not self.running:
            return
        self._advance_one()
        if self.running:
            self.after_id = self.root.after(int(self.speed.get()), self.step)

    def close(self):
        self._pause()
        self.root.destroy()


def main():
    root = tk.Tk()
    GuandanViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
