"""
牌型大小比较逻辑。

规则（见 rules_design.md 1.2）：
    1. 若双方都是炸弹Tier（含同花顺、天王炸）内的类型
       -> 按 BOMB_TIER_ORDER 索引比较，索引大者赢；索引相同再比 power（点数）
    2. 若一方是炸弹Tier、另一方不是
       -> 炸弹Tier方直接赢（炸弹/同花顺可压任意非炸弹牌型）
    3. 若双方都不是炸弹Tier
       -> 必须 category 相同且 length 相同才能比较，否则非法比较（不可出）
"""

from .card import Rank, single_card_power
from .card_type import BOMB_TIER_ORDER, CardType, is_bomb_category


class IncomparableCardTypeError(Exception):
    """两个牌型之间无法比较大小（类型不同、长度不同、且都不是炸弹）。"""


def compare_card_type(a: CardType, b: CardType, level_rank: Rank) -> int:
    """
    比较 a 是否大于 b。

    Returns:
        1  如果 a > b
        -1 如果 a < b
        0  理论上不会出现平局（牌型比较不存在真正相等的合法出牌场景）

    Raises:
        IncomparableCardTypeError: 两者无法比较（非炸弹且类型/长度不同）
    """
    a_is_bomb = is_bomb_category(a.category)
    b_is_bomb = is_bomb_category(b.category)

    if a_is_bomb and b_is_bomb:
        tier_a = BOMB_TIER_ORDER.index(a.category)
        tier_b = BOMB_TIER_ORDER.index(b.category)
        if tier_a != tier_b:
            return 1 if tier_a > tier_b else -1
        return _compare_power(a.power, b.power)

    if a_is_bomb and not b_is_bomb:
        return 1
    if b_is_bomb and not a_is_bomb:
        return -1

    # 双方都不是炸弹：必须同类型同长度
    if a.category != b.category or a.length != b.length:
        raise IncomparableCardTypeError(
            f"无法比较 {a.category}(len={a.length}) 与 {b.category}(len={b.length})"
        )

    if a.category == a.category.SINGLE:
        # 单张走单独的 power 计算（级牌位规则），由调用方在构造 CardType 时
        # 用 single_card_power 填入 power，这里直接比较即可
        return _compare_power(a.power, b.power)

    return _compare_power(a.power, b.power)


def _compare_power(p1: float, p2: float) -> int:
    if p1 > p2:
        return 1
    if p1 < p2:
        return -1
    return 0
