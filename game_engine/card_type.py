"""
牌型分类定义。

出牌方式约束：每次出牌只能是单一牌型（不支持多组合甩牌）。
逢人配（红心级牌）规则见 rules_design.md 1.4 节：
  - 单张按级牌比较；两张红心级牌单独成对按级牌对子比较。
  - 可补任意非王牌型，不能替代大小王；全场最多两张。
"""

from dataclasses import dataclass, field
from enum import Enum, auto

from .card import Card


class CardTypeCategory(Enum):
    SINGLE = auto()
    PAIR = auto()
    TRIPLE = auto()
    TRIPLE_WITH_PAIR = auto()    # 三带二，3张同点+2张同点
    STRAIGHT = auto()             # 顺子，固定5张连续单张
    CONSECUTIVE_PAIRS = auto()    # 连对，固定3对共6张
    PLATE = auto()                # 钢板，2组及以上连续三张
    BOMB_4 = auto()
    BOMB_5 = auto()
    STRAIGHT_FLUSH = auto()       # 同花顺
    BOMB_6 = auto()
    BOMB_7 = auto()
    BOMB_8 = auto()
    JOKER_BOMB = auto()           # 天王炸


# 炸弹 Tier 顺序：索引越大越强。非炸弹类型不在此列表中，
# 非炸弹类型之间互不可比（必须同类型同长度才能比较）。
BOMB_TIER_ORDER = [
    CardTypeCategory.BOMB_4,
    CardTypeCategory.BOMB_5,
    CardTypeCategory.STRAIGHT_FLUSH,
    CardTypeCategory.BOMB_6,
    CardTypeCategory.BOMB_7,
    CardTypeCategory.BOMB_8,
    CardTypeCategory.JOKER_BOMB,
]

NON_BOMB_CATEGORIES = {
    CardTypeCategory.SINGLE,
    CardTypeCategory.PAIR,
    CardTypeCategory.TRIPLE,
    CardTypeCategory.TRIPLE_WITH_PAIR,
    CardTypeCategory.STRAIGHT,
    CardTypeCategory.CONSECUTIVE_PAIRS,
    CardTypeCategory.PLATE,
}


def is_bomb_category(category: CardTypeCategory) -> bool:
    return category in BOMB_TIER_ORDER


@dataclass
class CardType:
    """
    牌型识别结果。

    category:      识别出的牌型分类
    cards:         实际打出的牌（含百搭牌本身）
    wildcards_used: 参与百搭顶替的牌列表（子集of cards）
    power:         用于同类型/同Tier内部比较的点数强度（如顺子取最大点数、
                   炸弹取点数、天王炸/唯一类型可设为固定极大值）
    length:        参与比较长度校验用（顺子固定为5，连对/钢板按组数），
                   非顺子类连续牌型的长度含义见具体实现
    """
    category: CardTypeCategory
    cards: list[Card]
    wildcards_used: list[Card] = field(default_factory=list)
    power: float = 0.0
    length: int = 0

    def is_bomb_tier(self) -> bool:
        return is_bomb_category(self.category)


class InvalidCardTypeError(Exception):
    """选定的一组牌无法构成任何合法牌型时抛出。"""
