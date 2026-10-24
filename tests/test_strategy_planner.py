"""DP01–DP04 regression cases, with only public observation inputs."""
from collections import Counter
from agents.base import Observation
from agents.rule_agent import RuleAgent
from agents.strategy_planner import plans, tail_plan, StrategyOptions
from game_engine.card import Card, Rank, Suit
from game_engine.identify import identify_card_type
from game_engine.deck import build_deck


def cards(*ranks):
    counts = Counter()
    result = []
    for r in ranks:
        suit = Suit.JOKER if r > 14 else [Suit.SPADE, Suit.CLUB, Suit.DIAMOND, Suit.HEART][counts[r] % 4]
        result.append(Card(suit, Rank(r)))
        counts[r] += 1
    return result


def obs(hand, last, *, team=False, opponents=(12, 12), level=Rank.SEVEN, played=()):
    return Observation(hand, level, identify_card_type(last, level), 12, opponents,
                       last_play_by_teammate=team, played_cards=list(played))


def test_dp01_alternative_partitions_preserve_cards():
    hand = cards(14,14,14,3,3,3,4,4) + [Card(Suit.HEART, Rank.TWO)]
    alternatives = plans(hand, Rank.TWO)
    assert len(alternatives) >= 2
    for plan in alternatives:
        assert Counter(c for m in plan for c in m.cards) == Counter(hand)
    state = obs(hand, cards(13,13,13,13), level=Rank.TWO)
    action = RuleAgent('test').decide(state)
    assert len(action.cards) == 4 and any(c.rank == Rank.ACE for c in action.cards)
    assert len(tail_plan(hand, identify_card_type(action.cards, Rank.TWO), Rank.TWO)) == 1


def test_dp03_bomb_tail_and_ordinary_alternative():
    hand = cards(4,4,4,4,8,8,3)
    agent = RuleAgent('test')
    assert agent.decide(obs(hand, cards(2))).cards == cards(3)
    assert agent.decide(obs(hand, cards(14))).action_type == 'pass'
    action = agent.decide(obs(hand, cards(14), opponents=(1,12)))
    assert len(action.cards) == 4
    assert 'DP03' in agent.decision_reason
    assert agent.decision_trace['bomb_tail_hands'] == 2
    legacy = RuleAgent('test', options=StrategyOptions(bomb_routes=False))
    assert len(legacy.decide(obs(hand, cards(14))).cards) == 4


def test_dp02_last_bomb_and_small_tail():
    agent = RuleAgent('test')
    assert len(agent.decide(obs(cards(4,4,4,4), cards(14))).cards) == 4
    action = agent.decide(obs(cards(4,4,4,4,3,3), cards(14)))
    assert len(action.cards) == 4 and 'DP02' in agent.decision_reason


def test_dp04_low_cost_interception_and_counterexamples():
    hand = cards(12,3,9)
    state = obs(hand, cards(6), team=True, opponents=(1,12))
    agent = RuleAgent('test')
    assert agent.decide(state).action_type == 'play'
    legacy = RuleAgent('test', options=StrategyOptions(risk_interception=False))
    assert legacy.decide(state).action_type == 'pass'
    assert agent.decide(obs(hand, cards(16), team=True, opponents=(1,12))).action_type == 'pass'
    assert agent.decide(obs(hand, cards(6,6), team=True, opponents=(1,12))).action_type == 'pass'
    # All cards an ordinary blocker could stop are already publicly accounted for.
    exposed = [c for c in (Counter(build_deck()) - Counter(hand)).elements() if 6 < c.rank <= 12]
    assert agent.decide(obs(hand, cards(6), team=True, opponents=(1,12), played=exposed)).action_type == 'pass'


def test_dp04_bomb_with_final_pair():
    agent = RuleAgent('test')
    action = agent.decide(obs(cards(12,12,12,12,3,3), cards(6), team=True, opponents=(1,12)))
    assert len(action.cards) == 4 and '只剩一手' in agent.decision_reason
