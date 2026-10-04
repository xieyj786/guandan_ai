"""
基础牌数据结构：花色、点数、单张牌、逢人配（红心级牌）判断。
"""

from dataclasses import dataclass
from enum import Enum, IntEnum


class Suit(Enum):
    SPADE = "spade"      # 黑桃
    HEART = "heart"      # 红心
    CLUB = "club"        # 梅花
    DIAMOND = "diamond"  # 方块
    JOKER = "joker"      # 大小王，无花色概念，仅用占位


class Rank(IntEnum):
    """
    点数按单张排序中的相对大小定义（不含级牌特殊位置，级牌位置在运行时插入）。
    THREE=3 ... ACE=14，级牌在实际比较时会被提升到"级牌位"（高于 ACE，低于王）。
    """
    TWO = 2       # 拆分数据说明：普通点数2，非"级牌"含义（级牌用 LEVEL_RANK_POWER 单独定权重）
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14
    SMALL_JOKER = 15
    BIG_JOKER = 16


# 级牌位的排序权重：固定在 ACE(14) 之上、SMALL_JOKER(15) 之下
LEVEL_RANK_POWER = 14.5


@dataclass(frozen=True)
class Card:
    """单张牌。大小王的 suit=Suit.JOKER，rank=Rank.SMALL_JOKER / Rank.BIG_JOKER。"""
    suit: Suit
    rank: Rank

    def __repr__(self) -> str:
        if self.suit == Suit.JOKER:
            return "大王" if self.rank == Rank.BIG_JOKER else "小王"
        return f"{self.suit.value}{self.rank.name}"


_RANK_DISPLAY = {
    Rank.JACK: "J", Rank.QUEEN: "Q", Rank.KING: "K", Rank.ACE: "A",
    Rank.SMALL_JOKER: "小王", Rank.BIG_JOKER: "大王",
}
_SUIT_DISPLAY = {
    Suit.SPADE: "♠", Suit.HEART: "♥", Suit.CLUB: "♣", Suit.DIAMOND: "♦",
}


def card_display(card: Card) -> str:
    """返回用于日志和 Agent 提示词的牌面文本，如 ``♠A``、``大王``。"""
    if card.suit == Suit.JOKER:
        return _RANK_DISPLAY[card.rank]
    rank_str = _RANK_DISPLAY.get(card.rank, str(int(card.rank)))
    return f"{_SUIT_DISPLAY[card.suit]}{rank_str}"


def is_level_card(card: Card, level_rank: Rank) -> bool:
    """判断是否为本局的级牌（不区分花色）。"""
    return card.suit != Suit.JOKER and card.rank == level_rank


def is_wildcard(card: Card, level_rank: Rank) -> bool:
    """
    判断是否为逢人配（仅红心级牌）。
    注意：is_wildcard 仅表示"这张牌具备百搭资格"，
    是否真正触发百搭效果取决于它在牌型识别中的使用方式
    （单出/配对时按 3.4 节规则可能不触发百搭，见 card_type.py 中的说明）。
    """
    return card.suit == Suit.HEART and is_level_card(card, level_rank)


def single_card_power(card: Card, level_rank: Rank) -> float:
    """
    单张牌按"单出"语境下的排序权重（大王 > 小王 > 级牌 > A > ... > 3）。
    仅用于单张/单出比较，不用于牌型内部当百搭使用的场景。
    """
    if card.suit == Suit.JOKER:
        return float(card.rank)  # SMALL_JOKER=15, BIG_JOKER=16
    if is_level_card(card, level_rank):
        return LEVEL_RANK_POWER
    return float(card.rank)


def rank_power(rank: Rank, level_rank: Rank) -> float:
    """同点数牌型的力度：级牌高于 A，低于王。"""
    return LEVEL_RANK_POWER if rank == level_rank else float(rank)
