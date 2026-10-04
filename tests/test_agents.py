"""
Agent 层单元测试。

核心验证目标：确认 LLMAgent 真正调用了 client.chat()（不是像此前 Coze 代码
里的 agent_player.py 那样，_call_llm 是个永远返回空字符串、从未被接线的占位函数），
并且在 LLM 调用失败 / 返回内容不可解析 / 报出手牌里没有的牌时，能正确走 fallback。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.base import Action, Observation
from agents.llm_agent import LLMAgent, card_to_display
from agents.llm_client import BaseLLMClient, LLMRequestError
from agents.rule_agent import RuleAgent
from game_engine.card import Card, Rank, Suit
from game_engine.card_type import CardType, CardTypeCategory


class FakeLLMClient(BaseLLMClient):
    """测试用假客户端：记录是否被真正调用过，返回预设响应或抛出预设异常。"""

    def __init__(self, response: str = "", raise_error: bool = False):
        super().__init__(max_retries=1)
        self.response = response
        self.raise_error = raise_error
        self.call_count = 0
        self.last_prompt = None

    def _send_request(self, prompt: str) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        if self.raise_error:
            raise LLMRequestError("模拟请求失败")
        return self.response


def make_hand():
    return [
        Card(Suit.SPADE, Rank.THREE),
        Card(Suit.HEART, Rank.FIVE),
        Card(Suit.CLUB, Rank.KING),
    ]


def make_observation(hand=None, last_play=None):
    return Observation(
        hand=hand if hand is not None else make_hand(),
        level_rank=Rank.TWO,
        last_play=last_play,
        teammate_hand_size=20,
        opponent_hand_sizes=(20, 20),
    )


def test_llm_agent_actually_calls_client_chat():
    """核心回归测试：确认 client.chat() 真正被调用（这是此前 Coze 代码断掉的那根线）。"""
    client = FakeLLMClient(response='{"think": "过一手", "action": "pass", "cards": []}')
    agent = LLMAgent(name="TestAgent", client=client)

    action = agent.decide(make_observation())

    assert client.call_count == 1, "LLMAgent 必须真正调用 client.chat()，而不是静默跳过"
    assert client.last_prompt is not None and "手牌" in client.last_prompt
    assert action.action_type == "pass"


def test_llm_agent_parses_play_and_resolves_card():
    hand = make_hand()
    king_text = card_to_display(hand[2])  # ♣K
    client = FakeLLMClient(response=f'{{"think": "出王", "action": "play", "cards": ["{king_text}"]}}')
    agent = LLMAgent(name="TestAgent", client=client)

    action = agent.decide(make_observation(hand=hand))

    assert action.action_type == "play"
    assert action.cards == [hand[2]]


def test_llm_agent_falls_back_on_request_error():
    client = FakeLLMClient(raise_error=True)
    fallback_called = {"count": 0}

    class SpyFallback(RuleAgent):
        def decide(self, observation):
            fallback_called["count"] += 1
            return super().decide(observation)

    agent = LLMAgent(name="TestAgent", client=client, fallback=SpyFallback(name="fallback"))
    action = agent.decide(make_observation())

    assert fallback_called["count"] == 1
    assert action.action_type in ("play", "pass")


def test_llm_agent_falls_back_on_invalid_json():
    client = FakeLLMClient(response="这不是JSON，是LLM瞎说的话")
    agent = LLMAgent(name="TestAgent", client=client)

    action = agent.decide(make_observation())
    # fallback 是 RuleAgent，首出时应打出最小单张
    assert action.action_type == "play"


def test_llm_agent_falls_back_when_card_not_in_hand():
    client = FakeLLMClient(response='{"action": "play", "cards": ["♠A"]}')  # 手牌里没有黑桃A
    agent = LLMAgent(name="TestAgent", client=client)

    action = agent.decide(make_observation())
    # 应触发 fallback，而不是返回一张不存在的牌
    assert action.action_type == "play"
    assert action.cards[0] in make_hand() or action.cards[0] == make_hand()[0]


def test_rule_agent_leads_with_smallest_card():
    hand = make_hand()
    agent = RuleAgent(name="Rule")
    action = agent.decide(make_observation(hand=hand, last_play=None))

    assert action.action_type == "play"
    assert action.cards == [hand[0]]  # ♠3 是最小的


def test_rule_agent_follows_single_with_bigger_card():
    hand = make_hand()
    last_play = CardType(category=CardTypeCategory.SINGLE, cards=[], power=4.0, length=1)  # 比♠3(power=3)大
    agent = RuleAgent(name="Rule")

    action = agent.decide(make_observation(hand=hand, last_play=last_play))

    assert action.action_type == "play"
    assert action.cards[0].rank == Rank.FIVE  # ♥5 是第一张比power=4大的


def test_rule_agent_passes_when_cannot_beat():
    hand = [Card(Suit.SPADE, Rank.THREE)]
    last_play = CardType(category=CardTypeCategory.SINGLE, cards=[], power=16.0, length=1)  # 大王力度，无法压过
    agent = RuleAgent(name="Rule")

    action = agent.decide(make_observation(hand=hand, last_play=last_play))
    assert action.action_type == "pass"


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
