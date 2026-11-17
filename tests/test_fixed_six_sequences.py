from game_engine.deck import build_deck
from game_engine.card import Rank, Suit
from game_engine.identify import enumerate_interpretations
from game_engine.moves import generate_all_moves
from game_engine.card_type import CardTypeCategory

def test_wood_and_steel_are_exactly_six_cards():
    deck = build_deck()
    def groups(start, end, size):
        return [c for rank in range(start, end + 1) for c in [c for c in deck if int(c.rank) == rank][:size]]
    for size, category in [(2, CardTypeCategory.CONSECUTIVE_PAIRS), (3, CardTypeCategory.PLATE)]:
        six = groups(11, 13 if size == 2 else 12, size)
        assert any(p.category == category for p in enumerate_interpretations(six, Rank.TWO))
        for count in [2, 3, 4]:
            cards = groups(11, 10 + count, size)
            if len(cards) == 6:
                continue
            assert not any(p.category == category for p in enumerate_interpretations(cards, Rank.TWO))
        long_hand = groups(11, 14, size)
        moves = [p for p in generate_all_moves(long_hand, Rank.TWO) if p.category == category]
        assert moves and all(len(p.cards) == 6 for p in moves)
    wild = next(c for c in deck if c.suit == Suit.HEART and c.rank == Rank.TWO)
    six = groups(11, 12, 3)
    assert any(p.category == CardTypeCategory.PLATE for p in enumerate_interpretations(six[:-1] + [wild], Rank.TWO))
    nine = groups(11, 13, 3)
    assert not any(p.category == CardTypeCategory.PLATE for p in enumerate_interpretations(nine[:-1] + [wild], Rank.TWO))


def test_bomb_limit_includes_heart_level_wildcards():
    deck = build_deck()
    fives = [c for c in deck if c.rank == Rank.FIVE][:7]
    wilds = [c for c in deck if c.suit == Suit.HEART and c.rank == Rank.TWO]
    eight = fives + wilds[:1]
    nine = fives + wilds
    assert any(p.category == CardTypeCategory.BOMB_8 for p in enumerate_interpretations(eight, Rank.TWO))
    assert not enumerate_interpretations(nine, Rank.TWO)
    moves = generate_all_moves(nine, Rank.TWO)
    assert any(p.category == CardTypeCategory.BOMB_8 and len(p.cards) == 8 for p in moves)
    assert all(len(p.cards) <= 8 for p in moves)
