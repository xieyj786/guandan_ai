"""掼蛋桌面 GUI：观察、人机对战和可选 LLM；窗口布局与状态显示。"""
from __future__ import annotations

from dataclasses import replace
import tkinter as tk
from tkinter import ttk, font as tkfont

from agents.rule_agent import RuleAgent
from agents.base import Agent
from agents.deepseek_agent import DeepSeekAgent
from llm_settings import LLMSettings, StoredDeepSeekClient, background
from llm_dialog import LLMDialog
from game_engine.round_result import RoundResult
from game_engine.card import Card, Rank, Suit, card_display, single_card_power
from turn_log import format_turn_log
from card_ui import CardFace
from play_display import PlayStrip
from match_runner import Match
from game_series import LEVELS


class GuandanGUI:
    BG = "#123c35"
    PANEL = "#0d2d29"
    GOLD = "#e9c46a"
    TEAM_YELLOW = "#ffe66d"
    TEAM_BLUE = "#72c7ff"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("掼蛋 · 对局观察器")
        self.root.geometry("1200x780")
        self.root.minsize(1000, 680)
        self.root.configure(bg=self.BG)
        self.llm_settings = LLMSettings.load()
        self.llm_enabled = tk.BooleanVar(value=False)
        self.active_llm_settings = replace(self.llm_settings, enabled=self.llm_enabled.get())
        self.llm_dialog = None
        self.pending_job = None
        self.network_future = None
        self.llm_poll_id = None
        self.generation = 0
        self.closed = False
        self.running = False
        self.after_id: str | None = None
        self.human_mode = False
        self.failed = False
        self.seed = 42
        self.match: Match | None = None
        self.round_number = 0
        self.series_finished = False
        self.team_levels = {"A": Rank.TWO, "B": Rank.TWO}
        self.leading_team = "A"
        self.human_index = 0
        self.selected_cards: list[Card] = []
        self._build_ui()
        self.new_game()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

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
                              ("自动播放", self.toggle_auto), ("人机对战", self.start_human_game),
                              ("LLM设置", self.open_llm_settings)):
            button = ttk.Button(controls, text=text, command=command, width=8)
            button.pack(side="left", padx=2)
            self.control_buttons[text] = button
        self.llm_switch = ttk.Checkbutton(controls, text="接入 LLM", variable=self.llm_enabled, command=self._toggle_llm)
        self.llm_switch.pack(side="left", padx=12)
        self.auto_button = self.control_buttons["自动播放"]
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

    def _resize_play_label(self, event: tk.Event) -> None:
        widget = event.widget
        if isinstance(widget, tk.Label):
            widget.configure(wraplength=max(60, event.width - 10))

    def _pending_exchange_kind(self) -> str | None:
        m = self.match
        if m is None or m.tribute_session is None:
            return None
        pending = m.tribute_session.pending
        return pending[0] if pending is not None else None

    def new_game(self, human_mode=False):
        self._pause()
        self.active_llm_settings = replace(self.llm_settings, enabled=self.llm_enabled.get())
        self.human_mode = human_mode
        self.failed = False
        for name in ("单步", "自动播放"):
            self.control_buttons[name].configure(state="disabled" if human_mode else "normal")
        self.seed += 1
        self.round_number = 0
        self.series_finished = False
        self.team_levels = {"A": Rank.TWO, "B": Rank.TWO}
        self.leading_team = "A"
        self._clear_log()
        self.selected_cards = []
        self._start_round()
        self.status.configure(text="AI观察 · 已暂停" if not human_mode else "人机对战")
        if human_mode:
            self._continue_human()

    def start_human_game(self):
        self.new_game(human_mode=True)

    def _start_round(self, previous_result: RoundResult | None = None) -> None:
        self.round_number += 1
        self.turns = 0
        self.player_plays = ["等待出牌"] * 4
        self.player_cards: list[list[Card]] = [[] for _ in range(4)]
        agents: list[Agent] = [RuleAgent(f"AI{i + 1}") for i in range(4)]
        config = self.active_llm_settings
        if config.enabled and not (self.human_mode and config.seat == self.human_index):
            agents[config.seat] = DeepSeekAgent(f"AI{config.seat + 1}", StoredDeepSeekClient(config.model))
            self._log(f"AI{config.seat + 1} 使用 DeepSeek（{config.model}）；其他电脑玩家使用规则 AI")
        elif config.enabled and self.human_mode:
            self._log("AI1由你控制；本局其他玩家使用规则 AI。可在LLM设置中改选AI2～AI4。")
        level_rank = self.team_levels[self.leading_team]
        self.match = Match(agents=agents, level_rank=level_rank, verbose=False, seed=self.seed + self.round_number - 1, event_callback=self._on_event, use_wildcards=True, team_levels=dict(self.team_levels), previous_result=previous_result)
        self._log(f"第 {self.round_number} 局发牌：每人 27 张")
        self.match.prepare(interactive_player="AI1" if self.human_mode else None)
        self.match.event_callback = None
        self.level_a.configure(text=f"本局打 {self.match.level_rank.name}（全桌）　 A队进度：{self.team_levels['A'].name}", fg=self._team_color("A"))
        self.level_b.configure(text=f"B队进度：{self.team_levels['B'].name}", fg=self._team_color("B"))
        self._draw_table()

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
            active = index == m.current_player and not m._is_finished(index)
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
        m = self.match
        if m is None:
            return
        frame = self.seats[0]
        self.hand_row = tk.Frame(frame, bg=self.PANEL, height=82)
        self.hand_row.pack(fill="x", padx=2, pady=5)
        self.hand_row.grid_propagate(False)
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
            button = ttk.Button(actions, text=name, command=commands[name],
                                style="GameAction.TButton", width=7,
                                state="normal" if states[name] and not self.failed else "disabled")
            button.pack(side="left", padx=4, pady=(10, 0))
            self.action_buttons[name] = button
        hint = "点击手牌选择，再点击对应动作" if self.human_mode else "AI观察模式 · AI1由程序控制"
        tk.Label(actions, text=hint, bg=self.PANEL, fg="#b9d6ce",
                 font=("Arial", 10)).pack(side="left", padx=12)

    def _human_can_play(self):
        return (self.human_mode and self.match is not None and not self.failed
                and not self.series_finished and not self.match.tribute_pending
                and self.match.current_player == self.human_index
                and not self.match._is_finished(self.human_index))

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
            if len(m._active_players()) == 1:
                m.last_play = None
                m.pass_streak = 0
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
        m = self.match
        if m is None:
            return
        if not self.human_mode or not m.tribute_pending or self.failed:
            return
        if self._pending_exchange_kind() != kind:
            return
        if len(self.selected_cards) != 1:
            self.status.configure(text="请选择一张牌")
            return
        try:
            m.event_callback = self._on_event
            m.submit_tribute(self.selected_cards[0])
        except ValueError as exc:
            self.status.configure(text=str(exc))
            return
        finally:
            m.event_callback = None
        self.selected_cards = []
        self._draw_table()
        self._continue_human()

    def _record_turn(self, index, before):
        m = self.match
        if m is None:
            return
        self.turns += 1
        played = len(m.hands[index]) < before
        if played:
            last_play = m.last_play
            if last_play is None:
                raise RuntimeError("出牌后缺少出牌记录")
            self.player_cards[index] = list(last_play.cards)
            self.player_plays[index] = " ".join(card_display(c) for c in last_play.cards)
        else:
            self.player_cards[index] = []
            self.player_plays[index] = "过牌"
        for message in format_turn_log(m, index, before, self.turns):
            self._log(message)

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
        m = self.match
        if m is None:
            return
        if not self._human_can_play():
            return
        if not self.selected_cards:
            self.status.configure(text="请先选择要出的牌")
            return
        try:
            before = len(m.hands[self.human_index])
            m._handle_play(self.human_index, list(self.selected_cards))
            self._record_turn(self.human_index, before)
            self.selected_cards = []
            self._draw_table()
            self._finish_round_if_needed()
            self._continue_human()
        except Exception as exc:
            self.status.configure(text=f"出牌不合法：{exc}")

    def _pass_human(self):
        m = self.match
        if m is None:
            return
        if not self._human_can_play():
            return
        try:
            before = len(m.hands[self.human_index])
            m._handle_pass(self.human_index)
            self._record_turn(self.human_index, before)
            self.selected_cards = []
            self._draw_table()
            self._continue_human()
        except Exception as exc:
            self.status.configure(text=f"不能过牌：{exc}")

    def _on_event(self, message):
        self._log(message)

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

    def open_llm_settings(self):
        self._pause()
        if self.llm_dialog is not None and not self.llm_dialog.closed:
            self.llm_dialog.window.lift()
            return
        self.llm_dialog = LLMDialog(self.root, self.llm_settings, self._save_llm_settings,
                                    on_close=self._settings_closed)

    def _settings_closed(self):
        if not self.closed and self.human_mode:
            self._continue_human()

    def _toggle_llm(self):
        was_running = self.running
        self._pause()  # 丢弃尚未返回的模型动作，保留当前牌局。
        config = replace(self.llm_settings, enabled=self.llm_enabled.get())
        self.active_llm_settings = config
        if self.match:
            self.match.agents = [RuleAgent(f"AI{i+1}") for i in range(4)]
            if config.enabled and not (self.human_mode and config.seat == self.human_index):
                self.match.agents[config.seat] = DeepSeekAgent(f"AI{config.seat+1}", StoredDeepSeekClient(config.model))
        message = (f"LLM已开启：AI{config.seat+1}，从下一动作生效" if config.enabled
                   else "LLM已关闭：电脑玩家使用规则 AI")
        if config.enabled and self.human_mode and config.seat == self.human_index:
            message = "AI1由你操作；请在LLM设置中选择AI2～AI4"
        self._log(message)
        self.status.configure(text=message)
        if self.human_mode:
            self._continue_human()
        elif was_running:
            self.toggle_auto()

    def _save_llm_settings(self, settings):
        self.llm_settings = settings
        self._toggle_llm()
        self.status.configure(text="设置已保存；主界面“接入 LLM”开关控制是否调用")

    def _pause(self):
        self.generation += 1
        self.pending_job = None
        if self.llm_poll_id is not None:
            self.root.after_cancel(self.llm_poll_id)
            self.llm_poll_id = None
        self.running = False
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        if hasattr(self, "auto_button"):
            self.auto_button.configure(text="自动播放")

    def _advance_one(self):
        if not self.match or self.series_finished or self.failed:
            self._pause()
            return
        try:
            if self._await_human():
                return
            if self.turns >= 3000:
                raise RuntimeError("超过3000步，请新建对局")
            if self.pending_job is not None:
                return
            index = self.match.current_player
            agent = self.match.agents[index]
            if isinstance(agent, DeepSeekAgent):
                if self.network_future is not None and not self.network_future.done():
                    self.status.configure(text="上一请求正在结束，请稍后继续")
                    return
                if len(self.match._active_players()) == 1:
                    self.match.last_play = None
                    self.match.pass_streak = 0
                observation = self.match._build_observation(index)
                self.network_future = background(lambda: agent.decide(observation))
                self.pending_job = (self.network_future, self.match, index,
                                    len(self.match.hands[index]), self.generation, agent)
                self.status.configure(text=f"AI{index+1} · DeepSeek 正在思考…")
                self.llm_poll_id = self.root.after(80, self._poll_llm)
                return
            before = len(self.match.hands[index])
            self.match._take_turn()
            self._record_turn(index, before)
            self._finish_round_if_needed()
            self._draw_table()
            if not self.series_finished and not self._await_human():
                self.status.configure(text=f"第{self.turns}步 · 轮到AI{self.match.current_player+1}")
        except Exception as exc:
            self._pause()
            self.failed = True
            self._log(f"错误：{exc}")
            self.status.configure(text="对局出现错误，请新建对局")
            self._draw_table()

    def _poll_llm(self):
        self.llm_poll_id = None
        job = self.pending_job
        if self.closed or job is None:
            return
        future, match, index, before, generation, agent = job
        if not future.done():
            self.llm_poll_id = self.root.after(80, self._poll_llm)
            return
        self.pending_job = None
        if generation != self.generation or match is not self.match or index != match.current_player:
            return
        try:
            try:
                action = future.result()
            except Exception:
                action = RuleAgent(agent.name).decide(match._build_observation(index))
                agent.report = f"{agent.name}〔规则接管〕：模型请求未能完成"
            self._log(agent.report)
            if action.action_type == 'pass':
                match._handle_pass(index)
            else:
                match._handle_play(index, action.cards)
            self._record_turn(index, before)
            self._finish_round_if_needed()
            self._draw_table()
            if not self.series_finished and not self._await_human():
                self.status.configure(text=f"第{self.turns}步 · 轮到AI{match.current_player+1}")
            if self.running:
                self.after_id = self.root.after(650, self.step)
        except Exception:
            self._pause()
            self.failed = True
            self._log("错误：模型动作执行失败，请新建对局")
            self.status.configure(text="对局出现错误，请新建对局")

    def step(self):
        self.after_id = None
        if not self.running:
            return
        self._advance_one()
        if self.running and self.pending_job is None:
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
        if self.llm_dialog is not None and not self.llm_dialog.closed:
            self.llm_dialog.close()
        self._pause()
        self.root.destroy()

    def _next_team_level(self, team, upgrade):
        current = self.team_levels[team]
        if current == Rank.ACE:
            return Rank.ACE
        return LEVELS[min(LEVELS.index(current) + upgrade, len(LEVELS) - 1)]

    def _finish_round_if_needed(self):
        if not self.match or len(self.match.finish_order) != 4:
            return
        result = self.match._build_round_result()
        winner = result.winning_team
        old_level = self.team_levels[winner]
        self.leading_team = winner
        if old_level == Rank.ACE and result.upgrade_level == 3:
            self._log(f"{winner}队A级双下，比赛结束。")
            self.series_finished = True
            self._pause()
            self.status.configure(text="A级双下，比赛结束")
            self._draw_table()
            return
        self.team_levels[winner] = self._next_team_level(winner, result.upgrade_level)
        self._log(f"下一局全桌打 {self.team_levels[winner].name}；升级进度：A队{self.team_levels['A'].name}级，B队{self.team_levels['B'].name}级。")
        self.selected_cards = []
        self._start_round(previous_result=result)


def main():
    root = tk.Tk()
    GuandanGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
