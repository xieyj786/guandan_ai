"""Shared multi-round progression for desktop, offline and simulation callers."""
from dataclasses import dataclass

from game_engine.card import Rank
from gameplay.series import LEVELS


@dataclass(frozen=True)
class Progress:
    team_levels: dict[str, Rank]
    leading_team: str
    finished: bool


def advance_levels(team_levels: dict[str, Rank], winner: str, upgrade: int) -> Progress:
    levels = dict(team_levels)
    current = levels[winner]
    finished = current == Rank.ACE and upgrade == 3
    if current != Rank.ACE:
        levels[winner] = LEVELS[min(LEVELS.index(current) + upgrade, len(LEVELS) - 1)]
    return Progress(levels, winner, finished)
