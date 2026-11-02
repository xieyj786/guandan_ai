"""Legality only: candidate construction and comparison, never strategy scoring."""
from .card import Card, Rank
from .card_type import CardType
from .comparator import IncomparableCardTypeError, compare_card_type
from .moves import generate_all_moves


def beats(move: CardType, last: CardType, level: Rank) -> bool:
    try:
        return compare_card_type(move, last, level) == 1
    except IncomparableCardTypeError:
        return False


def legal_moves(hand: list[Card], level_rank: Rank, use_wildcards: bool = True,
                last_play: CardType | None = None) -> list[CardType]:
    moves = generate_all_moves(hand, level_rank, use_wildcards=use_wildcards,
                               last_play=last_play)
    return [move for move in moves if last_play is None or beats(move, last_play, level_rank)]
