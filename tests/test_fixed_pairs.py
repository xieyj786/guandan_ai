"""Consecutive pairs must have exactly three pairs, including wildcard interpretations."""
from game_engine.card import Card, Rank, Suit
from game_engine.card_type import CardTypeCategory as T, InvalidCardTypeError
from game_engine.identify import identify_card_type
from game_engine.moves import generate_all_moves
from agents.rule_agent import RuleAgent
from agents.base import Observation


def hand():
    return [Card(s,Rank(r)) for r in (5,6,7,8) for s in (Suit.SPADE,Suit.CLUB)]


def test_reject_four_pairs_natural_and_wild():
    for cards in (hand(),hand()[:-1]+[Card(Suit.HEART,Rank.TWO)]):
        try:identify_card_type(cards,Rank.TWO)
        except InvalidCardTypeError:pass
        else:assert False,'four pairs must not be accepted'


def test_generate_three_pair_windows_and_ai_legal():
    cards=hand()
    moves=generate_all_moves(cards,Rank.TWO)
    pairs=[m for m in moves if m.category==T.CONSECUTIVE_PAIRS]
    assert len(pairs)==2
    assert all(len(m.cards)==6 and m.length==3 for m in pairs)
    for m in pairs:assert identify_card_type(m.cards,Rank.TWO).category==T.CONSECUTIVE_PAIRS
    action=RuleAgent('test').decide(Observation(cards,Rank.TWO,None,12,(12,12)))
    assert len(action.cards)!=8
    identify_card_type(action.cards,Rank.TWO)


def test_wild_three_pairs_remain_legal():
    cards=hand()[:5]+[Card(Suit.HEART,Rank.TWO)]
    assert identify_card_type(cards,Rank.TWO).category==T.CONSECUTIVE_PAIRS
