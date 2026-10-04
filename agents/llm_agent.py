"""
LLM Agent：把 BaseLLMClient 接到 Agent 抽象层。

这里修复的是此前排查 Coze 代码时发现的关键问题：
    agent_player.py 里的 AgentPlayer._call_llm() 是一个永远返回空字符串的
    占位函数，从未真正调用 llm_coze.py / llm_deepseek.py 里写好的客户端——
    LLM 实际上一次都没被调用过，"接入LLM失败"的真正原因是接口没接线。

本模块把 client.chat() 真正接进 decide()，并且：
    - LLM 调用失败（LLMRequestError）或返回内容无法解析成合法出牌时，
      有明确的 fallback（默认 RuleAgent），不会再出现"看起来接了、
      实际没跑"的情况。
    - 出牌解析结果会校验是否真的对应手牌里的牌（防止 LLM 报出手里没有的牌）。
"""

from __future__ import annotations

import json
import re
from typing import Optional

from game_engine.card import Card, card_display, single_card_power
from .base import Action, Agent, Observation
from .llm_client import BaseLLMClient, LLMRequestError
from .rule_agent import RuleAgent

# 沿用 game_engine.card.card_display，命名保留 card_to_display 以兼容既有调用方/测试
card_to_display = card_display

PLAY_TEMPLATE = """你是一位掼蛋玩家，{personality}。

【当前游戏状态】
- 你的手牌: {hand}
- 本局级牌: {level_rank}
- 上一手出牌: {last_play}
- 队友剩余 {teammate_left} 张牌
- 对手剩余 {opp1_left} / {opp2_left} 张牌

【出牌规则】
1. 若上家出了牌，你必须出能压过它的同类型更大牌型，或炸弹，或选择"过"
2. 若你是首家，可以出任意合法牌型
3. 只能从你的手牌中选择要打出的牌，牌面用示例格式书写，如 "\u2660A"、"\u5927\u738b"

【输出格式，只输出 JSON，不要其他文字】
{{"think": "一句话说明思路", "action": "play 或 pass", "cards": ["牌1", "牌2", ...]}}

请决策：
"""


def _display_to_card(text: str, hand: list[Card]) -> Optional[Card]:
    """把 LLM 输出的牌面字符串映射回手牌里对应的 Card 对象（找第一张匹配的，避免重复引用同一张实例）。"""
    for card in hand:
        if card_to_display(card) == text.strip():
            return card
    return None


class LLMAgent(Agent):
    """
    由 LLM 驱动决策的 Agent。

    client: 任意 BaseLLMClient 实现（CozeLLMClient / DeepSeekLLMClient 等，策略可插拔）
    personality: 注入 Prompt 的人设文本，方便做多个风格不同的 LLM Agent
    fallback: LLM 调用失败或返回内容无法解析/校验时的兜底策略（默认 RuleAgent）
    """

    def __init__(self, name: str, client: BaseLLMClient, personality: str = "稳健型玩家", fallback: Optional[Agent] = None):
        super().__init__(name)
        self.client = client
        self.personality = personality
        self.fallback = fallback or RuleAgent(name=f"{name}(fallback)")

    def decide(self, observation: Observation) -> Action:
        prompt = self._build_prompt(observation)
        try:
            raw_response = self.client.chat(prompt)
        except LLMRequestError:
            return self.fallback.decide(observation)

        parsed = self._parse_response(raw_response)
        if parsed is None:
            return self.fallback.decide(observation)

        action_type, card_texts = parsed
        if action_type == "pass":
            return Action(action_type="pass")

        resolved = self._resolve_cards(card_texts, observation.hand)
        if resolved is None:
            return self.fallback.decide(observation)

        return Action(action_type="play", cards=resolved)

    def _build_prompt(self, observation: Observation) -> str:
        hand_str = ", ".join(
            card_to_display(c)
            for c in sorted(observation.hand, key=lambda c: single_card_power(c, observation.level_rank))
        )
        last_play_str = (
            "你是首家，可自由出牌"
            if observation.last_play is None
            else f"{observation.last_play.category.name}（力度 {observation.last_play.power}）"
        )

        return PLAY_TEMPLATE.format(
            personality=self.personality,
            hand=hand_str,
            level_rank=observation.level_rank.name,
            last_play=last_play_str,
            teammate_left=observation.teammate_hand_size,
            opp1_left=observation.opponent_hand_sizes[0],
            opp2_left=observation.opponent_hand_sizes[1],
        )

    @staticmethod
    def _parse_response(response: str) -> Optional[tuple[str, list[str]]]:
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", response)
            if not match:
                return None
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return None

        action_type = data.get("action")
        if action_type not in ("play", "pass"):
            return None
        cards = data.get("cards", []) if action_type == "play" else []
        if action_type == "play" and not cards:
            return None
        return action_type, cards

    @staticmethod
    def _resolve_cards(card_texts: list[str], hand: list[Card]) -> Optional[list[Card]]:
        """
        把 LLM 报出的牌面字符串一一映射回手牌中的 Card 对象。
        任意一张找不到、或重复引用了同一张牌实例，判定为无效响应（触发 fallback）。
        """
        remaining = list(hand)
        resolved: list[Card] = []
        for text in card_texts:
            card = _display_to_card(text, remaining)
            if card is None:
                return None
            resolved.append(card)
            remaining.remove(card)
        return resolved
