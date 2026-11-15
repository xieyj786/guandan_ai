"""掼蛋离线桌面入口；对局逻辑位于可供移动界面复用的 play_game.py。"""
from __future__ import annotations

import tkinter as tk

from gameplay.offline import PlayGame
from game_engine.card import Card, card_display
from strategy.rule_agent import RuleAgent
from presentation.table_view import GameTableView

class GuandanPlay(GameTableView):
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
            self.status.configure(text=f"{self.leading_team}队双升赢得本局比赛")
        self._draw_table()

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

    def _hint_human(self):
        if not self._human_can_play():
            return
        m = self.match
        self.game.prepare_human_turn()
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
