"""领出策略：小完整组、控制牌保护、报单例外与日志。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collections import Counter
from agents.base import Observation
from agents.rule_agent import RuleAgent
from game_engine.card import Card, Rank, Suit
from game_engine.card_type import CardTypeCategory as T
from game_engine.identify import identify_card_type
from game_engine.deck import deal_hands
from match_runner import Match
from turn_log import format_turn_log


def c(rank, suit=Suit.SPADE):
    return Card(suit, Rank(rank))


def act(hand, opponents=(12, 12)):
    agent = RuleAgent('test')
    result = agent.decide(Observation(hand, Rank.TWO, None, 12, opponents))
    return result, agent.decision_reason


def test_small_groups_before_straight():
    straight = [c(7), c(8, Suit.CLUB), c(9), c(10), c(11)]
    for small in ([c(3)], [c(3), c(3)], [c(3), c(3), c(3, Suit.CLUB)],
                  [c(3), c(3), c(3, Suit.CLUB), c(5), c(5)]):
        action, reason = act(straight + small)
        assert Counter(action.cards) == Counter(small)
        assert '小牌组合' in reason


def test_preserve_flush_and_bomb_without_splitting():
    for control in ([c(i) for i in range(3, 8)],
                    [c(3), c(3), c(3, Suit.CLUB), c(3, Suit.CLUB)]):
        hand = control + [c(9), c(11), c(11)]
        action, reason = act(hand)
        assert action.cards == [c(9)]
        assert '保留' in reason
        remainder = list(hand)
        for card in action.cards: remainder.remove(card)
        action, _ = act(remainder)
        assert action.cards == [c(11), c(11)]
        assert Counter(act(control)[0].cards) == Counter(control)  # 能走完仍直接走


def test_do_not_break_pair_or_straight_for_smallest_single():
    action, _ = act([c(3), c(3), c(5)])
    assert action.cards == [c(3), c(3)]
    run = [c(3), c(4, Suit.CLUB), c(5), c(6), c(7)]
    action, _ = act(run + [c(13)])
    assert identify_card_type(action.cards, Rank.TWO).category == T.STRAIGHT


def test_opponent_single_overrides_small_single_without_teammate_single():
    action, reason = act([c(3), c(9), c(9)], opponents=(1, 8))
    assert action.cards == [c(9), c(9)] and '报单' in reason


def test_partition_uses_each_card_once_and_logs_reason():
    for seed in range(20):
        for hand in deal_hands(seed):
            plan = RuleAgent._estimate_plan(Observation(hand, Rank.TWO, None, 27, (27, 27)))
            assert Counter(c for move in plan for c in move.cards) == Counter(hand)
    match = Match([RuleAgent(f'AI{i}') for i in range(4)], seed=19, verbose=False)
    match.prepare()
    index = match.current_player
    before = len(match.hands[index])
    match._take_turn()
    logs = format_turn_log(match, index, before, 1)
    assert any('〔规则AI〕' in line for line in logs)
    assert match.last_rule_reason is None
