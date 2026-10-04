"""
对战循环（Match Runner）—— Phase 1 目标："4 个 AI 自动打完一整局"。

职责：轮转出牌顺序、构造每个 Agent 的 Observation、调用 Agent.decide()，
用 game_engine（规则引擎）独立校验每一手出牌的合法性，维护"过牌收回出牌权"
和"打完的人退出轮转"的逻辑，最终交给 round_result 判定终局。

不属于本文件职责（留给后续阶段）：
    - 多局升级（由 GameSeries 或桌面入口传入上局结果，prepare 执行进还贡）
    - 网络/房间管理（对应架构图里的"对战调度服务"，本文件是它的最小离线版本）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from agents.base import Agent, Observation
from game_engine.card import Card, Rank, card_display
from game_engine.card_type import CardType
from game_engine.comparator import compare_card_type
from game_engine.comparator import IncomparableCardTypeError
from game_engine.deck import OpeningDeal, deal_hands, deal_opening
from game_engine.identify import identify_card_type
from game_engine.round_result import Player as RoundPlayer
from game_engine.round_result import RoundResult, judge_round_end
from game_engine.tribute import TributeOutcome, TributeSession, exchange_tribute


class IllegalMoveError(Exception):
    """Agent 给出的动作违反规则（出了手里没有的牌 / 压不过上家 / 首出时选择PASS）。"""


@dataclass
class Match:
    """
    单局对战编排器。

    agents: 长度为4的Agent列表，座位顺序即 agents[0..3]；队伍固定为 0&2 一队、1&3 一队
            （对应 round_result.py 里 team="A"/"B" 的约定）
    level_rank: 全桌统一的本局级牌；team_levels 仅记录双方升级进度
    """
    agents: list[Agent]
    level_rank: Rank = Rank.TWO
    verbose: bool = True
    seed: Optional[int] = None
    event_callback: Optional[Callable[[str], None]] = None
    use_wildcards: bool = True
    team_levels: Optional[dict[str, Rank]] = None

    previous_result: Optional[RoundResult] = None
    tribute_outcome: Optional[TributeOutcome] = field(default=None, init=False)
    tribute_session: Optional[TributeSession] = field(default=None, init=False)
    opening_deal: Optional[OpeningDeal] = field(default=None, init=False)
    prepared: bool = field(default=False, init=False)

    hands: list[list[Card]] = field(default_factory=list, init=False)
    finish_order: list[int] = field(default_factory=list, init=False)
    current_player: int = field(default=0, init=False)
    last_play: Optional[CardType] = field(default=None, init=False)
    last_player: Optional[int] = field(default=None, init=False)
    public_history: list[str] = field(default_factory=list, init=False)
    played_cards: list[Card] = field(default_factory=list, init=False)
    pass_streak: int = field(default=0, init=False)

    def __post_init__(self):
        if len(self.agents) != 4:
            raise ValueError("Match 需要正好 4 个 Agent")
        if len({agent.name for agent in self.agents}) != 4:
            raise ValueError("四名 Agent 的名字必须唯一，以确定进贡对象")
        if self.team_levels is None:
            self.team_levels = {"A": self.level_rank, "B": self.level_rank}

    def _emit(self, message: str):
        self.public_history.append(message)
        if self.event_callback:
            self.event_callback(message)

    def _team_of(self, idx: int) -> str:
        return "A" if idx % 2 == 0 else "B"

    # ---------- 对外主入口 ----------

    def prepare(self, interactive_player: str | None = None) -> None:
        """发牌并执行上局产生的进还贡；重复调用不重新发牌或重复交换。"""
        if self.prepared:
            return
        if self.previous_result is None:
            self.opening_deal = deal_opening(seed=self.seed)
            hands = self.opening_deal.hands
        else:
            hands = deal_hands(seed=self.seed)
        names = {agent.name: i for i, agent in enumerate(self.agents)}
        outcome = None
        if self.previous_result is not None:
            previous = self.previous_result
            if ({p.player_id for p in previous.finish_order} != set(names)
                    or any(p.team != self._team_of(names[p.player_id]) for p in previous.finish_order)):
                raise ValueError("上一局玩家和队伍必须与本局一致")
            mapping = {agent.name: hands[i] for i, agent in enumerate(self.agents)}
            if interactive_player is not None:
                self.tribute_session = TributeSession(previous, mapping, self.level_rank, interactive_player)
                outcome = self.tribute_session.outcome
            else:
                outcome = exchange_tribute(previous, mapping, self.level_rank)
        self.hands = hands
        self.tribute_outcome = outcome
        self.current_player = (names[outcome.first_player.player_id] if outcome else
                               self.opening_deal.first_player if self.opening_deal else 0)
        self.prepared = True
        if self.opening_deal is not None:
            deal = self.opening_deal
            messages = [f"首局翻牌：{card_display(deal.face_up_card)} → {self.agents[deal.first_receiver].name} 起牌",
                        f"明牌位于第{deal.face_up_position + 1}张 → {self.agents[deal.first_player].name} 获得明牌，首先出牌"]
            for message in messages:
                if self.verbose:
                    print(message)
                self._emit(message)
        if outcome is not None and not self.tribute_pending:
            self._log_tribute()

    @property
    def tribute_pending(self):
        return self.tribute_session is not None and not self.tribute_session.complete

    def submit_tribute(self, card):
        if self.tribute_session is None or not self.tribute_pending:
            raise ValueError("当前无需进还贡")
        self.tribute_session.submit(card)
        if not self.tribute_pending:
            self._log_tribute()

    def _log_tribute(self):
        outcome = self.tribute_outcome
        if outcome is not None:
            messages = []
            if outcome.anti_tribute:
                messages.append("抗贡成功：跳过进贡、还贡")
            else:
                for assignment in outcome.assignments:
                    assert assignment.return_card is not None
                    messages.append(f"{assignment.giver.player_id} 向 {assignment.receiver.player_id} 进贡 {card_display(assignment.tribute_card)}；"
                                    f"{assignment.receiver.player_id} 还贡 {card_display(assignment.return_card)}")
            messages.append(f"本局首出：{outcome.first_player.player_id}")
            for message in messages:
                if self.verbose:
                    print(message)
                self._emit(message)

    def run(self, max_turns: int = 3000) -> RoundResult:
        self.prepare()
        if self.verbose:
            self._log_deal()

        turns = 0
        while len(self.finish_order) < 4:
            if turns >= max_turns:
                raise RuntimeError(f"对局未在 {max_turns} 回合内结束，可能存在逻辑错误")
            turns += 1
            self._take_turn()

        result = self._build_round_result()
        if self.verbose:
            self._log_result(result)
        return result

    # ---------- 单回合处理 ----------

    def _take_turn(self):
        if self.tribute_pending:
            raise IllegalMoveError("请先完成进贡和还贡")
        idx = self.current_player
        if self._is_finished(idx):
            self.current_player = self._next_active(idx)
            return

        # 只剩一名玩家还有牌时，没有对手可以响应，直接让其自由领出
        active = self._active_players()
        if len(active) == 1 and self.last_play is not None:
            self.last_play = None
            self.pass_streak = 0

        observation = self._build_observation(idx)
        action = self.agents[idx].decide(observation)

        self.last_rule_reason = (idx, getattr(self.agents[idx], "decision_reason", ""))
        if action.action_type == "pass":
            self._handle_pass(idx)
        else:
            self._handle_play(idx, action.cards)

    def _handle_pass(self, idx: int):
        if self.tribute_pending:
            raise IllegalMoveError("请先完成进贡和还贡")
        if self.last_play is None:
            raise IllegalMoveError(f"{self.agents[idx].name} 处于首出位置，不能选择 PASS")

        if self.verbose:
            print(f"⏭️  {self.agents[idx].name} 过")
        self._emit(f"{self.agents[idx].name} 过牌")
        self.pass_streak += 1

        active = self._active_players()
        others_needed = len(active) - (1 if self.last_player in active else 0)

        if self.pass_streak >= others_needed:
            assert self.last_player is not None
            teammate = (self.last_player + 2) % 4
            if self.last_player in active:
                reclaim_to = self.last_player
            elif teammate in active:
                reclaim_to = teammate
                self._emit(f"{self.agents[teammate].name} 接风，重新领出。")
            else:
                # 队友也已走完时，顺序交给下一位仍有牌的玩家。
                reclaim_to = self._next_active(self.last_player)
            if self.verbose:
                print(f"   --- 收回出牌权，轮到 {self.agents[reclaim_to].name} 重新领出 ---")
            self.last_play = None
            self.pass_streak = 0
            self.current_player = reclaim_to
            return

        self.current_player = self._next_active(idx)

    def _handle_play(self, idx: int, cards: list[Card]):
        if self.tribute_pending:
            raise IllegalMoveError("请先完成进贡和还贡")
        hand = self.hands[idx]
        remaining = list(hand)
        for card in cards:
            if card not in remaining:
                raise IllegalMoveError(
                    f"{self.agents[idx].name} 出了手里没有的牌：{[card_display(c) for c in cards]}"
                )
            remaining.remove(card)

        if not cards:
            raise IllegalMoveError(f"{self.agents[idx].name} 选择出空牌组")

        played_type = identify_card_type(cards, self.level_rank, use_wildcards=self.use_wildcards, last_play=self.last_play)

        if self.last_play is not None:
            try:
                beats_last_play = compare_card_type(played_type, self.last_play, self.level_rank) == 1
            except IncomparableCardTypeError as exc:
                raise IllegalMoveError(f"{self.agents[idx].name} 出的牌型无法压上家") from exc
            if not beats_last_play:
                raise IllegalMoveError(
                    f"{self.agents[idx].name} 出的牌压不过上家：{[card_display(c) for c in cards]}"
                )

        for c in cards:
            hand.remove(c)

        if self.verbose:
            cards_str = ", ".join(card_display(c) for c in cards)
            print(f"✅ {self.agents[idx].name} 出 {cards_str} ({played_type.category.name})  剩余 {len(hand)} 张")
        cards_str = ", ".join(card_display(c) for c in cards)
        self._emit(f"{self.agents[idx].name} 出牌：{cards_str} 〔{played_type.category.name}〕，剩余 {len(hand)} 张")

        self.played_cards.extend(cards)
        self.last_play = played_type
        self.last_player = idx
        self.pass_streak = 0

        if len(hand) == 0:
            self.finish_order.append(idx)
            if self.verbose:
                print(f"🏆 {self.agents[idx].name} 出完了！排名第 {len(self.finish_order)}")
            self._emit(f"{self.agents[idx].name} 已出完，排名第 {len(self.finish_order)}")

        if len(self.finish_order) < 4:
            self.current_player = self._next_active(idx)

    # ---------- 辅助方法 ----------

    def _is_finished(self, idx: int) -> bool:
        return len(self.hands[idx]) == 0

    def _active_players(self) -> list[int]:
        return [i for i in range(4) if not self._is_finished(i)]

    def _next_active(self, idx: int) -> int:
        nxt = (idx + 1) % 4
        while self._is_finished(nxt):
            nxt = (nxt + 1) % 4
        return nxt

    def _build_observation(self, idx: int) -> Observation:
        teammate_idx = (idx + 2) % 4
        opp_indices = [(idx + 1) % 4, (idx + 3) % 4]
        return Observation(
            hand=list(self.hands[idx]),
            last_play_by_teammate=self.last_play is not None and self.last_player == teammate_idx,
            played_cards=list(self.played_cards),
            play_history=self.public_history[-16:],
            use_wildcards=self.use_wildcards,
            level_rank=self.level_rank,
            last_play=self.last_play,
            teammate_hand_size=len(self.hands[teammate_idx]),
            opponent_hand_sizes=(len(self.hands[opp_indices[0]]), len(self.hands[opp_indices[1]])),
        )

    def _build_round_result(self) -> RoundResult:
        team_of = lambda i: "A" if i % 2 == 0 else "B"  # noqa: E731
        finish_players = [RoundPlayer(player_id=self.agents[i].name, team=team_of(i)) for i in self.finish_order]
        return judge_round_end(finish_players)

    def _log_deal(self):
        print("=" * 60)
        print(f"🎴 掼蛋对局开始！本局级牌：{self.level_rank.name}")
        print("=" * 60)
        for i, agent in enumerate(self.agents):
            hand_str = ", ".join(card_display(c) for c in sorted(self.hands[i], key=lambda c: c.rank))
            print(f"   {agent.name}（{'A' if i % 2 == 0 else 'B'}队）: {hand_str}")
        print("-" * 60)

    def _log_result(self, result: RoundResult):
        print("=" * 60)
        order_str = " > ".join(p.player_id for p in result.finish_order)
        print(f"🏁 名次：{order_str}")
        print(f"🎉 {result.winning_team} 队获胜，升 {result.upgrade_level} 级")
        print(f"📮 需要上贡：{[p.player_id for p in result.tribute_players]}")
        print("=" * 60)


if __name__ == "__main__":
    from agents.rule_agent import RuleAgent

    match = Match(agents=[RuleAgent(f"AI{i}") for i in range(4)])
    match.run()
