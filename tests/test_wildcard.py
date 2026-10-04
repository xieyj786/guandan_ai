"""
逢人配（红心级牌）相关测试：引擎识别层的完整语义 + 出牌生成器/RuleAgent 的简单用法。
以下默认级牌为 2，红心 2 即逢人配。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.base import Observation
from agents.rule_agent import RuleAgent
from game_engine.card import LEVEL_RANK_POWER, Card, Rank, Suit
from game_engine.card_type import CardType, CardTypeCategory, InvalidCardTypeError
from game_engine.identify import enumerate_interpretations, identify_card_type
from game_engine.moves import generate_all_moves

L = Rank.TWO
W = Card(Suit.HEART, Rank.TWO)  # 逢人配


def C(suit, rank):
    return Card(suit, rank)


def ident(cards, last_play=None):
    return identify_card_type(cards, L, last_play=last_play)


def test_single_wildcard_uses_level_position():
    ct = ident([W])
    assert ct.category == CardTypeCategory.SINGLE
    assert ct.power == LEVEL_RANK_POWER


def test_wildcard_completes_pair_triple_and_bombs():
    nines = [C(Suit.SPADE, Rank.NINE), C(Suit.CLUB, Rank.NINE), C(Suit.DIAMOND, Rank.NINE), C(Suit.HEART, Rank.NINE)]
    assert ident(nines[:1] + [W]).category == CardTypeCategory.PAIR
    assert ident(nines[:2] + [W]).category == CardTypeCategory.TRIPLE
    assert ident(nines[:3] + [W]).category == CardTypeCategory.BOMB_4
    assert ident(nines + [W]).category == CardTypeCategory.BOMB_5
    assert ident(nines[:3] + [W, W]).category == CardTypeCategory.BOMB_5
    # 混炸与纯炸同大小
    assert ident(nines[:3] + [W]).power == ident(nines).power


def test_two_wildcards_form_level_pair():
    ct = ident([W, W])
    assert ct.category == CardTypeCategory.PAIR
    assert ct.power == LEVEL_RANK_POWER


def test_wildcard_cannot_substitute_jokers():
    big = Card(Suit.JOKER, Rank.BIG_JOKER)
    small = Card(Suit.JOKER, Rank.SMALL_JOKER)
    for cards in ([big, W], [big, big, W], [big, big, small, W]):
        try:
            ident(cards)
            assert False, f"{cards} 不应被识别为合法牌型"
        except InvalidCardTypeError:
            pass
    assert ident([big, big, small, small]).category == CardTypeCategory.JOKER_BOMB
    assert ident([big, big]).category == CardTypeCategory.PAIR  # 真王对子仍然合法


def test_wildcard_in_straight_and_flush():
    mixed = [C(Suit.SPADE, Rank.THREE), C(Suit.HEART, Rank.FOUR), C(Suit.CLUB, Rank.FIVE),
             C(Suit.SPADE, Rank.SIX), W]
    ct = ident(mixed)
    assert ct.category == CardTypeCategory.STRAIGHT and ct.power == float(Rank.SEVEN)  # 2 不入顺子，只能补 7

    spades = [C(Suit.SPADE, r) for r in (Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX)] + [W]
    assert ident(spades).category == CardTypeCategory.STRAIGHT_FLUSH  # 同花色 + 逢人配 = 同花顺


def test_best_interpretation_against_last_play():
    cards = [C(Suit.SPADE, Rank.FIVE), C(Suit.HEART, Rank.SIX), C(Suit.CLUB, Rank.SEVEN),
             C(Suit.SPADE, Rank.EIGHT), W]
    assert ident(cards).power == float(Rank.NINE)  # 无上家：取最大解释 5-9
    last = CardType(CardTypeCategory.STRAIGHT, [], power=8.0, length=5)
    assert ident(cards, last).power == float(Rank.NINE)  # 只有 5-9 能压过上家的 8
    high = CardType(CardTypeCategory.STRAIGHT, [], power=9.0, length=5)
    assert ident(cards, high).power == float(Rank.NINE)  # 压不过时仍返回最大解释，由调用方判定非法


def test_wildcard_in_consecutive_pairs_plate_and_triple_plus_two():
    pairs = [C(Suit.SPADE, Rank.THREE), C(Suit.CLUB, Rank.THREE), C(Suit.SPADE, Rank.FOUR),
             C(Suit.CLUB, Rank.FOUR), C(Suit.SPADE, Rank.FIVE), W]
    ct = ident(pairs)
    assert ct.category == CardTypeCategory.CONSECUTIVE_PAIRS and ct.power == float(Rank.FIVE)

    plate = [C(Suit.SPADE, Rank.SEVEN), C(Suit.CLUB, Rank.SEVEN), C(Suit.DIAMOND, Rank.SEVEN),
             C(Suit.SPADE, Rank.EIGHT), C(Suit.CLUB, Rank.EIGHT), W]
    kinds = {i.category for i in enumerate_interpretations(plate, L)}
    assert CardTypeCategory.PLATE in kinds

    t2 = [C(Suit.SPADE, Rank.NINE), C(Suit.CLUB, Rank.NINE), C(Suit.DIAMOND, Rank.NINE),
          C(Suit.SPADE, Rank.FOUR), W]
    ct = ident(t2)
    assert ct.category == CardTypeCategory.TRIPLE_WITH_PAIR and ct.power == float(Rank.NINE)


def test_generator_builds_wildcard_bombs_and_pairs():
    hand = [C(Suit.SPADE, Rank.NINE), C(Suit.CLUB, Rank.NINE), C(Suit.DIAMOND, Rank.NINE), W]
    with_wild = [m for m in generate_all_moves(hand, L) if m.wildcards_used]
    assert any(m.category == CardTypeCategory.BOMB_4 and m.power == 9.0 for m in with_wild)
    # 生成器给出的每个候选，都必须能被引擎识别为同一牌型
    for m in generate_all_moves(hand, L):
        assert identify_card_type(m.cards, L).category in {m.category, CardTypeCategory.STRAIGHT_FLUSH}


def test_rule_agent_prefers_natural_and_uses_wildcard_bomb_when_needed():
    def obs(hand, last):
        return Observation(hand=hand, level_rank=L, last_play=last, teammate_hand_size=20,
                           opponent_hand_sizes=(20, 20))

    # 天然对子 K 优先于"9+逢人配"的对子（尽量保留逢人配）
    hand = [C(Suit.SPADE, Rank.NINE), W, C(Suit.SPADE, Rank.KING), C(Suit.CLUB, Rank.KING)]
    action = RuleAgent("a").decide(obs(hand, CardType(CardTypeCategory.PAIR, [], power=5.0, length=2)))
    assert W not in action.cards

    # 压不过时，用逢人配补成炸弹
    hand = [C(Suit.SPADE, Rank.NINE), C(Suit.CLUB, Rank.NINE), C(Suit.DIAMOND, Rank.NINE), W]
    action = RuleAgent("a").decide(obs(hand, CardType(CardTypeCategory.PAIR, [], power=14.0, length=2)))
    assert action.action_type == "play" and W in action.cards
    assert identify_card_type(action.cards, L).category == CardTypeCategory.BOMB_4


def test_disabled_wildcards_and_observation_are_consistent():
    from match_runner import Match
    for enabled in (False, True):
        for level in (Rank.TWO, Rank.SEVEN, Rank.ACE):
            for seed in range(5):
                match = Match([RuleAgent(str(i)) for i in range(4)], seed=seed,
                              verbose=False, use_wildcards=enabled,
                              team_levels={"A": level, "B": Rank.FIVE})
                match.run()
                assert len(match.finish_order) == 4 and not any(match.hands)
    try:
        identify_card_type([C(Suit.SPADE, Rank.NINE), W], L, False)
    except InvalidCardTypeError:
        pass
    else:
        raise AssertionError("关闭百搭后不能补对子")


def test_ambiguous_plate_follows_with_matching_interpretation():
    from match_runner import Match
    cards = [C(s, r) for r in (Rank.SEVEN, Rank.EIGHT)
             for s in (Suit.SPADE, Suit.CLUB)] + [W, W]
    last = CardType(CardTypeCategory.PLATE, [], power=7, length=2)
    ct = identify_card_type(cards, L, last_play=last)
    assert ct.category == CardTypeCategory.PLATE and ct.power == 8
    match = Match([RuleAgent(str(i)) for i in range(4)], verbose=False)
    match.hands = [cards, [C(Suit.SPADE, Rank.ACE)], [], []]
    match.last_play = last
    # 此候选来自天然三张不足的钢板，AI 当前只补对子/三张/炸弹；人工出牌仍须正确校验。
    match._handle_play(0, cards)
    assert match.last_play.category == CardTypeCategory.PLATE


def test_two_wildcards_are_both_protected_in_tribute():
    from game_engine.tribute import determine_tribute_card
    ace = C(Suit.SPADE, Rank.ACE)
    assert determine_tribute_card([W, W, ace], L) == ace


def test_generated_moves_match_identifier_and_available_cards():
    from collections import Counter
    from game_engine.deck import deal_hands
    for level in (Rank.TWO, Rank.SEVEN, Rank.ACE):
        for hand in deal_hands(seed=42):
            for move in generate_all_moves(hand, level):
                assert not (Counter(move.cards) - Counter(hand))
                actual = identify_card_type(move.cards, level)
                assert (move.category, move.power, move.length) == (actual.category, actual.power, actual.length)
