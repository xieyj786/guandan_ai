"""Offline game controller shared by desktop and future mobile interfaces.

Only this layer calls Match's internal turn methods. UI adapters use hand indices
for actions and JSON-compatible snapshots; no Tk, credentials or network required.
"""
from __future__ import annotations

from strategy.rule_agent import RuleAgent
from game_engine.card import Card, Rank
from game_engine.round_result import RoundResult
from gameplay.progression import advance_levels
from gameplay.match import Match
from gameplay.turn_log import format_turn_log


class PlayGame:
    def __init__(self, agent_factory=RuleAgent):
        self.agent_factory = agent_factory
        self.seed = 42
        self.human_index = 0
        self.human_mode = False
        self.match: Match | None = None
        self.round_number = 0
        self.turns = 0
        self.series_finished = False
        self.team_levels = {"A": Rank.TWO, "B": Rank.TWO}
        self.leading_team = "A"
        self.player_cards: list[list[Card]] = [[] for _ in range(4)]
        self.player_plays = ["等待出牌"] * 4
        self.events: list[str] = []

    def new_game(self, human_mode=False, seed: int | None = None):
        self.seed = self.seed + 1 if seed is None else seed
        self.human_mode = human_mode
        self.round_number = 0
        self.series_finished = False
        self.team_levels = {"A": Rank.TWO, "B": Rank.TWO}
        self.leading_team = "A"
        self.events.clear()
        self._start_round()

    def _start_round(self, previous_result: RoundResult | None = None):
        self.round_number += 1
        self.turns = 0
        self.player_cards = [[] for _ in range(4)]
        self.player_plays = ["等待出牌"] * 4
        self.match = Match(
            agents=[self.agent_factory(f"AI{i+1}") for i in range(4)],
            level_rank=self.team_levels[self.leading_team],
            seed=self.seed + self.round_number - 1, verbose=False,
            event_callback=self.events.append, use_wildcards=True,
            team_levels=dict(self.team_levels), previous_result=previous_result,
        )
        self.events.append(f"第 {self.round_number} 局发牌：每人 27 张")
        try:
            self.match.prepare(interactive_player="AI1" if self.human_mode else None)
        finally:
            self.match.event_callback = None

    @property
    def pending_exchange_kind(self) -> str | None:
        m = self.match
        if m is None or m.tribute_session is None:
            return None
        pending = m.tribute_session.pending
        return pending[0] if pending else None

    @property
    def human_can_play(self) -> bool:
        m = self.match
        return bool(self.human_mode and m and not self.series_finished
                    and not m.tribute_pending and m.current_player == self.human_index
                    and not m.is_finished(self.human_index))

    def prepare_human_turn(self):
        """The final remaining player leads freely, as in Match._take_turn."""
        m = self.match
        if self.human_can_play and m:
            m.prepare_turn()

    def _require_human_turn(self) -> Match:
        if not self.human_can_play or self.match is None:
            raise ValueError("当前不能由你出牌")
        self.prepare_human_turn()
        return self.match

    def _cards_at(self, indices: list[int]) -> list[Card]:
        if self.match is None:
            raise ValueError("请先开始新局")
        hand = self.match.hands[self.human_index]
        if (any(type(i) is not int or not 0 <= i < len(hand) for i in indices)
                or len(set(indices)) != len(indices)):
            raise ValueError("所选手牌编号无效或重复")
        return [hand[i] for i in indices]

    def step(self) -> bool:
        m = self.match
        if m is None or self.series_finished or m.tribute_pending or self.human_can_play:
            self.prepare_human_turn()
            return False
        if self.turns >= 3000:
            raise RuntimeError("超过3000步，请新建对局")
        index = m.current_player
        before = len(m.hands[index])
        m.take_turn()
        self._record_turn(index, before)
        self._finish_round()
        self.prepare_human_turn()
        return True

    def play(self, indices: list[int]):
        m = self._require_human_turn()
        cards = self._cards_at(indices)
        if not cards:
            raise ValueError("请先选择要出的牌")
        before = len(m.hands[self.human_index])
        m.play_cards(self.human_index, cards)
        self._record_turn(self.human_index, before)
        self._finish_round()
        self.prepare_human_turn()

    def pass_turn(self):
        m = self._require_human_turn()
        before = len(m.hands[self.human_index])
        m.pass_turn(self.human_index)
        self._record_turn(self.human_index, before)
        self._finish_round()
        self.prepare_human_turn()

    def exchange(self, index: int):
        m = self.match
        if not self.human_mode or not m or not m.tribute_pending:
            raise ValueError("当前没有待完成的进贡或还贡")
        card = self._cards_at([index])[0]
        m.event_callback = self.events.append
        try:
            m.submit_tribute(card)
        finally:
            m.event_callback = None
        self.prepare_human_turn()

    def _record_turn(self, index, before):
        m = self.match
        assert m is not None
        self.turns += 1
        played = len(m.hands[index]) < before
        self.player_cards[index] = list(m.last_play.cards) if played and m.last_play else []
        self.player_plays[index] = "出牌" if played else "过牌"
        self.events.extend(format_turn_log(m, index, before, self.turns))

    def _finish_round(self):
        m = self.match
        if m is None or len(m.finish_order) != 4:
            return
        result = m.round_result()
        winner = result.winning_team
        progress = advance_levels(self.team_levels, winner, result.upgrade_level)
        self.leading_team = progress.leading_team
        self.team_levels = progress.team_levels
        if progress.finished:
            self.series_finished = True
            self.events.append(f"{winner}队A级双下，比赛结束。")
            return
        self.events.append(f"下一局全桌打 {self.team_levels[winner].name}；升级进度：A队{self.team_levels['A'].name}级，B队{self.team_levels['B'].name}级。")
        self._start_round(previous_result=result)

    def drain_events(self) -> list[str]:
        events, self.events = self.events, []
        return events

    def snapshot(self) -> dict:
        """Full local state for rendering. Hand indices distinguish duplicate cards.

        This is an offline view, not a multiplayer visibility/security boundary.
        Indices must be refreshed after every action; never cache them across turns.
        """
        def card_data(card):
            return {"suit": card.suit.value, "rank": int(card.rank)}

        m = self.match
        return {
            "round_number": self.round_number, "turns": self.turns,
            "human_mode": self.human_mode, "human_index": self.human_index,
            "series_finished": self.series_finished,
            "team_levels": {team: int(rank) for team, rank in self.team_levels.items()},
            "leading_team": self.leading_team,
            "level_rank": int(m.level_rank) if m else None,
            "current_player": m.current_player if m else None,
            "finish_order": list(m.finish_order) if m else [],
            "hands": [[dict(card_data(c), index=i) for i, c in enumerate(hand)]
                      for hand in m.hands] if m else [],
            "player_cards": [[card_data(c) for c in cards] for cards in self.player_cards],
            "player_plays": list(self.player_plays),
            "human_can_play": self.human_can_play,
            "can_pass": bool(self.human_can_play and m and m.last_play),
            "pending_exchange": self.pending_exchange_kind,
            "eligible_exchange_indices": [i for i, c in enumerate(m.hands[self.human_index])
                if any(c is eligible for eligible in m.tribute_session.eligible_cards())]
                if m and m.tribute_pending and m.tribute_session else [],
        }
