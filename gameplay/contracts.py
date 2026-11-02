"""
Agent 抽象层：统一的观测/动作接口。

所有 Agent（人类输入适配器 / 规则AI / 搜索型AI / LLM Agent）都实现同一个
decide() 接口，这样 Match Server 层可以无差别地混合调用、混合组队。
见 rules_design.md 之外的架构讨论（系统架构第四节 Agent 抽象层）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from game_engine.card import Card, Rank
from game_engine.card_type import CardType


@dataclass
class Observation:
    """
    Agent 在轮到自己出牌时能看到的全部合法信息。
    不包含任何队友/对手手牌内容，只有已知的公开信息 + 自己手牌，
    保证 Agent 不会越权访问未公开状态。
    """
    hand: list[Card]                        # 自己当前手牌
    level_rank: Rank                        # 本局级牌
    last_play: Optional[CardType]           # 上一手有效出牌（None 表示需要自己首出）
    teammate_hand_size: int
    opponent_hand_sizes: tuple[int, int]    # 下家、上家对手的手牌数（按出牌顺序）
    last_play_by_teammate: bool = field(default=False, kw_only=True)
    played_cards: list[Card] = field(default_factory=list, kw_only=True)
    use_wildcards: bool = field(default=True, kw_only=True)
    play_history: list[str] = field(default_factory=list)  # 简要出牌历史，供 Prompt 等场景使用


@dataclass
class Action:
    """
    Agent 的决策结果。
    action_type: "play" 或 "pass"
    cards: action_type == "play" 时的出牌（必须是 hand 的子集，最终合法性由引擎再次校验）
    """
    action_type: str
    cards: list[Card] = field(default_factory=list)


class Agent(ABC):
    """所有 Agent 的统一接口：人类输入适配器 / 规则AI / 搜索型AI / LLM Agent 都实现它。"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def decide(self, observation: Observation) -> Action:
        """根据观测返回决策。子类必须实现。"""
        raise NotImplementedError
