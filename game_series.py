"""掼蛋多局比赛：级牌从 2 逐步推进到 A。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from agents.base import Agent
from game_engine.card import Rank
from game_engine.round_result import RoundResult
from match_runner import Match


LEVELS = (Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN,
          Rank.EIGHT, Rank.NINE, Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE)


@dataclass
class GameSeries:
    """管理多局升级及下一局的进贡、抗贡、自动还贡。"""

    agents: list[Agent]
    level_rank: Rank = Rank.TWO
    team_levels: dict[str, Rank] = field(default_factory=lambda: {"A": Rank.TWO, "B": Rank.TWO})
    seed: Optional[int] = None
    verbose: bool = True
    event_callback: Optional[Callable[[str], None]] = None
    round_number: int = field(default=0, init=False)
    history: list[RoundResult] = field(default_factory=list, init=False)
    finished: bool = field(default=False, init=False)

    def _emit(self, message: str):
        if self.event_callback:
            self.event_callback(message)

    def _level_index(self) -> int:
        return LEVELS.index(self.level_rank)

    def play_round(self) -> RoundResult:
        if self.finished:
            raise RuntimeError("比赛已经结束")
        self.round_number += 1
        round_seed = None if self.seed is None else self.seed + self.round_number - 1
        self._emit(f"第 {self.round_number} 局开始：级牌 {self.level_rank.name}")
        match = Match(
            agents=self.agents,
            level_rank=self.level_rank,
            verbose=self.verbose,
            seed=round_seed,
            event_callback=self.event_callback,
            use_wildcards=True,
            team_levels=dict(self.team_levels),
            previous_result=self.history[-1] if self.history else None,
        )
        result = match.run()
        self.history.append(result)

        # A 级只有双下才结束；A 级单下继续留在 A 级。
        winning_team = result.winning_team
        if self.team_levels[winning_team] == Rank.ACE:
            self.level_rank = Rank.ACE
            if result.upgrade_level == 3:
                self.finished = True
                self._emit(f"{winning_team}队A级双下，比赛结束")
            else:
                self._emit(f"{winning_team}队A级未双下，下一局继续A级")
            return result

        old_level = self.team_levels[winning_team]
        next_index = min(LEVELS.index(old_level) + result.upgrade_level, len(LEVELS) - 1)
        self.team_levels[winning_team] = LEVELS[next_index]
        self.level_rank = self.team_levels[winning_team]
        self._emit(f"{winning_team}队 {old_level.name}级升 {result.upgrade_level} 级，下一局级牌：{self.team_levels[winning_team].name}")
        return result

    def run(self, max_rounds: int = 100) -> list[RoundResult]:
        while not self.finished and self.round_number < max_rounds:
            self.play_round()
        if not self.finished:
            raise RuntimeError(f"比赛未在 {max_rounds} 局内结束")
        return self.history


if __name__ == "__main__":
    from agents.rule_agent import RuleAgent

    series = GameSeries([RuleAgent(f"AI{i}") for i in range(4)], seed=42)
    series.run()
    print(f"比赛结束，共 {series.round_number} 局，最终级牌：{series.level_rank.name}")
