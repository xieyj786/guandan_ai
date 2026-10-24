"""
高效枚举手牌能构成的所有合法牌型。

设计要点：按点数/花色分组后直接构造候选牌型，不对手牌做暴力穷举组合
（此前排查 Coze 生成代码时发现 combinations(hand, n) 式的暴力穷举在27张
手牌时会产生上亿种组合，直接卡死——这里的实现复杂度只与"不同点数的种类数"
相关，与手牌张数无关的指数爆炸。

支持百搭补对子、三张和炸弹；候选交由识别器统一确定最终牌型和力度。
顺子固定 5 张长度（同花顺同样固定 5 张，见 _straight_flushes）；连对固定3对，钢板仍支持变长。
对子/三张/三带二/炸弹的点数比较会应用级牌提升（rank_power），大王/小王也可以单独
组成"对大王"/"对小王"这样的普通对子（区别于需要凑齐4张的天王炸）。
"""

from __future__ import annotations

from collections import defaultdict

from .card import Card, Rank, Suit, is_wildcard, rank_power, single_card_power
from .card_type import CardType, CardTypeCategory
from .identify import identify_card_type

_STRAIGHT_ORDER = [
    Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN, Rank.EIGHT,
    Rank.NINE, Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE,
]
_SPECIAL_STRAIGHT = (Rank.ACE, Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE)
_JOKER_RANKS = (Rank.SMALL_JOKER, Rank.BIG_JOKER)
_BOMB_CATEGORY_BY_SIZE = {
    4: CardTypeCategory.BOMB_4,
    5: CardTypeCategory.BOMB_5,
    6: CardTypeCategory.BOMB_6,
    7: CardTypeCategory.BOMB_7,
    8: CardTypeCategory.BOMB_8,
}


def generate_all_moves(hand: list[Card], level_rank: Rank, use_wildcards: bool = True, last_play: CardType | None = None) -> list[CardType]:
    """返回手牌能构成的所有合法牌型（每种牌型每种"选牌方式"生成一个候选）。"""
    rank_groups: dict[Rank, list[Card]] = defaultdict(list)
    suit_groups: dict[Suit, list[Card]] = defaultdict(list)
    for card in hand:
        rank_groups[card.rank].append(card)
        if card.suit != Suit.JOKER:
            suit_groups[card.suit].append(card)

    # 同点数组内让逢人配排在最后：凑牌时优先用天然牌，尽量把逢人配留着
    for group in rank_groups.values():
        group.sort(key=lambda c: is_wildcard(c, level_rank))

    moves: list[CardType] = []
    moves += _singles(rank_groups, level_rank)
    moves += _pairs(rank_groups, level_rank)
    moves += _triples(rank_groups, level_rank)
    moves += _triple_plus_two(rank_groups, level_rank)
    moves += _bombs(rank_groups, level_rank)
    moves += _joker_bomb(rank_groups)
    moves += _straights(rank_groups)
    moves += _consecutive_pairs(rank_groups)
    moves += _plates(rank_groups)
    moves += _straight_flushes(suit_groups)
    if use_wildcards:
        moves += _wildcard_completions(hand, rank_groups, level_rank)
    # 同一组选牌只保留识别器的最优解释，避免 AI 与对局校验使用不同力度。
    normalized = {}
    for move in moves:
        key = tuple(sorted((c.suit.value, int(c.rank)) for c in move.cards))
        if key not in normalized:
            normalized[key] = identify_card_type(move.cards, level_rank, use_wildcards=use_wildcards, last_play=last_play)
    return list(normalized.values())


def _singles(rank_groups, level_rank) -> list[CardType]:
    return [
        CardType(category=CardTypeCategory.SINGLE, cards=[cards[0]], power=single_card_power(cards[0], level_rank))
        for cards in rank_groups.values()
    ]


def _pairs(rank_groups, level_rank) -> list[CardType]:
    """对子。大王/小王也可以单独凑成"对大王"/"对小王"这样的普通对子。"""
    moves = []
    for rank, cards in rank_groups.items():
        if len(cards) < 2:
            continue
        moves.append(CardType(category=CardTypeCategory.PAIR, cards=cards[:2], power=rank_power(rank, level_rank)))
    return moves


