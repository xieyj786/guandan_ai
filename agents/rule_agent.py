"""规则 AI：完整分组优先处理弱牌，保留控制牌，并根据公开信息配合队友。"""

from __future__ import annotations

from collections import Counter

from game_engine.card import Rank, is_wildcard, single_card_power
from game_engine.deck import build_deck
from game_engine.card_type import BOMB_TIER_ORDER, CardType, CardTypeCategory, is_bomb_category
from game_engine.comparator import IncomparableCardTypeError, compare_card_type
from game_engine.moves import generate_all_moves
from .base import Action, Agent, Observation



def _uses_wildcard(move: CardType, level_rank: Rank) -> bool:
    return any(is_wildcard(c, level_rank) for c in move.cards)


class RuleAgent(Agent):
    """基于公开信息配合队友；保留基础牌型选择及简单逢人配补牌策略。"""

    def decide(self, observation: Observation) -> Action:
        self.decision_reason = "按现有跟牌策略选择最省的有效牌"
        if not observation.hand:
            return Action(action_type="pass")

        moves = generate_all_moves(observation.hand, observation.level_rank,
                                   use_wildcards=observation.use_wildcards, last_play=observation.last_play)

        legal = moves if observation.last_play is None else [
            m for m in moves if self._beats(m, observation.last_play, observation.level_rank)]
        # 能合法一手出完时，优先走牌，包括队友当前控牌的情况。
        finishing = [m for m in legal if len(m.cards) == len(observation.hand)]
        if finishing:
            self.decision_reason = "可以一手出完，优先走牌"
            return Action("play", finishing[0].cards)

        unseen = Counter(build_deck()) - Counter(observation.hand) - Counter(observation.played_cards)
        ceiling = max((single_card_power(c, observation.level_rank) for c in unseen), default=0)
        if observation.last_play is not None:
            if observation.last_play_by_teammate:
                # 只处理明确的一张牌危险；只剩一张的上家已对当前牌作出响应，
                # 不因其牌少而抢队友。最高未见单牌也可能在队友手中，故这是保守估计。
                threat = (observation.opponent_hand_sizes[0] == 1
                          and observation.last_play.category == CardTypeCategory.SINGLE
                          and observation.last_play.power < ceiling)
                blockers = [m for m in legal if
                            (m.category == CardTypeCategory.SINGLE and m.power >= ceiling)
                            or is_bomb_category(m.category)] if threat else []
                if blockers:
                    self.decision_reason = "下家报单，接过牌权封堵对手"
                    return self._follow(blockers, observation.last_play, observation.level_rank)
                self.decision_reason = "队友控牌，让牌配合"
                return Action("pass")
            return self._follow(moves, observation.last_play, observation.level_rank)

        plan = self._estimate_plan(observation)
        if 1 in observation.opponent_hand_sizes:
            multiple = [m for m in plan if len(m.cards) > 1]
            if multiple:
                action = self._lead(multiple, observation.level_rank)
                self.decision_reason = "对手报单，优先出完整多张组合"
                return action
            self.decision_reason = "对手报单且只剩散单，先出最大单张"
            return Action("play", max(plan, key=lambda m: m.power).cards)
        if observation.teammate_hand_size == 1:
            control = any(is_bomb_category(m.category) or
                          (m.category == CardTypeCategory.SINGLE and m.power >= ceiling)
                          for m in plan[:3])
            if len(plan) > 3 and not control:
                # 仅送现成散单：不能拆对子、顺子、炸弹等，也不送红心配/级牌/大牌。
                grouped = {c for m in moves if len(m.cards) > 1 for c in m.cards}
                singles = [m for m in moves if m.category == CardTypeCategory.SINGLE
                           and m.cards[0] not in grouped and m.power <= 10
                           and not _uses_wildcard(m, observation.level_rank)]
                if singles:
                    self.decision_reason = "自身牌弱，送小散单帮助队友走牌"
                    return Action("play", min(singles, key=lambda m: m.power).cards)
        return self._lead(plan, observation.level_rank)

    @staticmethod
    def _beats(move: CardType, last: CardType, level: Rank) -> bool:
        try:
            return compare_card_type(move, last, level) == 1
        except IncomparableCardTypeError:
            return False

    @staticmethod
    def _estimate_plan(observation: Observation) -> list[CardType]:
        """贪心估算出完需要几手；不是最优分组，也不保证实际三轮收回牌权。

        先保留炸弹，再按一次能出最多牌分组；同样张数优先保留较强组合。
        每轮重算，确保两副同牌及红心配不会重复使用。
        """
        remaining = list(observation.hand)
        plan = []
        while remaining:
            moves = generate_all_moves(remaining, observation.level_rank,
                                       use_wildcards=observation.use_wildcards)
            move = max(moves, key=lambda m: (is_bomb_category(m.category), len(m.cards), m.power))
            plan.append(move)
            for card in move.cards:
                remaining.remove(card)
        return plan

    def _lead(self, moves: list[CardType], level_rank: Rank) -> Action:
        """只在不重复用牌的整理方案中挑选，不从所有子组合中拆出小牌。"""
        ordinary = [m for m in moves if not is_bomb_category(m.category)]
        if not ordinary:
            move = min(moves, key=lambda m: (BOMB_TIER_ORDER.index(m.category), m.power))
            self.decision_reason = "整理后只剩控制牌，先出较小炸弹"
            return Action("play", move.cards)
        natural = [m for m in ordinary if not _uses_wildcard(m, level_rank)]
        pool = natural or ordinary
        simple = {CardTypeCategory.SINGLE, CardTypeCategory.PAIR, CardTypeCategory.TRIPLE,
                  CardTypeCategory.TRIPLE_WITH_PAIR}
        # 小三带二的搭档也须是小牌，避免为了处理三张浪费大对子。
        weak = [m for m in pool if m.category in simple and
                max(single_card_power(c, level_rank) for c in m.cards) <= 10]
        if weak:
            move = min(weak, key=lambda m: (m.power, -len(m.cards)))
            self.decision_reason = "先处理整理后的小牌组合，不拆完整牌型"
        else:
            # 缺少明显弱小组时，倾向多出牌；不把顺子永久置于首位。
            move = min(pool, key=lambda m: (-len(m.cards), m.power))
            self.decision_reason = "没有明显小牌组，优先减少剩余出牌手数"
        if any(is_bomb_category(m.category) for m in moves):
            self.decision_reason += "；保留炸弹或同花顺"
        return Action("play", move.cards)

    def _follow(self, moves: list[CardType], last_play: CardType, level_rank: Rank) -> Action:
        beatable = []
        for move in moves:
            try:
                if compare_card_type(move, last_play, level_rank) == 1:
                    beatable.append(move)
            except IncomparableCardTypeError:
                continue

        if not beatable:
            self.decision_reason = "没有能压过的牌，过牌"
            return Action(action_type="pass")

        non_bomb = [m for m in beatable if not is_bomb_category(m.category)]
        natural_non_bomb = [m for m in non_bomb if not _uses_wildcard(m, level_rank)]
        pool = natural_non_bomb or non_bomb or beatable  # 天然牌 > 含逢人配的非炸弹 > 炸弹

        def key(m: CardType):
            tier = BOMB_TIER_ORDER.index(m.category) if is_bomb_category(m.category) else -1
            return (tier, m.power, _uses_wildcard(m, level_rank))

        pool.sort(key=key)
        return Action(action_type="play", cards=pool[0].cards)
