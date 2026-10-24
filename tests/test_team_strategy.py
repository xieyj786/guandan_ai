"""配合策略回归：只使用自己手牌和公开信息。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.base import Observation
from agents.rule_agent import RuleAgent
from game_engine.card import Card, Rank, Suit
from game_engine.identify import identify_card_type
from match_runner import Match


def cards(*ranks):
    result = []
    seen = {}
    suits = [Suit.SPADE, Suit.SPADE, Suit.CLUB, Suit.CLUB, Suit.DIAMOND, Suit.DIAMOND]
    for r in ranks:
        count = seen.get(r, 0)
        result.append(Card(Suit.JOKER if r > 14 else suits[count], Rank(r)))
        seen[r] = count + 1
    return result


def decide(hand, last=None, mate=1, opponents=(10, 10), teammate=False, played=()):
    return RuleAgent('test').decide(Observation(cards(*hand), Rank.TWO,
        identify_card_type(cards(*last), Rank.TWO) if last else None,
        mate, opponents, last_play_by_teammate=teammate, played_cards=list(played)))


def test_teammate_control_pass_and_finish():
    assert decide([5, 9], [3], teammate=True).action_type == 'pass'
    assert decide([5], [3], teammate=True).cards == cards(5)
    assert decide([3, 3, 3, 3]).cards == cards(3, 3, 3, 3)


def test_block_only_immediate_single_threat():
    assert decide([3, 16], [5], opponents=(1, 9), teammate=True).cards == cards(16)
    assert decide([3, 16], [5], opponents=(9, 1), teammate=True).action_type == 'pass'
    assert decide([3, 14], [5], opponents=(1, 9), teammate=True).cards == cards(14)  # DP04: 降低风险即可
    assert decide([3, 15], [16], opponents=(1, 9), teammate=True).action_type == 'pass'
    assert decide([3, 3, 3, 3, 9], [5, 5], opponents=(1, 9), teammate=True).action_type == 'pass'


def test_feed_loose_single_when_weak_but_preserve_groups():
    hand = [3, 5, 7, 9, 11, 11]
    assert decide(hand).cards == cards(3)
    assert decide(hand, mate=2).cards == cards(3)  # 正常领出也优先小散牌
    assert decide([3, 3, 5, 7, 9, 11]).cards == cards(5)
    assert len(decide(hand, opponents=(1, 9)).cards) == 2


def test_control_or_short_plan_uses_own_plan():
    assert decide([3, 5, 7, 9, 11, 11, 16]).cards == cards(3)
    assert decide([3, 5, 11, 11]).cards == cards(3)
    assert decide([3, 5, 7, 9, 11, 11, 11, 11]).cards == cards(3)


def test_public_cards_change_control_estimate():
    from game_engine.deck import build_deck
    exposed = [c for c in build_deck() if c.rank in (Rank.SMALL_JOKER, Rank.BIG_JOKER, Rank.TWO)]
    hand = [3, 5, 7, 9, 11, 11, 14]
    assert decide(hand).cards == cards(3)
    agent = RuleAgent('test')
    state = Observation(cards(*hand), Rank.TWO, None, 1, (10, 10))
    agent.decide(state)
    assert '帮助队友' in agent.decision_reason
    state.played_cards = exposed
    agent.decide(state)
    assert '帮助队友' not in agent.decision_reason
    assert decide(hand, played=exposed).cards == cards(3)


def test_match_public_observation_and_seeded_completion():
    for seed in range(10):
        match = Match([RuleAgent(f'AI{i}') for i in range(4)], seed=seed, verbose=False)
        match.prepare()
        actor = match.current_player
        match._take_turn()
        obs = match._build_observation((actor + 2) % 4)
        assert obs.last_play_by_teammate
        assert obs.played_cards == match.last_play.cards
        obs.played_cards.clear()
        assert match.played_cards
        match.run()
        assert len(match.finish_order) == 4
        assert len(match.played_cards) == 108