def _triples(rank_groups, level_rank) -> list[CardType]:
    moves = []
    for rank, cards in rank_groups.items():
        if rank in _JOKER_RANKS or len(cards) < 3:
            continue  # 大小王最多各2张，凑不出三张
        moves.append(CardType(category=CardTypeCategory.TRIPLE, cards=cards[:3], power=rank_power(rank, level_rank)))
    return moves


def _triple_plus_two(rank_groups, level_rank) -> list[CardType]:
    moves = []
    triple_ranks = [r for r, c in rank_groups.items() if r not in _JOKER_RANKS and len(c) >= 3]
    pair_ranks = [r for r, c in rank_groups.items() if len(c) >= 2]
    for t_rank in triple_ranks:
        for p_rank in pair_ranks:
            if p_rank == t_rank:
                continue
            cards = rank_groups[t_rank][:3] + rank_groups[p_rank][:2]
            moves.append(CardType(
                category=CardTypeCategory.TRIPLE_WITH_PAIR, cards=cards, power=rank_power(t_rank, level_rank),
            ))
    return moves


def _bombs(rank_groups, level_rank) -> list[CardType]:
    moves = []
    for rank, cards in rank_groups.items():
        if rank in _JOKER_RANKS or len(cards) < 4:
            continue  # 大小王最多各2张，凑不出4张炸弹；天王炸走 _joker_bomb 单独处理
        for size in range(4, min(len(cards), 8) + 1):
            moves.append(CardType(
                category=_BOMB_CATEGORY_BY_SIZE[size], cards=cards[:size], power=rank_power(rank, level_rank),
            ))
    return moves


def _joker_bomb(rank_groups) -> list[CardType]:
    small = rank_groups.get(Rank.SMALL_JOKER, [])
    big = rank_groups.get(Rank.BIG_JOKER, [])
    if len(small) == 2 and len(big) == 2:
        return [CardType(category=CardTypeCategory.JOKER_BOMB, cards=small + big, power=float("inf"))]
    return []


def _present_mask(rank_groups, min_count: int) -> list[bool]:
    return [len(rank_groups.get(r, [])) >= min_count for r in _STRAIGHT_ORDER]


def _find_runs(mask: list[bool]) -> list[tuple[int, int]]:
    """返回 mask 中值为 True 的最长连续段 [(start, end)]（闭区间索引）。"""
    runs = []
    start = None
    for i, ok in enumerate(mask + [False]):
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            runs.append((start, i - 1))
            start = None
    return runs


def _straights(rank_groups) -> list[CardType]:
    """顺子固定为5张连续单张，支持2-3-4-5-6和A-2-3-4-5。"""
    moves = []
    for start, end in _find_runs(_present_mask(rank_groups, 1)):
        run_len = end - start + 1
        for offset in range(run_len - 5 + 1):
            s = start + offset
            cards = [rank_groups[_STRAIGHT_ORDER[i]][0] for i in range(s, s + 5)]
            if len({c.suit for c in cards}) == 1:
                # 保留可用的混花顺子，避免代表牌全同花时遗漏普通顺子。
                suit = cards[0].suit
                for index, card in enumerate(cards):
                    alternative = next((c for c in rank_groups[card.rank] if c.suit != suit), None)
                    if alternative is not None:
                        cards[index] = alternative
                        break
            moves.append(CardType(
                category=CardTypeCategory.STRAIGHT, cards=cards,
                power=float(_STRAIGHT_ORDER[s + 4]), length=5,
            ))
    special = _special_window(rank_groups, _SPECIAL_STRAIGHT)
    if special is not None:
        cards = list(special)
        if len({c.suit for c in cards}) == 1:
            suit = cards[0].suit
            for index, card in enumerate(cards):
                alternative = next((c for c in rank_groups[card.rank] if c.suit != suit), None)
                if alternative is not None:
                    cards[index] = alternative
                    break
        moves.append(CardType(category=CardTypeCategory.STRAIGHT, cards=cards,
                              power=float(Rank.FIVE), length=5))
    return moves


