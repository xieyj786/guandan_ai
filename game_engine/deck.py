"""两副牌的生成与四人发牌。"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .card import Card, Rank, Suit

_NATURAL_RANKS = [
    Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN, Rank.EIGHT,
    Rank.NINE, Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE, Rank.TWO,
]
_SUITS = [Suit.SPADE, Suit.HEART, Suit.CLUB, Suit.DIAMOND]


def build_deck() -> list[Card]:
    """生成未洗牌的两副标准掼蛋牌（108 张）。"""
    deck: list[Card] = []
    for _ in range(2):
        for suit in _SUITS:
            for rank in _NATURAL_RANKS:
                deck.append(Card(suit, rank))
        deck.extend((Card(Suit.JOKER, Rank.SMALL_JOKER), Card(Suit.JOKER, Rank.BIG_JOKER)))
    return deck


def deal_hands(seed: int | None = None) -> list[list[Card]]:
    """洗牌后按座位顺序返回四副各 27 张的手牌。"""
    deck = build_deck()
    random.Random(seed).shuffle(deck)
    return [deck[i * 27:(i + 1) * 27] for i in range(4)]


@dataclass
class OpeningDeal:
    """首局明牌发牌结果；编号是洗牌前牌堆中的唯一位置，范围0～107。"""
    hands: list[list[Card]]
    card_ids: list[list[int]]
    face_up_card: Card
    face_up_id: int
    face_up_position: int  # 插回后的牌堆位置，从0开始
    first_receiver: int
    first_player: int


def opening_count(card: Card) -> int:
    if card.suit == Suit.JOKER:
        raise ValueError("大小王不能作为首局明牌，请重新抽牌")
    return 1 if card.rank == Rank.ACE else int(card.rank)


def deal_opening(seed: int | None = None) -> OpeningDeal:
    """洗牌、抽明牌（王重抽）、随机插回、从起牌者逐张逆时针发牌。"""
    rng = random.Random(seed)
    deck = list(enumerate(build_deck()))
    rng.shuffle(deck)
    while True:
        chosen = rng.randrange(len(deck))
        if deck[chosen][1].suit != Suit.JOKER:
            break
    identifier, face_up = deck.pop(chosen)
    position = rng.randrange(len(deck) + 1)
    deck.insert(position, (identifier, face_up))
    first_receiver = (opening_count(face_up) - 1) % 4
    hands: list[list[Card]] = [[] for _ in range(4)]
    ids: list[list[int]] = [[] for _ in range(4)]
    first_player = (first_receiver + position) % 4
    for offset, (card_id, card) in enumerate(deck):
        seat = (first_receiver + offset) % 4
        hands[seat].append(card)
        ids[seat].append(card_id)
    return OpeningDeal(hands, ids, face_up, identifier, position, first_receiver, first_player)
