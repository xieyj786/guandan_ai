"""Versioned, public-information-only planning helpers (DP01–DP04)."""
from collections import Counter
from dataclasses import dataclass

from game_engine.card_type import is_bomb_category
from game_engine.moves import generate_all_moves

STRATEGY_VERSION = '0.3'


@dataclass(frozen=True)
class StrategyOptions:
    multi_plan: bool = True
    bomb_routes: bool = True
    risk_interception: bool = True
    endgame_cards: int = 12  # Bound ordinary-follow replanning cost; experimental, not a strength claim.

    def __post_init__(self):
        if not isinstance(self.endgame_cards, int) or isinstance(self.endgame_cards, bool) or self.endgame_cards < 0:
            raise ValueError("endgame_cards must be a nonnegative integer")


def remainder(hand, move):
    remaining = list(hand)
    for card in move.cards:
        remaining.remove(card)
    return remaining


def plans(hand, level, wildcards=True, multiple=True):
    """Bounded alternative partitions; never claim optimality or guaranteed control."""
    cache = {}
    result = []
    for mode in range(3 if multiple else 1):
        remaining = list(hand)
        plan = []
        while remaining:
            key = tuple(sorted(Counter(remaining).items(), key=lambda p: (p[0].suit.value, p[0].rank)))
            if key not in cache:
                cache[key] = generate_all_moves(remaining, level, use_wildcards=wildcards)
            moves = cache[key]
            if mode == 0:
                score = lambda m: (is_bomb_category(m.category), len(m.cards), m.power)
            elif mode == 1:
                score = lambda m: (len(m.cards), not is_bomb_category(m.category), m.power)
            else:
                score = lambda m: (is_bomb_category(m.category), len(m.cards), -m.power)
            move = max(moves, key=score)
            plan.append(move)
            remaining = remainder(remaining, move)
        if plan not in result:
            result.append(plan)
    return result


def tail_plan(hand, move, level, wildcards=True):
    """Evaluate remainder independently of the initial grouping, including final hands."""
    rest = remainder(hand, move)
    if not rest:
        return []
    choices = generate_all_moves(rest, level, use_wildcards=wildcards)
    finish = next((m for m in choices if len(m.cards) == len(rest)), None)
    if finish:
        return [finish]
    return min(plans(rest, level, wildcards), key=len)