def _consecutive_pairs(rank_groups) -> list[CardType]:
    moves = []
    for start, end in _find_runs(_present_mask(rank_groups, 2)):
        run_len = end - start + 1
        for length in (3,):
            for offset in range(run_len - length + 1):
                s = start + offset
                idxs = range(s, s + length)
                cards = [c for i in idxs for c in rank_groups[_STRAIGHT_ORDER[i]][:2]]
                moves.append(CardType(
                    category=CardTypeCategory.CONSECUTIVE_PAIRS, cards=cards,
                    power=float(_STRAIGHT_ORDER[s + length - 1]), length=length,
                ))
    return moves


def _plates(rank_groups) -> list[CardType]:
    moves = []
    for start, end in _find_runs(_present_mask(rank_groups, 3)):
        run_len = end - start + 1
        for length in range(2, run_len + 1):
            for offset in range(run_len - length + 1):
                s = start + offset
                idxs = range(s, s + length)
                cards = [c for i in idxs for c in rank_groups[_STRAIGHT_ORDER[i]][:3]]
                moves.append(CardType(
                    category=CardTypeCategory.PLATE, cards=cards,
                    power=float(_STRAIGHT_ORDER[s + length - 1]), length=length,
                ))
    return moves


def _straight_flushes(suit_groups) -> list[CardType]:
    moves = []
    rank_order_index = {r: i for i, r in enumerate(_STRAIGHT_ORDER)}
    for cards in suit_groups.values():
        by_rank: dict[Rank, Card] = {}
        for c in cards:
            if c.rank in rank_order_index:
                by_rank.setdefault(c.rank, c)
        mask = [r in by_rank for r in _STRAIGHT_ORDER]
        for start, end in _find_runs(mask):
            run_len = end - start + 1
            for offset in range(run_len - 5 + 1):
                s = start + offset
                window_cards = [by_rank[_STRAIGHT_ORDER[i]] for i in range(s, s + 5)]
                moves.append(CardType(
                    category=CardTypeCategory.STRAIGHT_FLUSH, cards=window_cards,
                    power=float(_STRAIGHT_ORDER[s + 4]), length=5,
                ))
        special = _special_window(by_rank, _SPECIAL_STRAIGHT)
        if special is not None:
            moves.append(CardType(category=CardTypeCategory.STRAIGHT_FLUSH, cards=special,
                                  power=float(Rank.FIVE), length=5))
    return moves


def _special_window(groups, window):
    if all(rank in groups for rank in window):
        return [groups[rank][0] if isinstance(groups[rank], list) else groups[rank] for rank in window]
    return None


def _wildcard_completions(hand, rank_groups, level_rank) -> list[CardType]:
    """
    逢人配补牌候选（当前阶段只做最简单的用法，更灵活的搭配留给后续 AI 代理）：
        - 用逢人配把某点数补成炸弹：3张+1 -> 4张炸弹，4张+1 -> 5张炸弹，2张+2 -> 4张炸弹 ...
        - 兜底：单张+逢人配 -> 对子；两张+逢人配 -> 三张（同理一张+两张逢人配 -> 三张）
    不生成顺子/钢板/连对/同花顺的逢人配补位（引擎的识别层已完整支持，
    人类玩家或后续 AI 可以直接使用）。级牌本身不参与补牌（红心级牌已在级牌点数组内）。
    """
    wilds = [c for c in hand if is_wildcard(c, level_rank)]
    if not wilds:
        return []

    moves = []
    for rank, cards in rank_groups.items():
        if rank in _JOKER_RANKS or rank == level_rank:
            continue
        for count in range(1, min(len(cards), 8) + 1):
            for k in range(1, len(wilds) + 1):
                total = count + k
                if total > 8:
                    continue
                category = {2: CardTypeCategory.PAIR, 3: CardTypeCategory.TRIPLE}.get(total)
                if category is None:
                    category = _BOMB_CATEGORY_BY_SIZE[total]
                moves.append(CardType(
                    category=category, cards=list(cards[:count]) + wilds[:k],
                    power=rank_power(rank, level_rank), wildcards_used=wilds[:k],
                ))
    return moves
