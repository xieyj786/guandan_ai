"""
牌型识别（支持红心级牌 / 逢人配）。

给定一组已选定要打出的牌，判断它们能构成哪些合法牌型。
逢人配规则（见 rules_design.md 1.4，本次与参考项目对齐）：
    - 逢人配 = 红心级牌，全场最多 2 张，可替代任意"非王"的牌；
    - 逢人配不能替代大小王：王对子、天王炸都必须由真王凑成；
    - 单独出一张逢人配时按级牌位排序（不触发百搭）；
    - 两张逢人配单独成对，按级牌对子算；
    - 不支持甩牌，每次只出一个牌型，因此百搭只需在单一牌型内部补缺口，
      而天然牌的点数分布基本已经锁定了目标牌型；
    - 一组牌有多种合法解释时，自动取"对出牌者最有利"的那一种：
      能压过上家的解释中最大的一个（没有上家则取整体最大的一个）。

其他约定：
    - 顺子/同花顺固定 5 张；连对固定3档；钢板（2档及以上）允许变长；
    - 顺子/连对/钢板不含王；普通2可参与，另支持特殊顺子 A-2-3-4-5；
    - 五张同花色加逢人配补缺口，视为同花顺（比普通顺子更大）；
    - "三带二"为临时开发牌型：三张 + 一对（对子可以是王对子），大小由三张决定；
    - 对子/三张/三带二/炸弹按点数比较时，级牌被提升到 A 与小王之间（card.rank_power）。

对外接口：
    enumerate_interpretations(cards, level_rank) -> list[CardType]   # 列出全部合法解释
    identify_card_type(cards, level_rank, use_wildcards=True, last_play=None) -> CardType  # 选出最优解释
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from .card import Card, Rank, Suit, is_wildcard, rank_power, single_card_power
from .card_type import (
    BOMB_TIER_ORDER,
    CardType,
    CardTypeCategory,
    InvalidCardTypeError,
    is_bomb_category,
)
from .comparator import IncomparableCardTypeError, compare_card_type

# 顺子/连对/钢板允许出现的点数范围：2~A，不含大小王。
# 非当前级牌的2按普通小牌处理，因此2-3-4-5-6等牌型合法。
_STRAIGHT_ORDER = [
    Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN, Rank.EIGHT,
    Rank.NINE, Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE,
]
_SPECIAL_STRAIGHT = (Rank.ACE, Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE)
_STRAIGHT_RANKS = set(_STRAIGHT_ORDER)
_JOKER_RANKS = (Rank.SMALL_JOKER, Rank.BIG_JOKER)

_BOMB_CATEGORY_BY_SIZE = {
    4: CardTypeCategory.BOMB_4,
    5: CardTypeCategory.BOMB_5,
    6: CardTypeCategory.BOMB_6,
    7: CardTypeCategory.BOMB_7,
    8: CardTypeCategory.BOMB_8,
}


def identify_card_type(cards: list[Card], level_rank: Rank, use_wildcards: bool = True, last_play: Optional[CardType] = None) -> CardType:
    """
    识别一组已选定的牌构成的牌型；识别失败抛出 InvalidCardTypeError。

    last_play: 上家的出牌（可选）。提供时，优先在"能压过上家"的解释里挑最大的；
               若没有任何解释能压过，返回整体最大的解释（由调用方再做比较并判定非法）。
    """
    interpretations = enumerate_interpretations(cards, level_rank, use_wildcards)
    if not interpretations:
        raise InvalidCardTypeError(f"无法为 {cards} 识别出合法牌型")

    if last_play is not None:
        beating = []
        for interp in interpretations:
            try:
                if compare_card_type(interp, last_play, level_rank) == 1:
                    beating.append(interp)
            except IncomparableCardTypeError:
                continue
        if beating:
            interpretations = beating

    return max(interpretations, key=_interpretation_key)


def enumerate_interpretations(cards: list[Card], level_rank: Rank, use_wildcards: bool = True) -> list[CardType]:
    """返回这组牌所有合法的牌型解释（含逢人配的各种替代方案）。空列表表示不是合法牌型。"""
    if not cards:
        return []
    for card in cards:
        if not isinstance(card, Card) or not isinstance(card.suit, Suit) or not isinstance(card.rank, Rank):
            return []
        if (card.suit == Suit.JOKER) != (card.rank in _JOKER_RANKS):
            return []
    if any(count > 2 for count in Counter(cards).values()):
        return []

    wild = [c for c in cards if use_wildcards and is_wildcard(c, level_rank)]
    natural = [c for c in cards if not (use_wildcards and is_wildcard(c, level_rank))]
    if len(wild) > 2:
        return []

    n = len(cards)
    counts = Counter(c.rank for c in natural)

    if _is_joker_bomb(cards):
        return [CardType(category=CardTypeCategory.JOKER_BOMB, cards=cards, power=float("inf"), length=4)]

    if n == 1:
        return [CardType(
            category=CardTypeCategory.SINGLE, cards=cards,
            power=single_card_power(cards[0], level_rank), length=1,
        )]

    results: list[CardType] = []
    results += _same_rank_interpretations(cards, natural, wild, counts, level_rank)
    if n == 5:
        results += _triple_plus_two_interpretations(cards, wild, counts, level_rank)
        results += _straight_interpretations(cards, natural, wild, counts)
    if n == 6:
        results += _run_interpretations(cards, wild, counts, group=2, min_len=3,
                                        category=CardTypeCategory.CONSECUTIVE_PAIRS)
    if n >= 6 and n % 3 == 0:
        results += _run_interpretations(cards, wild, counts, group=3, min_len=2,
                                        category=CardTypeCategory.PLATE)
    return results


def _interpretation_key(ct: CardType):
    tier = BOMB_TIER_ORDER.index(ct.category) if is_bomb_category(ct.category) else -1
    return (tier, ct.power, ct.length)


def _is_joker_bomb(cards: list[Card]) -> bool:
    jokers = [c for c in cards if c.suit == Suit.JOKER]
    if len(cards) != 4 or len(jokers) != 4:
        return False
    big = sum(1 for c in jokers if c.rank == Rank.BIG_JOKER)
    return big == 2


def _same_rank_interpretations(cards, natural, wild, counts, level_rank) -> list[CardType]:
    """对子 / 三张 / 4~8 张炸弹：天然牌点数一致，缺口由逢人配补齐。"""
    n = len(cards)
    if not 2 <= n <= 8:
        return []

    if any(r in _JOKER_RANKS for r in counts):
        # 逢人配不能替代王：王对子必须是两张同种真王
        if len(counts) == 1 and not wild and n == 2:
            rank = next(iter(counts))
            return [CardType(category=CardTypeCategory.PAIR, cards=cards, power=rank_power(rank, level_rank), length=n)]
        return []

    if not counts:
        # 全是逢人配：两张逢人配 = 级牌对子
        if n == 2:
            return [CardType(
                category=CardTypeCategory.PAIR, cards=cards,
                power=rank_power(level_rank, level_rank), length=2, wildcards_used=list(wild),
            )]
        return []

    if len(counts) != 1:
        return []

    rank = next(iter(counts))
    category = {2: CardTypeCategory.PAIR, 3: CardTypeCategory.TRIPLE}.get(n) or _BOMB_CATEGORY_BY_SIZE[n]
    return [CardType(category=category, cards=cards, power=rank_power(rank, level_rank), length=n, wildcards_used=list(wild))]


def _triple_plus_two_interpretations(cards, wild, counts, level_rank) -> list[CardType]:
    """三带二（临时牌型）：一组三张 + 一对，两组点数不同；对子可以是王对子；大小由三张决定。"""
    w = len(wild)
    results = []
    ranks = list(counts)
    for t in ranks:
        if t in _JOKER_RANKS or counts[t] > 3:
            continue
        need_triple = 3 - counts[t]
        others = [r for r in ranks if r != t]
        if len(others) > 1:
            continue
        if others:
            p = others[0]
            if counts[p] > 2:
                continue
            need_pair = 2 - counts[p]
            if p in _JOKER_RANKS and need_pair > 0:
                continue  # 逢人配不能补成王
        else:
            need_pair = 2  # 对子部分完全由逢人配充当，点数任意，不影响大小
        if need_triple + need_pair == w:
            results.append(CardType(
                category=CardTypeCategory.TRIPLE_WITH_PAIR, cards=cards,
                power=rank_power(t, level_rank), length=5, wildcards_used=list(wild),
            ))
    return results


def _straight_interpretations(cards, natural, wild, counts) -> list[CardType]:
    """5 张顺子 / 同花顺：天然牌点数互不相同且落在某个 5 连窗口内，空缺由逢人配补。"""
    if any(r not in _STRAIGHT_RANKS for r in counts) or any(c != 1 for c in counts.values()):
        return []
    results = []
    same_suit = len({c.suit for c in natural}) <= 1
    for start in range(len(_STRAIGHT_ORDER) - 4):
        window = _STRAIGHT_ORDER[start:start + 5]
        if not set(counts) <= set(window):
            continue
        top = float(window[-1])
        results.append(CardType(
            category=CardTypeCategory.STRAIGHT, cards=cards, power=top, length=5, wildcards_used=list(wild),
        ))
        if same_suit:
            results.append(CardType(
                category=CardTypeCategory.STRAIGHT_FLUSH, cards=cards, power=top, length=5,
                wildcards_used=list(wild),
            ))
    window = _SPECIAL_STRAIGHT
    if set(counts) <= set(window) and len(counts) + len(wild) == 5:
        top = float(Rank.FIVE)
        results.append(CardType(category=CardTypeCategory.STRAIGHT, cards=cards,
                                power=top, length=5, wildcards_used=list(wild)))
        if same_suit:
            results.append(CardType(category=CardTypeCategory.STRAIGHT_FLUSH, cards=cards,
                                    power=top, length=5, wildcards_used=list(wild)))
    return results


def _run_interpretations(cards, wild, counts, group: int, min_len: int, category) -> list[CardType]:
    """连对（每档2张）/ 钢板（每档3张）：天然牌落在某个连续窗口内且每档不超过 group 张。"""
    if any(r not in _STRAIGHT_RANKS for r in counts) or any(c > group for c in counts.values()):
        return []
    k = len(cards) // group
    if k < min_len or k > len(_STRAIGHT_ORDER):
        return []
    results = []
    for start in range(len(_STRAIGHT_ORDER) - k + 1):
        window = _STRAIGHT_ORDER[start:start + k]
        if set(counts) <= set(window):
            results.append(CardType(
                category=category, cards=cards, power=float(window[-1]), length=k, wildcards_used=list(wild),
            ))
    return results
