"""掼蛋桌面 GUI：观察、人机对战和可选 LLM；窗口布局与状态显示。"""
from __future__ import annotations

from dataclasses import replace
import time
import sys
import tkinter as tk
from tkinter import ttk

from strategy.rule_agent import RuleAgent
from gameplay.contracts import Agent
from integrations.llm.deepseek_agent import DeepSeekAgent
from integrations.llm.settings import LLMSettings, configured_client, background
from presentation.llm_dialog import LLMDialog
from integrations.llm.activity import LLMActivity, activity_text
from evaluation.runtime import IdleSleepGuard
from game_engine.round_result import RoundResult
from game_engine.card import Card, Rank, Suit, card_display, single_card_power
from gameplay.turn_log import format_turn_log
from presentation.table_view import GameTableView
from presentation.hand_tabs import HandTabsMixin
from gameplay.match import Match
from gameplay.progression import advance_levels

class GuandanGUI(HandTabsMixin, GameTableView):
    BG = "#123c35"
    PANEL = "#0d2d29"
    GOLD = "#e9c46a"
    TEAM_YELLOW = "#ffe66d"
    TEAM_BLUE = "#72c7ff"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("掼蛋 · 对局观察器")
        self.root.geometry("1200x850")
        self.root.minsize(1000, 680)
        self.root.configure(bg=self.BG)
        self.llm_settings = LLMSettings.load()
        self.llm_enabled = tk.BooleanVar(value=False)
        self.active_llm_settings = replace(self.llm_settings, enabled=self.llm_enabled.get())
        self.llm_dialog = None
        self.pending_job = None
        self.network_future = None
        self.llm_poll_id = None
        self.llm_activity = LLMActivity()
        self.llm_window_started = time.time()
        self.prevent_idle_sleep = tk.BooleanVar(value=sys.platform == 'darwin')
        self.sleep_guard = IdleSleepGuard()
        self.llm_stats_poll_id = None
        self.llm_request_started = None
        self.generation = 0
        self.closed = False
        self.running = False
        self.after_id: str | None = None
        self.action_flash_id: str | None = None
        self.action_flash_on = False
        self.action_highlights = {}
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
        self.llm_stats_label = tk.Label(self.root, bg=self.BG, fg=self.GOLD, justify='left', anchor='w', wraplength=1160, font=('Microsoft YaHei UI',10))
        self.llm_stats_label.pack(fill='x', padx=12, pady=3, before=self.root.winfo_children()[1])
        self.llm_stats_label.bind("<Configure>", self._resize_play_label)
        self._refresh_llm_activity()
        self.new_game()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _extra_control_buttons(self):
        return (("LLM设置", self.open_llm_settings),)

    def _build_extra_controls(self, controls):
        self.llm_switch = ttk.Checkbutton(controls, text="接入 LLM", variable=self.llm_enabled, command=self._toggle_llm)
        self.llm_switch.pack(side="left", padx=12)
        if sys.platform == 'darwin':
            ttk.Checkbutton(controls, text='LLM运行时防止空闲睡眠', variable=self.prevent_idle_sleep).pack(side='left', padx=5)

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
        self.pending_round_result = None
        self.hand_tab = 0
        self.failed = False
        for name in ("单步", "看AI对战"):
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
            agents[config.seat] = DeepSeekAgent(f"AI{config.seat + 1}", configured_client(config))
            self._log(f"AI{config.seat + 1} 使用 {config.provider}（{config.model}）；其他电脑玩家使用规则 AI")
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

    def _human_can_play(self):
        return (self.human_mode and self.match is not None and not self.failed
                and not self.series_finished and not self.match.tribute_pending
                and self.match.current_player == self.human_index
                and not self.match.is_finished(self.human_index))

    def _await_human(self):
        if self.pending_round_result is not None:
            return False
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
            m.prepare_turn()
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
        if self.pending_round_result is None:
            self.status.configure(text="人机对战 · 其他玩家行动中")
        self.after_id = self.root.after(3000 if self.pending_round_result is not None else 900, self.step)

    def _hint_human(self):
        if not self._human_can_play():
            return
        m = self.match
        m.prepare_turn()
        action = RuleAgent("出牌提示").decide(m.observation(self.human_index))
        self.selected_cards = list(action.cards) if action.action_type == "play" else []
        self._draw_table()
        if action.action_type == "pass":
            self.status.configure(text="提示：建议过牌，请点击过牌")
        else:
            cards = " ".join(card_display(card) for card in self.selected_cards)
            self.status.configure(text=f"提示：建议出 {cards}；已选中，请点击出牌确认")

    def _submit_pending_exchange(self):
        kind = self._pending_exchange_kind()
        if kind in ("tribute", "return"):
            self._submit_exchange(kind)

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
            m.play_cards(self.human_index, list(self.selected_cards))
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
            m.pass_turn(self.human_index)
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
                self.match.agents[config.seat] = DeepSeekAgent(f"AI{config.seat+1}", configured_client(config))
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
            self.auto_button.configure(text="看AI对战")

    def _advance_one(self):
        if not self.match or self.series_finished or self.failed:
            self._pause()
            return
        try:
            if self.pending_round_result is not None:
                result, self.pending_round_result = self.pending_round_result, None
                self._start_round(previous_result=result)
                self._await_human()
                return
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
                self.match.prepare_turn()
                observation = self.match.observation(index)
                self.network_future = background(lambda: self._decide_llm(agent, observation))
                self.llm_request_started = time.monotonic()
                self.pending_job = (self.network_future, self.match, index,
                                    len(self.match.hands[index]), self.generation, agent)
                self.status.configure(text=f"AI{index+1} · {getattr(agent.client, 'provider_name', 'DeepSeek')} 正在思考…")
                self.llm_poll_id = self.root.after(80, self._poll_llm)
                return
            before = len(self.match.hands[index])
            self.match.take_turn()
            self._record_turn(index, before)
            self._finish_round_if_needed()
            self._draw_table()
            if not self.series_finished and self.pending_round_result is None and not self._await_human():
                self.status.configure(text=f"第{self.turns}步 · 轮到AI{self.match.current_player+1}")
        except Exception as exc:
            self._pause()
            self.failed = True
            self._log(f"错误：{exc}")
            self.status.configure(text="对局出现错误，请新建对局")
            self._draw_table()

    def _decide_llm(self, agent, observation):
        client = agent.client
        client.last_request_metrics = None
        kind = 'fallback'
        try:
            action = agent.decide(observation)
            kind = agent.last_decision_kind
            return action
        finally:
            self.llm_activity.record(kind, getattr(client, 'last_request_metrics', None))

    def _refresh_llm_activity(self):
        self.llm_stats_poll_id = None
        if self.closed:
            return
        elapsed = max(0, int(time.time() - self.llm_window_started))
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.llm_stats_label.configure(text=f'窗口时长{hours:02d}:{minutes:02d}:{seconds:02d} · ' + activity_text(self.llm_activity.summary()))
        pending = self.network_future is not None and not self.network_future.done()
        watching = self.running and self.match is not None and any(isinstance(a, DeepSeekAgent) for a in self.match.agents)
        if self.prevent_idle_sleep.get() and (pending or watching):
            if self.sleep_guard.process is None:
                try:
                    self.sleep_guard.start()
                except OSError:
                    self.prevent_idle_sleep.set(False)
                    self._log('无法启用防空闲睡眠；对局继续运行。')
        else:
            self.sleep_guard.stop()
        self.llm_stats_poll_id = self.root.after(200, self._refresh_llm_activity)

    def _poll_llm(self):
        self.llm_poll_id = None
        job = self.pending_job
        if self.closed or job is None:
            return
        future, match, index, before, generation, agent = job
        if not future.done():
            elapsed = time.monotonic() - self.llm_request_started if self.llm_request_started is not None else 0
            self.status.configure(text=f"AI{index+1} · {getattr(agent.client, 'provider_name', 'DeepSeek')} 正在决策，已等待{elapsed:.1f}秒")
            self.llm_poll_id = self.root.after(80, self._poll_llm)
            return
        self.pending_job = None
        if generation != self.generation or match is not self.match or index != match.current_player:
            return
        try:
            try:
                action = future.result()
            except Exception:
                action = RuleAgent(agent.name).decide(match.observation(index))
                agent.report = f"{agent.name}〔规则接管〕：模型请求未能完成"
            self._log(agent.report)
            match.apply_action(index, action)
            self._record_turn(index, before)
            self._finish_round_if_needed()
            self._draw_table()
            if not self.series_finished and self.pending_round_result is None and not self._await_human():
                self.status.configure(text=f"第{self.turns}步 · 轮到AI{match.current_player+1}")
            if self.running:
                self.after_id = self.root.after(3000 if self.pending_round_result is not None else 900, self.step)
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
            self.after_id = self.root.after(3000 if self.pending_round_result is not None else 900, self.step)

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
        if self.llm_stats_poll_id is not None:
            self.root.after_cancel(self.llm_stats_poll_id)
            self.llm_stats_poll_id = None
        self.sleep_guard.stop()
        self._stop_action_flash()
        if self.llm_dialog is not None and not self.llm_dialog.closed:
            self.llm_dialog.close()
        self._pause()
        self.root.destroy()

    def _finish_round_if_needed(self):
        if not self.match or len(self.match.finish_order) != 4:
            return
        result = self.match.round_result()
        winner = result.winning_team
        progress = advance_levels(self.team_levels, winner, result.upgrade_level)
        self.leading_team = progress.leading_team
        self.team_levels = progress.team_levels
        if progress.finished:
            self._log(f"{winner}队双升赢得本局比赛。")
            self.series_finished = True
            self._pause()
            self.status.configure(text=f"{winner}队双升赢得本局比赛")
            self._draw_table()
            return
        self._log(f"下一局全桌打 {self.team_levels[winner].name}；升级进度：A队{self.team_levels['A'].name}级，B队{self.team_levels['B'].name}级。")
        self.selected_cards = []
        self.pending_round_result = result
        self.status.configure(text=f"本局结束 · {winner}队获胜，升{result.upgrade_level}级；下一局打{self.team_levels[winner].name}")

def main():
    root = tk.Tk()
    GuandanGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
