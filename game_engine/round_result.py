"""
终局判定与升级逻辑。见 rules_design.md 2 节。
"""

from dataclasses import dataclass
from enum import Enum


class TributeType(Enum):
    NONE = "none"        # 理论上不会出现（每局必产生进贡或抗贡场景）
    SINGLE = "single"    # 单贡：仅末游上贡
    DOUBLE = "double"    # 双贡：三游、末游都上贡


@dataclass
class Player:
    player_id: str
    team: str


@dataclass
class RoundResult:
    winning_team: str
    upgrade_level: int
    tribute_type: TributeType
    tribute_players: list[Player]   # 需要上贡的玩家（单贡1人，双贡2人）
    finish_order: list[Player]      # 按出完顺序：[头游, 二游, 三游, 末游]

    @property
    def head_player(self) -> Player:
        return self.finish_order[0]

    @property
    def second_player(self) -> Player:
        return self.finish_order[1]

    @property
    def last_player(self) -> Player:
        return self.finish_order[3]


def judge_round_end(finish_order: list[Player]) -> RoundResult:
    """
    根据出完牌顺序判定本局结果。

    Args:
        finish_order: 按出完顺序排列的 4 名玩家 [头游, 二游, 三游, 末游]

    Returns:
        RoundResult
    """
    if len(finish_order) != 4:
        raise ValueError("finish_order 必须包含 4 名玩家")

    first, second, third, fourth = finish_order
    winning_team = first.team

    if second.team == winning_team:
        upgrade = 3
        tribute_type = TributeType.DOUBLE
        tribute_players = [third, fourth]
    elif third.team == winning_team:
        upgrade = 2
        tribute_type = TributeType.SINGLE
        tribute_players = [fourth]
    else:  # fourth.team == winning_team
        upgrade = 1
        tribute_type = TributeType.SINGLE
        tribute_players = [fourth]

    return RoundResult(
        winning_team=winning_team,
        upgrade_level=upgrade,
        tribute_type=tribute_type,
        tribute_players=tribute_players,
        finish_order=finish_order,
    )
